from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.chat import MessageOut


class SessionCreate(BaseModel):
    title: Optional[str] = None


class SessionUpdateTitle(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class SessionOut(BaseModel):
    id: str
    title: Optional[str] = None
    pinned: bool
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class SessionDetail(BaseModel):
    id: str
    title: Optional[str] = None
    pinned: bool
    created_at: datetime
    updated_at: datetime
    messages: List[MessageOut]


class SessionListResponse(BaseModel):
    sessions: List[SessionOut]
    total: int
