from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import FileRecord


class FileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        file_id: str,
        object_name: str,
        file_name: str,
        content_type: Optional[str] = None,
        size: Optional[int] = None,
        url: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> FileRecord:
        record = FileRecord(
            id=file_id,
            object_name=object_name,
            file_name=file_name,
            content_type=content_type,
            size=size,
            url=url,
            user_id=user_id,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_by_id(self, file_id: str) -> Optional[FileRecord]:
        return await self.db.get(FileRecord, file_id)

    async def list_by_user(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[FileRecord]:
        stmt = (
            select(FileRecord)
            .where(FileRecord.user_id == user_id)
            .order_by(FileRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_all(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[FileRecord]:
        stmt = (
            select(FileRecord)
            .order_by(FileRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def delete(self, file_id: str) -> bool:
        record = await self.get_by_id(file_id)
        if not record:
            return False
        await self.db.delete(record)
        return True
