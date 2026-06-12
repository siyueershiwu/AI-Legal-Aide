"""入库 pipeline: file → parse → chunk → dedup → embed → 写 DB + ChromaDB。

法律语境下的关键差异：
- 当 doc_type == "statute" 时走 law_chunker (按"第N条"切分 + hierarchy 前缀)
- 其它 doc_type (interpretation / commentary / scenario / boundary / diff / repeal_note / other)
  继续走通用 chunker；如果文本里能识别到 "第N条" 也尽量打 article_no 标签
- chunk 元数据带 law_code / doc_type / version / is_current / article_no / title

入库是 CPU 密集型（embedding），但单 doc < 500 chunk 时 < 10s 同步可接受。
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge import (
    DOC_TYPE_VALUES,
    LAW_CODE_VALUES,
    KnowledgeChunk,
    KnowledgeDocument,
)
from app.repositories.file_repo import FileRepository
from app.repositories.knowledge_repo import KnowledgeRepository
from app.services.document_parser import document_parser
from app.services.rag.chunker import chunk_hash, split_text
from app.services.rag.embedder import embedder
from app.services.rag.law_chunker import LawChunk, extract_article_refs, split_law_text
from app.services.rag.vector_store import vector_store
from app.services.storage import storage

logger = logging.getLogger(__name__)


class IngestError(Exception):
    """入库失败（带可读 message 抛给上层 → HTTP 4xx）。"""


def _build_chunks_for_doc(
    raw_text: str,
    *,
    doc_type: str,
    law_title: str,
) -> list[dict]:
    """根据 doc_type 选切分器；返回 [{text, article_no?}, ...] 待入 chunk_items。

    - statute      → law_chunker（按条切 + hierarchy 前缀 + article_no）
    - 其它 doc_type → 通用 chunker；尝试从每段文本里抓 "第N条" 反查 article_no
    """
    if doc_type == "statute":
        law_chunks: list[LawChunk] = split_law_text(
            raw_text, law_title=law_title, soft_limit=max(800, settings.CHUNK_SIZE)
        )
        if not law_chunks:
            # 如果没识别到任何 "第N条" 标题，降级走通用切分器
            logger.warning("law_chunker found 0 articles, fallback to generic split_text")
            generic = split_text(raw_text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
            return [{"text": t, "article_no": _guess_article_no(t)} for t in generic]
        return [
            {"text": c.text, "article_no": c.article_no or None}
            for c in law_chunks
        ]

    # 非法条正文：通用切分 + 尽力打 article_no
    generic = split_text(raw_text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
    return [{"text": t, "article_no": _guess_article_no(t)} for t in generic]


def _guess_article_no(text: str) -> Optional[str]:
    """从释义/场景类 chunk 内识别第一个 "第N条" 引用，便于关联回正文。"""
    refs = extract_article_refs(text[:400])  # 只看前 400 字（标题区）
    return refs[0] if refs else None


async def ingest_file(
    db: AsyncSession,
    *,
    file_id: str,
    title: str,
    law_code: str,
    doc_type: str,
    version: str = "current",
    is_current: bool = True,
    effective_date: Optional[date] = None,
    repealed_date: Optional[date] = None,
    issuing_body: Optional[str] = None,
    article_range: Optional[str] = None,
    source_type: str = "upload",
    owner_id: Optional[str] = None,
) -> KnowledgeDocument:
    """单文件入库完整流程。失败回滚（删 DB 行 + 删向量）。"""
    if law_code not in LAW_CODE_VALUES:
        raise IngestError(f"不支持的法律名称: {law_code}（允许: {LAW_CODE_VALUES}）")
    if doc_type not in DOC_TYPE_VALUES:
        raise IngestError(f"不支持的文档类型: {doc_type}（允许: {DOC_TYPE_VALUES}）")

    file_repo = FileRepository(db)
    kb_repo = KnowledgeRepository(db)

    file_record = await file_repo.get_by_id(file_id)
    if not file_record:
        raise IngestError(f"文件不存在: {file_id}")

    try:
        file_bytes = storage.get_data(file_record.object_name)
    except Exception as e:
        raise IngestError(f"下载文件失败: {e}") from e

    file_ext = os.path.splitext(file_record.file_name)[1]
    raw_text = document_parser.parse(file_bytes, file_ext)
    if not raw_text or raw_text.startswith("不支持") or "解析失败" in raw_text:
        raise IngestError(f"文档解析失败: {raw_text or '空内容'}")

    # 按 doc_type 选切分器
    chunk_specs = _build_chunks_for_doc(raw_text, doc_type=doc_type, law_title=law_code)
    # 去重：同 hash 的 text 去重（保留首个的 article_no）
    seen_hashes: set[str] = set()
    deduped: list[dict] = []
    for spec in chunk_specs:
        h = chunk_hash(spec["text"])
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        deduped.append({**spec, "content_hash": h})
    if not deduped:
        raise IngestError("文档内容为空或全部重复")

    texts = [s["text"] for s in deduped]

    doc_id = str(uuid.uuid4())
    try:
        doc = await kb_repo.create_doc(
            doc_id=doc_id,
            title=title,
            law_code=law_code,
            doc_type=doc_type,
            version=version,
            is_current=is_current,
            effective_date=effective_date,
            repealed_date=repealed_date,
            issuing_body=issuing_body,
            article_range=article_range,
            source_type=source_type,
            file_id=file_id,
            owner_id=owner_id,
        )
    except Exception as e:
        raise IngestError(f"创建文档记录失败: {e}") from e

    try:
        embeddings = await embedder.embed_documents(texts)
    except Exception as e:
        await kb_repo.delete_doc(doc_id)
        await db.commit()
        raise IngestError(f"向量化失败: {e}") from e

    chunk_items = [
        {
            "chunk_index": i,
            "text": spec["text"],
            "char_count": len(spec["text"]),
            "content_hash": spec["content_hash"],
            "article_no": spec.get("article_no"),
        }
        for i, spec in enumerate(deduped)
    ]
    try:
        rows = await kb_repo.add_chunks(doc_id, chunk_items)
    except Exception as e:
        await kb_repo.delete_doc(doc_id)
        await db.commit()
        raise IngestError(f"写 chunk 失败: {e}") from e

    ids = [r.id for r in rows]
    metadatas = [
        {
            "document_id": doc_id,
            "chunk_id": row.id,
            "law_code": law_code,
            "doc_type": doc_type,
            "version": version,
            "is_current": is_current,
            "article_no": row.article_no or "",
            "title": title,
        }
        for row in rows
    ]
    try:
        await vector_store.add_async(ids, embeddings, texts, metadatas)
    except Exception as e:
        await kb_repo.delete_doc(doc_id)
        await db.commit()
        raise IngestError(f"写向量库失败: {e}") from e

    await kb_repo.update_doc_counts(
        doc_id, chunk_count=len(deduped), char_count=len(raw_text)
    )
    await db.commit()

    logger.info(
        "Ingested doc %s: %d chunks, %d chars, law=%s type=%s version=%s is_current=%s",
        doc_id, len(deduped), len(raw_text),
        law_code, doc_type, version, is_current,
    )
    return doc


async def delete_document(db: AsyncSession, doc_id: str) -> bool:
    """删 KnowledgeDocument（cascade 删 chunks） + 删 ChromaDB 向量。"""
    kb_repo = KnowledgeRepository(db)
    doc = await kb_repo.get_doc(doc_id)
    if not doc:
        return False
    await vector_store.delete_by_document_async(doc_id)
    await kb_repo.delete_doc(doc_id)
    await db.commit()
    return True


async def rebuild_all(db: AsyncSession) -> dict:
    """清空 ChromaDB + 重新跑所有 doc 的入库。"""
    kb_repo = KnowledgeRepository(db)
    docs = list(await kb_repo.list_all_docs())
    await vector_store.reset_async()
    success = 0
    failed = 0
    errors: list[str] = []
    for doc in docs:
        try:
            await _reingest_existing(db, doc)
            success += 1
        except Exception as e:
            failed += 1
            errors.append(f"{doc.title}: {e}")
            logger.exception("rebuild ingest failed: %s", doc.title)
    return {"success": success, "failed": failed, "errors": errors[:10]}


async def _reingest_existing(db: AsyncSession, doc: KnowledgeDocument) -> None:
    """重建时复用元数据重新入库。失败抛异常让 rebuild 捕获。"""
    if not doc.file_id:
        raise IngestError(f"doc {doc.id} 无关联 file_id")
    file_repo = FileRepository(db)
    file_record = await file_repo.get_by_id(doc.file_id)
    if not file_record:
        raise IngestError(f"doc {doc.id} 关联文件已删除")

    file_bytes = storage.get_data(file_record.object_name)
    file_ext = os.path.splitext(file_record.file_name)[1]
    raw_text = document_parser.parse(file_bytes, file_ext)

    chunk_specs = _build_chunks_for_doc(raw_text, doc_type=doc.doc_type, law_title=doc.law_code)
    seen_hashes: set[str] = set()
    deduped: list[dict] = []
    for spec in chunk_specs:
        h = chunk_hash(spec["text"])
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        deduped.append({**spec, "content_hash": h})
    if not deduped:
        raise IngestError(f"doc {doc.id} 解析为空")

    texts = [s["text"] for s in deduped]
    embeddings = await embedder.embed_documents(texts)

    # 清旧 chunks（直接走 SQL，避免 ORM cascade 异步坑）
    old_chunks = (await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id)
    )).scalars().all()
    for c in old_chunks:
        await db.delete(c)
    await db.flush()

    # 写新 chunks
    new_rows: list[KnowledgeChunk] = []
    for i, spec in enumerate(deduped):
        r = KnowledgeChunk(
            document_id=doc.id,
            chunk_index=i,
            text=spec["text"],
            char_count=len(spec["text"]),
            content_hash=spec["content_hash"],
            article_no=spec.get("article_no"),
        )
        db.add(r)
        new_rows.append(r)
    await db.flush()
    for r in new_rows:
        await db.refresh(r)

    metadatas = [
        {
            "document_id": doc.id,
            "chunk_id": r.id,
            "law_code": doc.law_code,
            "doc_type": doc.doc_type,
            "version": doc.version,
            "is_current": doc.is_current,
            "article_no": r.article_no or "",
            "title": doc.title,
        }
        for r in new_rows
    ]
    await vector_store.add_async([r.id for r in new_rows], embeddings, texts, metadatas)
    doc.chunk_count = len(deduped)
    doc.char_count = len(raw_text)
    await db.commit()
