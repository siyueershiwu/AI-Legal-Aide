"""
豆包 AI 服务（Volcengine Ark）- Chat Completions API（OpenAI 兼容）。

端点: POST /api/v3/chat/completions
文档: https://www.volcengine.com/docs/82379/1499107

支持:
- 流式 SSE (stream=True)
- 原生 function call (tools / tool_choice)
- 多模态附件：图片（image_url）+ 文档（text，解析后内联）
- 5xx / 429 自动重试（指数退避）
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.tools import tool_registry

logger = logging.getLogger(__name__)

# 5xx / 429 重试配置
_MAX_RETRIES = 2
_RETRY_BACKOFF = 0.6
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

# RAG 系统提示：法律领域，强制走 kb_search + 防幻觉硬约束
_SYSTEM_PROMPT_RAG = """你是中国法律条文检索问答助手。所有涉及中国法律的问题（包括但不限于：
民法典、刑法、劳动法、劳动合同法、治安管理处罚法、个人信息保护法、网络安全法、数据安全法、
宪法、行政处罚法、民事诉讼法、刑事诉讼法、公司法 等；用户口语化提问如"老板拖欠工资能告吗"
"打人会判几年"也算法律问题）必须遵守以下**硬约束**：

1. **必须**先调用 kb_search 工具检索知识库，再回答。问得明确时 law_code/doc_type 参数尽量填。
2. **仅**基于工具返回的引用块作答。**禁止凭记忆生成法条编号、法条原文、司法解释、
   立法理由、案例编号**——这是绝对红线，违反即视为幻觉。
3. 工具返回硬阻止串（"未检索到对应法律条款"）时，**必须**原样告知用户未命中，
   不得用预训练知识补救，可建议用户去『国家法律法规数据库 flk.npc.gov.cn』查询。
4. 引用法条必须复述工具返回的原文，格式 `《XX法》第N条：「原文」` + `[来源N]`，
   N 与素材块编号对应；不准简写、不准改写。
5. 命中已废止版本（素材标 `已废止`）时，必须显式标注「该条已废止/修订，
   现行版本见 [来源M]」，绝不混用新旧。
6. 涉及具体案件、金额、刑期、期限时，回答末尾**必须**附：
   「本回答仅基于公开法律条文，不构成正式法律意见，建议咨询执业律师。」

非法律问题（数学、翻译、搜索、天气等）正常回答，无需调 kb_search。"""

# 附件 resolver 协议：file_id → 0+ 个 OpenAI content parts
#  - image_url part: {"type": "image_url", "image_url": {"url": ...}}
#  - text part:      {"type": "text", "text": "..."}
# 返回 [] 或抛异常都视为"该附件无内容可发"，跳过即可，不阻断整次请求。
AttachmentResolver = Callable[[str], Awaitable[List[Dict[str, Any]]]]


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

    async def _resolve_attachments(
        self,
        file_ids: List[str],
        attachment_resolver: Optional[AttachmentResolver],
    ) -> List[Dict[str, Any]]:
        """并发把 file_id 解析成多模态 content parts 并拍平。

        - 任何单文件失败（[] / 异常）都跳过
        - 解析器返回的 parts 可能是 text 或 image_url，按 file_ids 顺序拼接
        """
        if not file_ids or attachment_resolver is None:
            return []
        results = await asyncio.gather(
            *(attachment_resolver(fid) for fid in file_ids),
            return_exceptions=True,
        )
        parts: List[Dict[str, Any]] = []
        for fid, res in zip(file_ids, results):
            if isinstance(res, Exception):
                logger.warning("attachment resolve failed (id=%s): %s", fid, res)
                continue
            if isinstance(res, list):
                parts.extend(res)
        return parts

    def _build_messages(
        self,
        message: str,
        history: Optional[List[dict]] = None,
        attachment_parts: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """构造 Chat Completions messages 数组（OpenAI 格式）。

        attachment_parts: 已由 _resolve_attachments 解析好的 content 列表
        （可能混合 image_url 和 text）。当前 user 消息带附件时，content 改为
        数组，**附件在前、用户文本在末尾**。
        历史消息保持 content: str 格式不展开。

        首条固定为 RAG_SYSTEM_PROMPT，强制法律问题走 kb_search。
        """
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": _SYSTEM_PROMPT_RAG},
        ]

        # 历史消息
        if history:
            for h in history:
                role = h.get("role", "user")
                content = h.get("content", "")
                if role in ("user", "assistant", "system"):
                    messages.append({"role": role, "content": content})

        # 当前 user 消息
        if attachment_parts:
            user_content: List[Dict[str, Any]] = list(attachment_parts)
            if message:
                user_content.append({"type": "text", "text": message})
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": message})
        return messages

    async def stream_chat(
        self,
        message: str,
        history: Optional[List[dict]] = None,
        file_ids: Optional[List[str]] = None,
        attachment_resolver: Optional[AttachmentResolver] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        if not self.api_key:
            yield {"type": "error", "message": "DOUBAO_API_KEY 未配置"}
            return

        # 1) 先把 file_id 解析成多模态 parts（在调模型前一次性解析完成）
        # 2) 历史 / 当前消息构造只跟"已解析好的 parts"打交道，不依赖外部服务
        attachment_parts = await self._resolve_attachments(file_ids or [], attachment_resolver)
        # messages 在多轮 tool_calls 循环中可变追加
        messages: List[Dict[str, Any]] = self._build_messages(message, history, attachment_parts)
        tool_schemas = tool_registry.openai_schemas()

        last_err: Optional[str] = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                # ---- 单轮：拿到本轮所有事件 ----
                round_events: List[Dict[str, Any]] = []
                retry_needed = False
                async for evt in self._stream_once(messages, tool_schemas):
                    if evt.get("type") == "_retry":
                        last_err = evt.get("message", "")
                        if attempt < _MAX_RETRIES:
                            backoff = _RETRY_BACKOFF * (2 ** attempt)
                            logger.warning(
                                "Ark 暂态错误，%.1fs 后第 %d 次重试: %s",
                                backoff, attempt + 1, last_err,
                            )
                            await asyncio.sleep(backoff)
                            retry_needed = True
                            break
                        yield {"type": "error", "message": last_err or "Ark 服务不可用"}
                        return
                    round_events.append(evt)
                if retry_needed:
                    continue

                # ---- 找出本轮的工具调用和文本 ----
                assistant_tool_calls: List[Dict[str, Any]] = []
                tool_results: List[Dict[str, Any]] = []

                for evt in round_events:
                    et = evt.get("type")
                    if et == "text":
                        # 文本 delta 直接 yield 给上层
                        yield evt
                    elif et == "tool_call":
                        tool_results.append({
                            "name": evt.get("name", ""),
                            "arguments": evt.get("arguments", {}),
                            "call_id": evt.get("call_id", ""),
                        })
                        # 也 yield 一个 tool_call 事件给上层做日志
                        yield evt
                    elif et == "tool_result":
                        # 把工具结果回填到 messages，供下一轮请求
                        # 查找对应的 tool_call 以补全 arguments
                        tc = next(
                            (t for t in tool_results if t["call_id"] == evt.get("call_id")),
                            None,
                        )
                        tool_results_by_id = {t["call_id"]: t for t in tool_results}
                        call_id = evt.get("call_id", "")
                        if call_id in tool_results_by_id:
                            tool_results_by_id[call_id]["result"] = evt.get("result")
                        yield evt
                        # RAG 特殊: kb_search 的结果反解出 sources 事件，透传给前端做引用展示
                        if tc and tc["name"] == "kb_search":
                            result = evt.get("result") or {}
                            if isinstance(result, dict) and result.get("ok"):
                                from app.services.rag.retriever import parse_sources_from_llm_result
                                sources = parse_sources_from_llm_result(
                                    result.get("result", "")
                                )
                                if sources:
                                    yield {"type": "sources", "sources": sources}

                # ---- 构造 assistant 消息（OpenAI 格式，需要 id/name/arguments 字符串）----
                for t in tool_results:
                    # 工具名 + arguments 字符串形式（与 OpenAI 协议一致）
                    if "result" not in t:
                        t["result"] = {"ok": False, "error": "未取到工具结果"}
                    # 序列化 arguments
                    try:
                        args_str = json.dumps(t["arguments"], ensure_ascii=False)
                    except (TypeError, ValueError):
                        args_str = "{}"
                    assistant_tool_calls.append({
                        "id": t["call_id"],
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "arguments": args_str,
                        },
                    })

                if assistant_tool_calls:
                    # 追加 assistant 消息（含 tool_calls）
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": assistant_tool_calls,
                    })
                    # 追加每个工具的结果
                    for t in tool_results:
                        result_obj = t["result"]
                        # tool message 的 content 必须是字符串
                        if isinstance(result_obj, dict):
                            content_str = (
                                result_obj.get("result", "")
                                if result_obj.get("ok")
                                else f"错误: {result_obj.get('error', '未知')}"
                            )
                        else:
                            content_str = str(result_obj)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": t["call_id"],
                            "content": content_str,
                        })
                    # 继续下一轮 —— 让模型基于工具结果生成自然语言回复
                    continue

                # ---- 无工具调用，本轮就是终态 ----
                yield {"type": "done"}
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
        self,
        messages: List[Dict[str, Any]],
        tool_schemas: List[Dict[str, Any]],
    ) -> AsyncIterator[Dict[str, Any]]:
        """单次 Chat Completions 流式调用。"""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        # 有 tools 时才附加（避免空 tools 导致 400）
        if tool_schemas:
            payload["tools"] = tool_schemas
            payload["tool_choice"] = "auto"

        pending_tool_calls: Dict[int, Dict[str, Any]] = {}

        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json=payload,
            ) as resp:
                if resp.status_code in _RETRYABLE_STATUS:
                    body = await resp.aread()
                    yield {
                        "type": "_retry",
                        "message": f"Ark 返回 {resp.status_code}: {body.decode(errors='ignore')[:200]}",
                    }
                    return
                if resp.status_code != 200:
                    body = await resp.aread()
                    body_text = body.decode(errors='ignore')[:800]
                    logger.error("Ark API %d: %s", resp.status_code, body_text)
                    yield {
                        "type": "error",
                        "message": f"Ark 返回 {resp.status_code}: {body_text}",
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

                    choices = event.get("choices", [])
                    if not choices:
                        continue
                    choice = choices[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    # ---- 文本 delta ----
                    text_delta = delta.get("content", "")
                    if text_delta:
                        yield {"type": "text", "delta": text_delta}

                    # ---- tool_calls delta 累积 ----
                    tc_deltas = delta.get("tool_calls", [])
                    for tc in tc_deltas:
                        idx = tc.get("index", 0)
                        if idx not in pending_tool_calls:
                            pending_tool_calls[idx] = {
                                "id": tc.get("id", ""),
                                "name": "",
                                "arguments": "",
                            }
                        entry = pending_tool_calls[idx]
                        if "id" in tc and tc["id"]:
                            entry["id"] = tc["id"]
                        func = tc.get("function", {})
                        if func.get("name"):
                            entry["name"] += func["name"]
                        if func.get("arguments"):
                            entry["arguments"] += func["arguments"]

                    # ---- finish_reason == "tool_calls"：执行工具 ----
                    if finish_reason == "tool_calls":
                        for entry in pending_tool_calls.values():
                            name = entry["name"]
                            call_id = entry["id"]
                            try:
                                args = (
                                    json.loads(entry["arguments"])
                                    if entry["arguments"]
                                    else {}
                                )
                            except json.JSONDecodeError:
                                args = {}
                            yield {
                                "type": "tool_call",
                                "name": name,
                                "arguments": args,
                                "call_id": call_id,
                            }
                            result = await tool_registry.execute_async(name, args)
                            yield {
                                "type": "tool_result",
                                "name": name,
                                "result": result,
                                "call_id": call_id,
                            }
                        pending_tool_calls.clear()
                        return  # 本轮结束，由 stream_chat 决定是否继续

                    # ---- finish_reason == "stop"：本轮终态 ----
                    if finish_reason == "stop":
                        pending_tool_calls.clear()
                        return


doubao_service = DoubaoService()
