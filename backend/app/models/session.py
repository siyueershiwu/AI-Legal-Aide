from __future__ import annotations

from typing import List, TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, UpdatedAt, UUIDStrPK

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.chat import ChatMessage


class ChatSession(Base):
    """对话会话"""

    __tablename__ = "sessions"

    id: Mapped[UUIDStrPK]
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    user: Mapped["User"] = relationship(back_populates="sessions")
    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )
