"""法律知识库 Pydantic schemas。"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.knowledge import DOC_TYPE_VALUES, LAW_CODE_VALUES, SOURCE_TYPE_VALUES


class KnowledgeCreateRequest(BaseModel):
    file_id: str
    title: str = Field(..., min_length=1, max_length=255)
    law_code: str
    doc_type: str
    version: str = Field(default="current", max_length=32)
    is_current: bool = True
    effective_date: Optional[date] = None
    repealed_date: Optional[date] = None
    issuing_body: Optional[str] = Field(default=None, max_length=64)
    article_range: Optional[str] = Field(default=None, max_length=64)
    source_type: str = Field(default="upload", max_length=16)


class BatchDeleteRequest(BaseModel):
    ids: List[str] = Field(..., min_length=1, max_length=200)


class KnowledgeDocumentOut(BaseModel):
    id: str
    title: str
    law_code: str
    doc_type: str
    version: str
    is_current: bool
    effective_date: Optional[date] = None
    repealed_date: Optional[date] = None
    issuing_body: Optional[str] = None
    article_range: Optional[str] = None
    source_type: str
    file_id: Optional[str] = None
    chunk_count: int
    char_count: int
    owner_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeDocumentListResponse(BaseModel):
    documents: List[KnowledgeDocumentOut]
    total: int


class KnowledgeStatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    total_characters: int
    by_law_code: dict
    by_doc_type: dict
    current_count: int
    repealed_count: int


class KnowledgeSourceOut(BaseModel):
    title: str
    law_code: str
    doc_type: str
    version: str
    is_current: bool = True
    article_no: Optional[str] = None
    score: float
    snippet: str


class KnowledgePreviewResponse(BaseModel):
    sources: List[KnowledgeSourceOut]


class KnowledgeRebuildResponse(BaseModel):
    success: int
    failed: int
    errors: List[str]


# 元数据枚举（供前端生成下拉选项）
class KnowledgeMetaResponse(BaseModel):
    law_codes: List[str]
    doc_types: List[str]
    source_types: List[str] = list(SOURCE_TYPE_VALUES)


# 取枚举值（启动时导出）
LAW_CODE_OPTIONS = list(LAW_CODE_VALUES)
DOC_TYPE_OPTIONS = list(DOC_TYPE_VALUES)
