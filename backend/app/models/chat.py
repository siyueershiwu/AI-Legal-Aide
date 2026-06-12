from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, UUIDStrPK

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.session import ChatSession


class ChatMessage(Base):
    """单条对话消息记录（一问一答共一行）"""

    __tablename__ = "chat_history"
    __table_args__ = (
        Index("ix_chat_user_time", "user_id", "created_at"),
        Index("ix_chat_session_time", "session_id", "created_at"),
    )

    id: Mapped[UUIDStrPK]
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dislike_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[CreatedAt]

    user: Mapped["User"] = relationship(back_populates="messages")
    session: Mapped["ChatSession | None"] = relationship(back_populates="messages")
