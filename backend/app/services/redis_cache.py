"""
异步 Redis 缓存服务 - 队列 / 缓存 / 防重 / 流式状态

设计要点：
- streaming 占用用 Lua 脚本原子地 check + set（避免两个请求都看到空闲）
- 缓存截断按"最近 N 轮对话"，不丢上下文（业务层负责总结）
- 防重标记在异常时能被释放（release_duplicate）
"""
from __future__ import annotations

import hashlib
import json
from typing import List, Optional

from fastapi import Depends
from redis.asyncio import Redis

from app.core.deps import RedisDep


class RedisCache:
    PREFIX_CHAT_CACHE = "chat:cache:"
    PREFIX_DEDUP = "chat:dedup:"
    PREFIX_STREAMING = "chat:streaming:"
    PREFIX_STOP = "chat:stop:"

    CHAT_CACHE_TTL = 3600 * 24
    DEDUP_TTL = 300
    STREAMING_TTL = 600

    def __init__(self, redis: Redis):
        self.redis = redis

    # ===== 对话缓存 =====
    async def cache_chat(self, session_id: str, messages: List[dict]) -> None:
        # 注：截断策略由调用方负责（按业务/Token 预算），这里只存
        data = json.dumps(messages, ensure_ascii=False)
        await self.redis.set(
            f"{self.PREFIX_CHAT_CACHE}{session_id}", data, ex=self.CHAT_CACHE_TTL
        )

    async def get_cached_chat(self, session_id: str) -> Optional[List[dict]]:
        data = await self.redis.get(f"{self.PREFIX_CHAT_CACHE}{session_id}")
        if not data:
            return None
        return json.loads(data)

    async def clear_chat_cache(self, session_id: Optional[str] = None) -> int:
        if session_id:
            await self.redis.delete(f"{self.PREFIX_CHAT_CACHE}{session_id}")
            return 1
        keys = await self.redis.keys(f"{self.PREFIX_CHAT_CACHE}*")
        if keys:
            await self.redis.delete(*keys)
            return len(keys)
        return 0

    # ===== 防重（用 SETNX 保证原子）=====
    @staticmethod
    def _fingerprint(user_id: str, message: str) -> str:
        return hashlib.md5(f"{user_id}:{message}".encode()).hexdigest()

    async def check_and_mark_duplicate(self, user_id: str, message: str) -> bool:
        """True = 重复（已存在），False = 新消息（已标记）"""
        key = f"{self.PREFIX_DEDUP}{self._fingerprint(user_id, message)}"
        ok = await self.redis.set(key, "1", ex=self.DEDUP_TTL, nx=True)
        return not bool(ok)

    async def release_duplicate(self, user_id: str, message: str) -> None:
        """DB 失败时回滚防重，让用户能重试"""
        key = f"{self.PREFIX_DEDUP}{self._fingerprint(user_id, message)}"
        await self.redis.delete(key)

    # ===== 流式状态（原子获取/释放）=====
    # Lua: 抢 streaming 锁。返回 1 = 抢到，0 = 已被占
    _ACQUIRE_LUA = """
    if redis.call('EXISTS', KEYS[1]) == 1 then
      return 0
    else
      redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
      return 1
    end
    """

    async def acquire_streaming(self, session_id: str, chat_id: str) -> bool:
        key = f"{self.PREFIX_STREAMING}{session_id}"
        result = await self.redis.eval(
            self._ACQUIRE_LUA, 1, key, chat_id, str(self.STREAMING_TTL)
        )
        return int(result) == 1

    async def release_streaming(self, session_id: str) -> None:
        await self.redis.delete(f"{self.PREFIX_STREAMING}{session_id}")

    async def is_streaming(self, session_id: str) -> Optional[str]:
        return await self.redis.get(f"{self.PREFIX_STREAMING}{session_id}")

    # ===== 停止标记 =====
    async def set_stop_flag(self, session_id: str) -> None:
        await self.redis.set(
            f"{self.PREFIX_STOP}{session_id}", "1", ex=self.STREAMING_TTL
        )

    async def is_stopped(self, session_id: str) -> bool:
        return await self.redis.get(f"{self.PREFIX_STOP}{session_id}") == "1"

    async def clear_stop_flag(self, session_id: str) -> None:
        await self.redis.delete(f"{self.PREFIX_STOP}{session_id}")

    # ===== 监控 =====
    async def get_stats(self) -> dict:
        info = await self.redis.info()
        return {
            "connected": True,
            "used_memory": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
        }


def get_redis_cache(redis: RedisDep) -> RedisCache:
    return RedisCache(redis)


RedisCacheDep = Depends(get_redis_cache)
