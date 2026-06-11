from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAt, UUIDStrPK

if TYPE_CHECKING:
    from app.models.user import User


class FileRecord(Base):
    """文件元数据（MinIO 对象存储的引用）"""

    __tablename__ = "files"
    __table_args__ = (Index("ix_files_object_name", "object_name"),)

    id: Mapped[UUIDStrPK]
    object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[CreatedAt]

    user: Mapped["User | None"] = relationship(back_populates="files")
