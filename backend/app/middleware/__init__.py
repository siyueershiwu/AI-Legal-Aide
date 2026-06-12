"""
中间件 - 限流（异步）+ 结构化日志

注：故意不用 starlette.middleware.base.BaseHTTPMiddleware。
该基类在内部用 anyio.create_task_group 流式转发响应体，与
multipart/form-data 大文件上传 / SSE 场景有已知竞态，会把异常包成
ExceptionGroup 抛到 ASGI 顶层（issue: encode/starlette#1438）。
这里改写为纯 ASGI 中间件，规避该问题。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Awaitable, Callable, MutableMapping

from app.db.redis import redis_client

logger = logging.getLogger(__name__)


SKIP_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}


# ---------- 纯 ASGI 工具 ----------
Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
App = Callable[[Scope, Receive, Send], Awaitable[None]]


def _build_json_response(status_code: int, body: dict) -> dict:
    """构造符合 ASGI 规范的 http.response.start / http.response.body"""
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    return {
        "status_code": status_code,
        "headers": [(b"content-type", b"application/json")],
        "body": payload,
    }


# ---------- 限流 ----------
class RateLimitMiddleware:
    """基于 Redis INCR + EXPIRE 的滑动限流（纯 ASGI）"""

    def __init__(self, app: App, max_requests: int = 60, window: int = 60) -> None:
        self.app = app
        self.max_requests = max_requests
        self.window = window

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if path in SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        key = f"ratelimit:{client_ip}"

        try:
            current = await redis_client.incr(key)
            if current == 1:
                await redis_client.expire(key, self.window)
            if current > self.max_requests:
                resp = _build_json_response(
                    429,
                    {"detail": "请求过于频繁，请稍后再试", "retry_after": self.window},
                )
                await send({"type": "http.response.start", "status": resp["status_code"],
                            "headers": resp["headers"]})
                await send({"type": "http.response.body", "body": resp["body"]})
                return
        except Exception as e:
            # 限流是软依赖：失败不阻塞请求
            logger.warning("Rate limit check failed: %s", e)

        await self.app(scope, receive, send)


# ---------- 访问日志 ----------
class LoggingMiddleware:
    """访问日志（纯 ASGI）"""

    def __init__(self, app: App) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.time()
        status_code = 500  # 收不到响应则记 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.time() - start) * 1000, 2)
            client = scope.get("client")
            ip = client[0] if client else "-"
            logger.info(
                "%s %s %d %.2fms ip=%s",
                scope.get("method", "-"),
                scope.get("path", "-"),
                status_code,
                duration_ms,
                ip,
            )
