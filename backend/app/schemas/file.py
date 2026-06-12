from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    file_id: str
    object_name: str
    url: str
    name: str
    type: str
    size: int
    created_at: datetime


class FileOut(BaseModel):
    file_id: str
    object_name: str
    url: str
    name: str
    type: str
    size: int
    uploaded_at: datetime


class FileUrlResponse(BaseModel):
    url: str
    expires: int


class FileParseResponse(BaseModel):
    file_id: str
    file_name: str
    content_type: str
    content: str  # 文档提取出的纯文本（截断到 10000 字符）
