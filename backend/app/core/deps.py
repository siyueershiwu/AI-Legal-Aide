"""
FastAPI 依赖注入：DB Session / 当前用户 / Redis
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, get_token_from_credentials
from app.core.exceptions import PermissionDeniedError
from app.db.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repo import UserRepository

__all__ = ["get_db", "get_redis", "get_current_user", "DbSession", "RedisDep", "CurrentUser"]


# 类型别名
DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]


async def get_current_user(
    token: Annotated[str, Depends(get_token_from_credentials)],
    db: DbSession,
) -> User:
    """从 JWT 解析 user_id，再查 DB 验证 user 存在并返回 ORM 对象"""
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise PermissionDeniedError("Token 缺少 subject")
    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise PermissionDeniedError("用户不存在或已被删除")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
