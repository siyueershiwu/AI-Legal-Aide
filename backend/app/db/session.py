"""
异步 SQLAlchemy 引擎 + Session 工厂
"""
from __future__ import annotations

from typing import Any, AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _build_engine_kwargs() -> dict[str, Any]:
    """按 dialect 适配 engine 参数。

    SQLite (CI 测试用 sqlite+aiosqlite) 不支持 pool_size/max_overflow/pool_recycle，
    SA 会自动落到 StaticPool；硬传这些参数会报：
      TypeError: Invalid argument(s) 'pool_size','max_overflow' sent to create_engine()
    """
    url = settings.DATABASE_URL
    kw: dict[str, Any] = {
        "echo": settings.DATABASE_ECHO,
        "pool_pre_ping": True,
        "future": True,
    }
    if url.startswith("sqlite"):
        return kw
    # MySQL / Postgres：连接池参数才生效
    kw.update(
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        # 30 分钟强制回收连接：MySQL 默认 wait_timeout=28800s，但云上 / 容器
        # 经常配 60-300s 的 NAT 空闲超时；不回收客户端会拿到已 RST 的连接。
        pool_recycle=1800,
    )
    return kw


engine = create_async_engine(settings.DATABASE_URL, **_build_engine_kwargs())

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每个请求一个 session，请求结束自动关闭"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
