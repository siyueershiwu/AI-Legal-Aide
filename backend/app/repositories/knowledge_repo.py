"""法律知识库 ORM 仓库。

- 创建文档: create_doc() — 自动 refresh 拿 server_default (created_at / updated_at / is_current)
- 切分写入: add_chunks() — 批量；items 可携带 article_no
- 查询: get_doc / list_docs / stats / get_by_article (精准条号命中)
- 删除: delete_doc (cascade 删 chunks via ORM)
"""
from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeChunk, KnowledgeDocument


class KnowledgeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ===== Document =====

    async def create_doc(
        self,
        *,
        doc_id: str,
        title: str,
        law_code: str,
        doc_type: str,
        version: str = "current",
        is_current: bool = True,
        effective_date=None,
        repealed_date=None,
        issuing_body: Optional[str] = None,
        article_range: Optional[str] = None,
        source_type: str = "upload",
        file_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> KnowledgeDocument:
        record = KnowledgeDocument(
            id=doc_id,
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
        self.db.add(record)
        await self.db.flush()
        # 强制加载 server_default (created_at / updated_at)，与 file_repo 同样的 async-sa 约束。
        await self.db.refresh(record)
        return record

    async def get_doc(self, doc_id: str) -> Optional[KnowledgeDocument]:
        return await self.db.get(KnowledgeDocument, doc_id)

    async def list_docs(
        self,
        *,
        law_code: Optional[str] = None,
        doc_type: Optional[str] = None,
        is_current: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[KnowledgeDocument]:
        stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())
        if law_code:
            stmt = stmt.where(KnowledgeDocument.law_code == law_code)
        if doc_type:
            stmt = stmt.where(KnowledgeDocument.doc_type == doc_type)
        if is_current is not None:
            stmt = stmt.where(KnowledgeDocument.is_current == is_current)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_all_docs(self) -> Sequence[KnowledgeDocument]:
        result = await self.db.execute(select(KnowledgeDocument))
        return result.scalars().all()

    async def delete_doc(self, doc_id: str) -> bool:
        record = await self.get_doc(doc_id)
        if not record:
            return False
        await self.db.delete(record)  # CASCADE 删 chunks
        return True

    async def update_doc_counts(
        self, doc_id: str, *, chunk_count: int, char_count: int
    ) -> None:
        record = await self.get_doc(doc_id)
        if not record:
            return
        record.chunk_count = chunk_count
        record.char_count = char_count

    # ===== Chunk =====

    async def add_chunks(
        self,
        doc_id: str,
        items: list[dict],
    ) -> list[KnowledgeChunk]:
        """items: [{chunk_index, text, char_count, content_hash, article_no?}, ...]"""
        rows = [
            KnowledgeChunk(
                document_id=doc_id,
                chunk_index=item["chunk_index"],
                text=item["text"],
                char_count=item["char_count"],
                content_hash=item["content_hash"],
                article_no=item.get("article_no"),
            )
            for item in items
        ]
        self.db.add_all(rows)
        await self.db.flush()
        # refresh 拿 created_at
        for r in rows:
            await self.db.refresh(r)
        return rows

    async def chunks_by_doc(self, doc_id: str) -> Sequence[KnowledgeChunk]:
        stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == doc_id)
            .order_by(KnowledgeChunk.chunk_index)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def chunks_by_article(
        self,
        *,
        law_code: str,
        article_no: str,
        is_current: Optional[bool] = True,
        limit: int = 5,
    ) -> list[dict]:
        """精准条号命中：跳过向量检索，直接按 (law_code, article_no) 查 chunks。

        返回 retriever 兼容格式（dict 列表），用于 retrieve() 第一层精准匹配分支。
        """
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.law_code == law_code)
            .where(KnowledgeChunk.article_no == article_no)
        )
        if is_current is not None:
            stmt = stmt.where(KnowledgeDocument.is_current == is_current)
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        out: list[dict] = []
        for chunk, doc in result.all():
            out.append({
                "snippet": chunk.text[:500],
                "title": doc.title,
                "law_code": doc.law_code,
                "doc_type": doc.doc_type,
                "version": doc.version,
                "is_current": doc.is_current,
                "article_no": chunk.article_no,
                "document_id": doc.id,
                "chunk_id": chunk.id,
                "score": 1.0,  # 精准命中给最高分
            })
        return out

    # ===== Stats =====

    async def stats(self) -> dict:
        """全局 + 按 law_code/doc_type 聚合 + 现行/废止计数。"""
        total_docs = await self.db.scalar(select(func.count(KnowledgeDocument.id))) or 0
        total_chunks = await self.db.scalar(select(func.count(KnowledgeChunk.id))) or 0
        total_chars = await self.db.scalar(
            select(func.coalesce(func.sum(KnowledgeDocument.char_count), 0))
        ) or 0

        # 按法律名分组
        by_law_rows = await self.db.execute(
            select(
                KnowledgeDocument.law_code,
                func.count(KnowledgeDocument.id),
            ).group_by(KnowledgeDocument.law_code)
        )
        by_law_code = {row[0]: row[1] for row in by_law_rows.all()}

        # 按文档类型分组
        by_type_rows = await self.db.execute(
            select(
                KnowledgeDocument.doc_type,
                func.count(KnowledgeDocument.id),
            ).group_by(KnowledgeDocument.doc_type)
        )
        by_doc_type = {row[0]: row[1] for row in by_type_rows.all()}

        # 现行 / 废止 版本计数
        current_count = await self.db.scalar(
            select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.is_current.is_(True))
        ) or 0
        repealed_count = await self.db.scalar(
            select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.is_current.is_(False))
        ) or 0

        return {
            "total_documents": int(total_docs),
            "total_chunks": int(total_chunks),
            "total_characters": int(total_chars),
            "by_law_code": by_law_code,
            "by_doc_type": by_doc_type,
            "current_count": int(current_count),
            "repealed_count": int(repealed_count),
        }
