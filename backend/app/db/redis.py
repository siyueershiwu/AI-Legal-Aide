"""
异步 Redis 客户端

注意：模块级 redis_client 是在 import 期就建好的连接池，
但底层 httpx / asyncio 都没有 blocking I/O，所以这个开销可接受。
如果需要 mock，把 get_redis 改成工厂函数即可。
"""
from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import settings


def get_redis() -> Redis:
    return Redis.from_url(
        settings.REDIS_URL,
        password=settings.REDIS_PASSWORD or None,
        decode_responses=True,
    )


redis_client = get_redis()
