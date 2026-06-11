"""会话路由 - 列表 / 详情 / 消息 / 置顶 / 重命名 / 删除 / 清空消息

IDOR 防御统一收敛到 Depends(get_owned_session)，
任何 session_id 路径参数都先过这一关。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.session import ChatSession
from app.repositories.chat_repo import ChatRepository
from app.repositories.session_repo import SessionRepository
from app.schemas.chat import MessageOut
from app.schemas.session import (
    SessionDetail,
    SessionListResponse,
    SessionOut,
    SessionUpdateTitle,
)

router = APIRouter()


# ============== IDOR 防御统一入口 ==============
async def get_owned_session(
    session_id: Annotated[str, Path(...)],
    current_user: CurrentUser,
    db: DbSession,
) -> ChatSession:
    """要求 session 存在且属于当前用户，否则 404（不区分两种情况）"""
    session = await SessionRepository(db).get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        raise NotFoundError("会话")
    return session


OwnedSession = Annotated[ChatSession, Depends(get_owned_session)]


# ============== 路由 ==============
@router.get("", response_model=SessionListResponse)
async def list_sessions(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> SessionListResponse:
    rows, total = await SessionRepository(db).list_by_user_with_count(
        current_user.id, limit=limit, offset=offset
    )
    sessions = [
        SessionOut(
            id=s.id,
            title=s.title,
            pinned=s.pinned,
            message_count=getattr(s, "_message_count", 0),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in rows
    ]
    return SessionListResponse(sessions=sessions, total=total)


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session: OwnedSession,
    db: DbSession,
) -> SessionDetail:
    messages = await ChatRepository(db).list_by_session(session.id)
    msgs_out = []
    for m in messages:
        msgs_out.append(
            MessageOut(id=m.id, role="user", content=m.question, created_at=m.created_at)
        )
        if m.answer:
            msgs_out.append(
                MessageOut(
                    id=f"{m.id}-ai",
                    role="assistant",
                    content=m.answer,
                    created_at=m.created_at,
                )
            )
    return SessionDetail(
        id=session.id,
        title=session.title,
        pinned=session.pinned,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=msgs_out,
    )


@router.delete("/{session_id}")
async def delete_session(
    session: OwnedSession,
    db: DbSession,
) -> dict:
    await SessionRepository(db).delete(session.id)
    await db.commit()
    return {"status": "deleted", "session_id": session.id}


@router.delete("/{session_id}/messages")
async def clear_session_messages(
    session: OwnedSession,
    db: DbSession,
) -> dict:
    count = await ChatRepository(db).clear_session_messages(session.id)
    await db.commit()
    return {"status": "cleared", "session_id": session.id, "deleted": count}


@router.post("/{session_id}/pin")
async def toggle_pin(
    session: OwnedSession,
    db: DbSession,
) -> dict:
    ok = await SessionRepository(db).toggle_pin(session.id)
    if not ok:
        raise NotFoundError("会话")
    await db.commit()
    return {"status": "toggled", "session_id": session.id, "pinned": session.pinned}


@router.put("/{session_id}/title")
async def update_title(
    body: SessionUpdateTitle,
    session: OwnedSession,
    db: DbSession,
) -> dict:
    title = body.title.strip()
    if not title:
        raise BadRequestError("标题不能为空")
    await SessionRepository(db).update_title(session.id, title)
    await db.commit()
    return {"status": "updated", "session_id": session.id, "title": title}
