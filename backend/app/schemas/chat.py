from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    """流式对话请求"""

    session_id: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=8000)
    file_ids: List[str] = Field(default_factory=list)


class ChatVoteRequest(BaseModel):
    vote_type: Literal[-1, 0, 1]  # -1=踩, 0=取消, 1=赞


class MessageOut(BaseModel):
    """单条消息（拆开 user/assistant）"""

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
