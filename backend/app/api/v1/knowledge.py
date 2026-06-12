"""法律知识库管理路由。

设计:
- 所有端点要求登录（CurrentUser 鉴权）
- 上传两步走: 先 POST /files/upload 拿 file_id，再 POST /knowledge/documents 触发入库
- 检索预览 (preview-search) 给 admin 验证入库质量
- 清空重建 (rebuild) 跑在后台（这里是同步实现，doc 数量大时会阻塞 ~数分钟；
  生产可考虑 FastAPI BackgroundTasks 或独立 worker，本项目 MVP 不做）
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import BadRequestError, NotFoundError
from app.repositories.knowledge_repo import KnowledgeRepository
from app.schemas.knowledge import (
    BatchDeleteRequest,
    KnowledgeCreateRequest,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentOut,
    KnowledgeMetaResponse,
    KnowledgePreviewResponse,
    KnowledgeRebuildResponse,
    KnowledgeSourceOut,
    KnowledgeStatsResponse,
    LAW_CODE_OPTIONS,
    DOC_TYPE_OPTIONS,
)
from app.services.rag.ingest import (
    IngestError,
    delete_document,
    ingest_file,
    rebuild_all,
)
from app.services.rag.retriever import retrieve

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["法律知识库"])


@router.get("/meta", response_model=KnowledgeMetaResponse)
async def get_meta() -> KnowledgeMetaResponse:
    """元数据枚举。前端用这个生成下拉选项，避免硬编码。"""
    return KnowledgeMetaResponse(
        law_codes=LAW_CODE_OPTIONS,
        doc_types=DOC_TYPE_OPTIONS,
    )


@router.post(
    "/documents",
    response_model=KnowledgeDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_document(
    req: KnowledgeCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> KnowledgeDocumentOut:
    """入库一个新法律文档（两步走的第二步）。"""
    try:
        doc = await ingest_file(
            db,
            file_id=req.file_id,
            title=req.title,
            law_code=req.law_code,
            doc_type=req.doc_type,
            version=req.version,
            is_current=req.is_current,
            effective_date=req.effective_date,
            repealed_date=req.repealed_date,
            issuing_body=req.issuing_body,
            article_range=req.article_range,
            source_type=req.source_type,
            owner_id=current_user.id,
        )
    except IngestError as e:
        raise BadRequestError(str(e))
    return KnowledgeDocumentOut.model_validate(doc)


@router.get("/documents", response_model=KnowledgeDocumentListResponse)
async def list_documents(
    db: DbSession,
    current_user: CurrentUser,
    law_code: str | None = None,
    doc_type: str | None = None,
    is_current: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> KnowledgeDocumentListResponse:
    """列出已入库文档。可按 law_code / doc_type / is_current 过滤。"""
    repo = KnowledgeRepository(db)
    docs = await repo.list_docs(
        law_code=law_code,
        doc_type=doc_type,
        is_current=is_current,
        limit=limit,
        offset=offset,
    )
    return KnowledgeDocumentListResponse(
        documents=[KnowledgeDocumentOut.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.delete("/documents/{document_id}")
async def delete_document_endpoint(
    document_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> JSONResponse:
    """删除单个文档（删 DB + 删 ChromaDB 向量）。"""
    ok = await delete_document(db, document_id)
    if not ok:
        raise NotFoundError(f"文档不存在: {document_id}")
    return JSONResponse({"success": True, "id": document_id})


@router.post("/documents/batch-delete")
async def batch_delete_documents(
    req: BatchDeleteRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> JSONResponse:
    """批量删除。返回成功/失败统计。"""
    success = 0
    failed: list[str] = []
    for did in req.ids:
        try:
            if await delete_document(db, did):
                success += 1
            else:
                failed.append(f"{did}: 不存在")
        except Exception as e:
            failed.append(f"{did}: {e}")
    return JSONResponse({"success": success, "failed": failed, "total": len(req.ids)})


@router.post("/rebuild", response_model=KnowledgeRebuildResponse)
async def rebuild(db: DbSession, current_user: CurrentUser) -> KnowledgeRebuildResponse:
    """清空 ChromaDB + 重新跑所有 doc 的入库。

    同步实现。doc 数量大（>100）时会阻塞 ~数分钟。
    """
    result = await rebuild_all(db)
    return KnowledgeRebuildResponse(**result)


@router.get("/stats", response_model=KnowledgeStatsResponse)
async def stats(db: DbSession, current_user: CurrentUser) -> KnowledgeStatsResponse:
    """知识库统计：总文档/总 chunk/总字符 + 按 law_code/doc_type 分组 + 现行/废止计数。"""
    repo = KnowledgeRepository(db)
    s = await repo.stats()
    return KnowledgeStatsResponse(**s)


@router.get("/preview-search", response_model=KnowledgePreviewResponse)
async def preview_search(
    q: str,
    db: DbSession,
    current_user: CurrentUser,
    law_code: str | None = None,
    doc_type: str | None = None,
    include_repealed: bool = False,
    top_k: int = 5,
) -> KnowledgePreviewResponse:
    """检索预览（admin 验证入库质量用，不带 LLM）。"""
    if top_k < 1 or top_k > 20:
        raise BadRequestError("top_k 必须在 1-20 之间")
    chunks = await retrieve(
        q,
        law_code=law_code,
        doc_type=doc_type,
        top_k=top_k,
        include_repealed=include_repealed,
    )
    return KnowledgePreviewResponse(
        sources=[
            KnowledgeSourceOut(
                title=c["title"],
                law_code=c["law_code"],
                doc_type=c["doc_type"],
                version=c["version"],
                is_current=c.get("is_current", True),
                article_no=c.get("article_no") or None,
                score=c["score"],
                snippet=c["snippet"],
            )
            for c in chunks
        ]
    )
