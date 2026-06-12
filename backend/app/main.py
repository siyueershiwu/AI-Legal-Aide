"""
FastAPI 应用入口
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.middleware import LoggingMiddleware, RateLimitMiddleware
from app.db.redis import redis_client
from app.db.session import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def _check_mysql() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("MySQL 启动检测失败: %s", e)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("应用启动 - 验证依赖连接")
    # MySQL 是必依赖：失败直接抛，让容器重启
    if not await _check_mysql():
        raise RuntimeError("MySQL 不可达，请检查 DATABASE_URL")
    logger.info("MySQL OK")
    # Redis 是软依赖：失败降级（限流/缓存不工作，但 API 可用）
    try:
        await redis_client.ping()
        logger.info("Redis OK")
    except Exception as e:
        logger.warning("Redis 启动检测失败（不影响启动）: %s", e)
    yield
    await redis_client.aclose()
    await engine.dispose()
    logger.info("应用关闭")


app = FastAPI(
    title=settings.APP_NAME,
    description="流式聊天后端 API",
    version="2.0.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

# CORS — 精确方法/头，避免与 allow_credentials=True 配合时 preflight 失败
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# 中间件
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
    window=settings.RATE_LIMIT_WINDOW_SECONDS,
)

# 路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    return {"message": f"{settings.APP_NAME} is running", "version": "2.0.0"}


@app.get("/healthz")
async def healthz() -> JSONResponse:
    redis_ok = False
    try:
        redis_ok = bool(await redis_client.ping())
    except Exception:
        pass
    mysql_ok = await _check_mysql()
    overall = "ok" if (redis_ok and mysql_ok) else "degraded"
    return JSONResponse(
        {
            "status": overall,
            "redis": "up" if redis_ok else "down",
            "mysql": "up" if mysql_ok else "down",
        }
    )
