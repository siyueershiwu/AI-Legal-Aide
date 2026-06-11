"""聊天路由 - SSE 流式对话 + 原生 function call。

落库 / Redis 缓存写入由 BackgroundTask 在响应结束后用独立 session 执行，
不依赖请求作用域的 AsyncSession（避免 StreamingResponse 关闭后 session 已失效）。
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from starlette.background import BackgroundTask

from app.core.deps import CurrentUser, DbSession, RedisDep
from app.core.exceptions import BadRequestError
from app.db.session import AsyncSessionLocal
from app.repositories.chat_repo import ChatRepository
from app.repositories.session_repo import SessionRepository
from app.schemas.chat import ChatStreamRequest
from app.services.doubao import doubao_service
from app.services.redis_cache import RedisCache

logger = logging.getLogger(__name__)

router = APIRouter()


def _sse(payload: dict) -> str:
    """SSE 事件序列化。统一入口，方便后续加心跳 / event name。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _persist_chat_and_cache(
    *,
    chat_id: str,
    session_id: str,
    user_message: str,
    final_answer: str,
    error_msg: str | None,
    redis: Redis,
) -> None:
    """BackgroundTask 入口：落库 + 缓存写入 + 清理流式状态。

    使用独立 AsyncSessionLocal()（不依赖请求作用域 session），
    因为 StreamingResponse 一旦 yield 第一个事件，请求级 Depends(get_db)
    的 async with 可能已经退出。
    """
    # DB 落库
    try:
        async with AsyncSessionLocal() as db:
            chat_repo = ChatRepository(db)
            await chat_repo.update_answer(chat_id, final_answer)
            srepo = SessionRepository(db)
            await srepo.touch(session_id)
            await db.commit()
    except Exception:
        logger.exception("Failed to persist chat answer (chat_id=%s)", chat_id)

    # Redis 缓存写入 + 流式状态清理
    cache = RedisCache(redis)
    try:
        cached = await cache.get_cached_chat(session_id) or []
        cached.append({"role": "user", "content": user_message})
        cached.append({"role": "assistant", "content": final_answer})
        await cache.cache_chat(session_id, cached)
    except Exception:
        logger.exception("Cache chat failed (session_id=%s)", session_id)
    finally:
        try:
            await cache.release_streaming(session_id)
            await cache.clear_stop_flag(session_id)
        except Exception:
            logger.exception("Clear streaming flags failed (session_id=%s)", session_id)


@router.post("/stream")
async def chat_stream(
    req: ChatStreamRequest,
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisDep,
):
    if not req.message and not req.file_ids:
        raise BadRequestError("消息内容不能为空")

    session_id = req.session_id or str(uuid.uuid4())
    user_id = current_user.id
    cache = RedisCache(redis)

    # ===== 防重 =====
    is_dup = await cache.check_and_mark_duplicate(user_id, req.message)
    if is_dup:
        async def _dup() -> AsyncIterator[str]:
            yield _sse({"content": "请勿重复提问相同问题", "done": True})
        return StreamingResponse(_dup(), media_type="text/event-stream")

    # ===== 并发防炸（先原子占位）=====
    chat_id = str(uuid.uuid4())
    acquired = await cache.acquire_streaming(session_id, chat_id)
    if not acquired:
        async def _busy() -> AsyncIterator[str]:
            yield _sse({"content": "请等待当前回复完成", "done": True})
        return StreamingResponse(_busy(), media_type="text/event-stream")

    # ===== DB 准备（失败要回滚 streaming 标记）=====
    try:
        srepo = SessionRepository(db)
        session = await srepo.get_by_id(session_id)
        if not session:
            title = req.message[:20] + ("..." if len(req.message) > 20 else "")
            await srepo.create(session_id=session_id, user_id=user_id, title=title)
            await db.commit()

        chat_repo = ChatRepository(db)
        await chat_repo.create(
            chat_id=chat_id,
            user_id=user_id,
            question=req.message,
            answer="",
            session_id=session_id,
        )
        await db.commit()
    except Exception:
        # DB 失败 → 释放 streaming 标记（让用户能重试），并把已占的 dedup 标记一起清掉
        await cache.release_streaming(session_id)
        await cache.release_duplicate(user_id, req.message)
        raise

    # ===== 拿历史 + 调模型 =====
    history = await cache.get_cached_chat(session_id)
    image_ids = req.file_ids or []

    # 闭包：BackgroundTask 读取（生成器在流式结束时 mutate）
    state: dict = {"final_answer": "", "error_msg": None}

    async def event_gen() -> AsyncIterator[str]:
        full_content = ""
        tool_results_text = ""
        error_msg: str | None = None

        try:
            async for event in doubao_service.stream_chat(
                message=req.message, history=history, image_ids=image_ids
            ):
                ev_type = event.get("type")

                if ev_type == "text":
                    delta = event.get("delta", "")
                    if not delta:
                        continue
                    full_content += delta
                    yield _sse({"content": delta, "done": False})

                elif ev_type == "tool_call":
                    name = event.get("name", "")
                    yield _sse({"event": "tool_call", "name": name})

                elif ev_type == "tool_result":
                    name = event.get("name", "")
                    result = event.get("result", {})
                    result_text = (
                        result.get("result", "") if isinstance(result, dict) else str(result)
                    )
                    tool_results_text += f"\n\n[{name}] {result_text}"
                    yield _sse({"content": f"\n\n[{name}] {result_text}", "done": False})

                elif ev_type == "done":
                    break

                elif ev_type == "error":
                    error_msg = event.get("message", "未知错误")
                    break

                # 停止标记
                if await cache.is_stopped(session_id):
                    logger.info("Stream stopped by user: %s", session_id)
                    await cache.clear_stop_flag(session_id)
                    break
        except Exception:
            logger.exception("event_generator error (session_id=%s)", session_id)
            error_msg = "AI 服务错误"
            # 异常路径立即释放 streaming 锁（不等 background task 走完）
            await cache.release_streaming(session_id)

        final_answer = full_content + tool_results_text
        if error_msg and not final_answer:
            final_answer = error_msg
        state["final_answer"] = final_answer
        state["error_msg"] = error_msg

        yield _sse({"content": "", "done": True, "error": error_msg})

    async def on_complete() -> None:
        await _persist_chat_and_cache(
            chat_id=chat_id,
            session_id=session_id,
            user_message=req.message,
            final_answer=state["final_answer"],
            error_msg=state["error_msg"],
            redis=redis,
        )

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        background=BackgroundTask(on_complete),
    )


@router.post("/stop/{session_id}")
async def stop_chat(session_id: str, redis: RedisDep) -> dict:
    cache = RedisCache(redis)
    await cache.set_stop_flag(session_id)
    return {"status": "stopping", "session_id": session_id}
