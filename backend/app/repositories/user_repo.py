from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        return await self.db.get(User, user_id)

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        user_id: str,
        username: str,
        password_hash: str | None = None,
        email: str | None = None,
    ) -> User:
        user = User(
            id=user_id,
            username=username,
            password_hash=password_hash,
            email=email,
        )
        self.db.add(user)
        # 不需要 refresh：UUID 是 Python 端 default，created_at 由调用方读出
        await self.db.flush()
        return user
