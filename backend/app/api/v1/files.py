"""文件路由 - 上传 / 下载 / 解析"""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, File, Query, UploadFile, status

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import BadRequestError, NotFoundError
from app.repositories.file_repo import FileRepository
from app.schemas.file import FileOut, FileParseResponse, FileUploadResponse, FileUrlResponse
from app.services.document_parser import document_parser
from app.services.storage import storage

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp",
    "text/plain", "text/markdown", "text/csv",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
    ".txt", ".md", ".csv", ".pdf", ".doc", ".docx",
}


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    current_user: CurrentUser = ...,
    db: DbSession = ...,
) -> FileUploadResponse:
    filename = file.filename or "unknown"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BadRequestError(f"不支持的文件扩展名: {ext}")
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestError(f"不支持的文件类型: {file.content_type}")

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise BadRequestError(
            f"文件大小超过限制 ({settings.MAX_FILE_SIZE // 1024 // 1024}MB)"
        )

    file_id = str(uuid.uuid4())
    object_name = f"{file_id}{ext}"
    content_type = file.content_type or "application/octet-stream"

    try:
        storage.upload_data(object_name, content, content_type)
        url = storage.get_presigned_url(object_name)
    except Exception as e:
        # Storage 自身的 StorageUnavailable 已是 503，其他异常归 500
        from app.services.storage import StorageUnavailable
        if isinstance(e, StorageUnavailable):
            raise
        raise BadRequestError(f"上传失败: {e}")

    repo = FileRepository(db)
    record = await repo.create(
        file_id=file_id,
        object_name=object_name,
        file_name=filename,
        content_type=content_type,
        size=len(content),
        url=url,
        user_id=current_user.id,
    )
    await db.commit()

    return FileUploadResponse(
        file_id=record.id,
        object_name=record.object_name,
        url=record.url or "",
        name=record.file_name,
        type=record.content_type or "application/octet-stream",
        size=record.size or 0,
        created_at=record.created_at,
    )


@router.get("/{file_id}", response_model=FileOut)
async def get_file_info(
    file_id: str, current_user: CurrentUser, db: DbSession
) -> FileOut:
    repo = FileRepository(db)
    record = await repo.get_by_id(file_id)
    if not record:
        raise NotFoundError("文件")
    return FileOut(
        file_id=record.id,
        object_name=record.object_name,
        url=record.url or "",
        name=record.file_name,
        type=record.content_type or "application/octet-stream",
        size=record.size or 0,
        uploaded_at=record.created_at,
    )


@router.get("/{file_id}/url", response_model=FileUrlResponse)
async def get_file_url(
    file_id: str,
    current_user: CurrentUser,
    db: DbSession,
    expires: int = Query(86400, ge=1, le=86400 * 7),
) -> FileUrlResponse:
    repo = FileRepository(db)
    record = await repo.get_by_id(file_id)
    if not record:
        raise NotFoundError("文件")
    url = storage.get_presigned_url(record.object_name, expires)
    return FileUrlResponse(url=url, expires=expires)


@router.delete("/{file_id}")
async def delete_file(
    file_id: str, current_user: CurrentUser, db: DbSession
) -> dict:
    repo = FileRepository(db)
    record = await repo.get_by_id(file_id)
    if not record:
        raise NotFoundError("文件")
    try:
        storage.delete_object(record.object_name)
    except Exception:
        pass  # 存储删失败不影响 DB 记录清理
    await repo.delete(file_id)
    await db.commit()
    return {"status": "deleted", "file_id": file_id}


@router.get("/{file_id}/parse", response_model=FileParseResponse)
async def parse_file(
    file_id: str, current_user: CurrentUser, db: DbSession
) -> FileParseResponse:
    repo = FileRepository(db)
    record = await repo.get_by_id(file_id)
    if not record:
        raise NotFoundError("文件")
    try:
        data = storage.get_data(record.object_name)
    except Exception as e:
        from app.services.storage import StorageUnavailable
        if isinstance(e, StorageUnavailable):
            raise
        raise BadRequestError(f"读取文件失败: {e}")
    ext = os.path.splitext(record.file_name)[1]
    content = document_parser.parse(data, ext)
    return FileParseResponse(
        file_id=record.id,
        file_name=record.file_name,
        content_type=record.content_type or "application/octet-stream",
        content=content[:10000],
    )


@router.get("")
async def list_files(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    repo = FileRepository(db)
    rows = await repo.list_by_user(current_user.id, limit=limit, offset=offset)
    return {
        "files": [
            {
                "file_id": r.id,
                "object_name": r.object_name,
                "url": r.url,
                "name": r.file_name,
                "type": r.content_type,
                "size": r.size,
                "uploaded_at": r.created_at,
            }
            for r in rows
        ],
        "total": len(rows),
    }
