from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage


class ChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        chat_id: str,
        user_id: str,
        question: str,
        session_id: Optional[str] = None,
        answer: str = "",
    ) -> ChatMessage:
        msg = ChatMessage(
            id=chat_id,
            user_id=user_id,
            session_id=session_id,
            question=question,
            answer=answer,
        )
        self.db.add(msg)
        # id 是 Python 端 default；created_at 由 SQL server_default 生成，
        # 若调用方需要，单独 select 或读 chat_repo.get_by_id(chat_id) 也可
        await self.db.flush()
        return msg

    async def update_answer(self, chat_id: str, answer: str) -> bool:
        stmt = (
            update(ChatMessage)
            .where(ChatMessage.id == chat_id)
            .values(answer=answer)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def list_by_session(self, session_id: str) -> Sequence[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_by_user(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, chat_id: str) -> Optional[ChatMessage]:
        return await self.db.get(ChatMessage, chat_id)

    async def delete(self, chat_id: str) -> bool:
        msg = await self.get_by_id(chat_id)
        if not msg:
            return False
        await self.db.delete(msg)
        return True

    async def clear_session_messages(self, session_id: str) -> int:
        stmt = delete(ChatMessage).where(ChatMessage.session_id == session_id)
        result = await self.db.execute(stmt)
        return result.rowcount

    async def add_vote(self, chat_id: str, delta: int) -> bool:
        """delta ∈ {-1, 1}（增/减）"""
        if delta not in (-1, 1):
            return False
        column = ChatMessage.like_count if delta == 1 else ChatMessage.dislike_count
        # 行级锁 + 不会跌破 0
        stmt = (
            update(ChatMessage)
            .where(ChatMessage.id == chat_id, column > 0)
            .values(**{column.name: column + delta})
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def switch_vote(self, chat_id: str, target: int) -> bool:
        """直接置为 target ∈ {0, 1, -1}（覆盖式投票，前端不再担心状态机）"""
        if target not in (-1, 0, 1):
            return False
        stmt = (
            update(ChatMessage)
            .where(ChatMessage.id == chat_id)
            .values(like_count=1 if target == 1 else 0, dislike_count=1 if target == -1 else 0)
        )
        result = await self.db.execute(stmt)
        return result.rowcount > 0

    async def search(
        self,
        keyword: str,
        user_id: Optional[str] = None,
        limit: int = 50,
    ) -> Sequence[ChatMessage]:
        pattern = f"%{keyword}%"
        conditions = [or_(ChatMessage.question.like(pattern), ChatMessage.answer.like(pattern))]
        if user_id:
            conditions.append(ChatMessage.user_id == user_id)
        stmt = (
            select(ChatMessage)
            .where(*conditions)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
