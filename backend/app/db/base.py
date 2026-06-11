"""
SQLAlchemy 2.0 declarative base
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 通用列类型
UUIDStrPK = Annotated[
    str,
    mapped_column(CHAR(36), primary_key=True, default=lambda: str(uuid4())),
]
CreatedAt = Annotated[
    datetime,
    mapped_column(DateTime, server_default=func.now(), nullable=False),
]
UpdatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    ),
]


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 声明基类"""

    pass
