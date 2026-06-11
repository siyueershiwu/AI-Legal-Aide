"""
豆包 AI 服务（Volcengine Ark 3.0）- 完整迁移到原生 function call。

API 文档：https://www.volcengine.com/docs/82379/1399567

主要变化 vs 旧实现：
- 同步 requests -> httpx.AsyncClient
- prompt 贴标签的伪 function call -> Ark 原生 tools / tool_choice
- 同步 time.sleep -> asyncio.sleep
- 5xx / 429 自动重试（指数退避）
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.tools import tool_registry

logger = logging.getLogger(__name__)

# 5xx / 429 重试配置
_MAX_RETRIES = 2
_RETRY_BACKOFF = 0.6  # 第一次等 0.6s，第二次 1.2s
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class DoubaoService:
    def __init__(self) -> None:
        self.base_url = settings.DOUBAO_BASE_URL.rstrip("/")
        self.model = settings.DOUBAO_MODEL
        self.api_key = settings.DOUBAO_API_KEY

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _wait_for_file_ready(self, file_id: str, timeout: int = 30) -> bool:
        """异步轮询文件状态，active 后多等几秒确保可读"""
        deadline = asyncio.get_event_loop().time() + timeout
        async with httpx.AsyncClient(timeout=10) as client:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await client.get(
                        f"{self.base_url}/files/{file_id}", headers=self._headers
                    )
                    if r.status_code == 200:
                        if r.json().get("status") == "active":
                            await asyncio.sleep(5)
                            return True
                except Exception as e:
                    logger.warning("wait_for_file_ready error: %s", e)
                await asyncio.sleep(2)
        return False

    def _build_input(
        self,
        message: str,
        history: Optional[List[dict]] = None,
        image_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """构造 Ark 3.0 input 数组"""
        items: List[Dict[str, Any]] = []
        if history:
            for h in history:
                role = h.get("role", "user")
                content = h.get("content", "")
                if role == "user":
                    parts: List[Dict[str, Any]] = []
                    if image_ids and h is history[-1]:
                        for fid in image_ids:
                            parts.append({"type": "input_image", "file_id": fid})
                    parts.append({"type": "input_text", "text": content})
                    items.append({"role": "user", "content": parts})
                else:
                    items.append({"role": "assistant", "content": content})
        else:
            parts = []
            if image_ids:
                for fid in image_ids:
                    parts.append({"type": "input_image", "file_id": fid})
            parts.append({"type": "input_text", "text": message})
            items.append({"role": "user", "content": parts})
        return items

    async def stream_chat(
        self,
        message: str,
        history: Optional[List[dict]] = None,
        image_ids: Optional[List[str]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        if not self.api_key:
            yield {"type": "error", "message": "DOUBAO_API_KEY 未配置"}
            return

        if image_ids:
            for fid in image_ids:
                await self._wait_for_file_ready(fid)

        payload: Dict[str, Any] = {
            "model": self.model,
            "input": self._build_input(message, history, image_ids),
            "stream": True,
            "tools": tool_registry.openai_schemas(),
            "tool_choice": "auto",
        }

        last_err: Optional[str] = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async for evt in self._stream_once(payload):
                    # 仅在响应头阶段才决定要不要重试；流已经开始就把 done/error 透传
                    if evt.get("type") == "_retry":
                        last_err = evt.get("message", "")
                        if attempt < _MAX_RETRIES:
                            backoff = _RETRY_BACKOFF * (2 ** attempt)
                            logger.warning(
                                "Ark 暂态错误，%.1fs 后第 %d 次重试: %s",
                                backoff, attempt + 1, last_err,
                            )
                            await asyncio.sleep(backoff)
                            break  # 跳出内层 for，重试
                        else:
                            yield {"type": "error", "message": last_err or "Ark 服务不可用"}
                            return
                    else:
                        yield evt
                        if evt.get("type") in ("done", "error"):
                            return
                else:
                    # async for 正常结束
                    return
            except httpx.HTTPError as e:
                last_err = f"网络错误: {e}"
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_BACKOFF * (2 ** attempt))
                    continue
                yield {"type": "error", "message": last_err}
                return
            except Exception as e:
                logger.exception("Doubao stream_chat error")
                yield {"type": "error", "message": f"内部错误: {e}"}
                return

    async def _stream_once(
        self, payload: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """单次 Ark 调用：返回 stream 内的事件 + 可重试哨兵 {_retry: ...}"""
        pending_tool_calls: Dict[str, Dict[str, Any]] = {}
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/responses",
                headers=self._headers,
                json=payload,
            ) as resp:
                if resp.status_code in _RETRYABLE_STATUS:
                    body = await resp.aread()
                    yield {
                        "_retry": True,
                        "message": f"Ark 返回 {resp.status_code}: {body.decode(errors='ignore')[:200]}",
                    }
                    return
                if resp.status_code != 200:
                    body = await resp.aread()
                    yield {
                        "type": "error",
                        "message": f"Ark 返回 {resp.status_code}: {body.decode(errors='ignore')[:500]}",
                    }
                    return

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload_str = line[5:].strip()
                    if payload_str == "[DONE]" or not payload_str:
                        continue
                    try:
                        event = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue
                    ev_type = event.get("type", "")

                    if ev_type == "response.output_text.delta":
                        delta = event.get("delta", "")
                        if delta:
                            yield {"type": "text", "delta": delta}

                    elif ev_type == "response.output_item.added":
                        item = event.get("item", {})
                        if item.get("type") == "function_call":
                            call_id = item.get("call_id") or item.get("id", "")
                            pending_tool_calls[call_id] = {
                                "name": item.get("name", ""),
                                "arguments": "",
                            }

                    elif ev_type == "response.function_call_arguments.delta":
                        call_id = event.get("call_id", "")
                        delta = event.get("delta", "")
                        if call_id in pending_tool_calls:
                            pending_tool_calls[call_id]["arguments"] += delta

                    elif ev_type == "response.function_call_arguments.done":
                        call_id = event.get("call_id", "")
                        arguments_str = event.get("arguments", "")
                        if call_id in pending_tool_calls:
                            pending_tool_calls[call_id]["arguments"] = arguments_str

                    elif ev_type == "response.completed":
                        for call_id, call in pending_tool_calls.items():
                            try:
                                args = (
                                    json.loads(call["arguments"])
                                    if call["arguments"]
                                    else {}
                                )
                            except json.JSONDecodeError:
                                args = {}
                            name = call["name"]
                            yield {
                                "type": "tool_call",
                                "name": name,
                                "arguments": args,
                                "call_id": call_id,
                            }
                            result = tool_registry.execute(name, args)
                            yield {
                                "type": "tool_result",
                                "name": name,
                                "result": result,
                                "call_id": call_id,
                            }
                        pending_tool_calls.clear()
                        yield {"type": "done"}
                        return


doubao_service = DoubaoService()

