"""投票路由 + 搜索"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import NotFoundError
from app.repositories.chat_repo import ChatRepository
from app.schemas.chat import ChatVoteRequest

router = APIRouter()


@router.post("/messages/{chat_id}/vote")
async def vote(
    chat_id: str,
    body: ChatVoteRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    repo = ChatRepository(db)
    msg = await repo.get_by_id(chat_id)
    if not msg or msg.user_id != current_user.id:
        raise NotFoundError("消息")
    ok = await repo.switch_vote(chat_id, body.vote_type)
    if not ok:
        raise NotFoundError("消息")
    await db.commit()
    return {
        "success": True,
        "chat_id": chat_id,
        "vote_type": body.vote_type,
        "like_count": msg.like_count,
        "dislike_count": msg.dislike_count,
    }


@router.get("/history/search")
async def search_history(
    keyword: str = Query(..., min_length=1, max_length=200),
    current_user: CurrentUser = ...,
    db: DbSession = ...,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    repo = ChatRepository(db)
    rows = await repo.search(keyword, user_id=current_user.id, limit=limit)
    return {
        "results": [
            {
                "id": m.id,
                "question": m.question,
                "answer": m.answer,
                "create_time": m.created_at,
            }
            for m in rows
        ],
        "total": len(rows),
    }
