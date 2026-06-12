from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import ChatSession


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, session_id: str) -> Optional[ChatSession]:
        return await self.db.get(ChatSession, session_id)

    async def list_by_user(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ChatSession]:
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.pinned.desc(), ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def create(
        self,
        *,
        session_id: str,
        user_id: str,
        title: Optional[str] = None,
    ) -> ChatSession:
        if not title:
            title = f"对话 {session_id[:8]}"
        session = ChatSession(id=session_id, user_id=user_id, title=title)
        self.db.add(session)
        await self.db.flush()
        return session

    async def update_title(self, session_id: str, title: str) -> bool:
        stmt = (
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(title=title)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def touch(self, session_id: str) -> None:
        """更新 updated_at 时间戳"""
        await self.db.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(updated_at=func.now())
        )

    async def toggle_pin(self, session_id: str) -> bool:
        session = await self.get_by_id(session_id)
        if not session:
            return False
        session.pinned = not session.pinned
        await self.db.flush()
        return True

    async def delete(self, session_id: str) -> bool:
        session = await self.get_by_id(session_id)
        if not session:
            return False
        await self.db.delete(session)
        return True

    async def list_by_user_with_count(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence["ChatSession"], int]:
        """一次查询拿全部 + 总数 + 每会话消息数（解决 N+1）"""
        from app.models.chat import ChatMessage

        # 1) 拿会话
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.pinned.desc(), ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()

        if not sessions:
            # 顺便拿总数（offset/limit 模式下 total 通常需要）
            total_stmt = select(func.count(ChatSession.id)).where(ChatSession.user_id == user_id)
            total = int((await self.db.execute(total_stmt)).scalar() or 0)
            return sessions, total

        # 2) 一次 group by 拿这些 session 的消息计数
        ids = [s.id for s in sessions]
        count_stmt = (
            select(ChatMessage.session_id, func.count(ChatMessage.id))
            .where(ChatMessage.session_id.in_(ids))
            .group_by(ChatMessage.session_id)
        )
        rows = (await self.db.execute(count_stmt)).all()
        count_map = {sid: int(c) for sid, c in rows}

        # 3) 总数
        total_stmt = select(func.count(ChatSession.id)).where(ChatSession.user_id == user_id)
        total = int((await self.db.execute(total_stmt)).scalar() or 0)

        # 挂在 ORM 对象上（临时属性，不持久化）
        for s in sessions:
            setattr(s, "_message_count", count_map.get(s.id, 0))
        return sessions, total
