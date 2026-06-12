"""
测试 DoubaoService.stream_chat 的工具调用循环。

模拟 Ark 返回两次 SSE 响应:
- 第一次: finish_reason=tool_calls
- 第二次: finish_reason=stop (自然语言回复)

期望: 第二次响应的文本 delta 被正确 yield 给上层,而不是被截断。
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.doubao import DoubaoService
from app.services.tools import tool_registry


def _sse_chunk(payload: Dict[str, Any]) -> bytes:
    """模拟 Ark 返回的 SSE chunk（按 aiter_lines 行为，行首有 'data:'）"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _text_delta(content: str) -> Dict[str, Any]:
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion.chunk",
        "choices": [{
            "index": 0,
            "delta": {"content": content, "role": "assistant"},
            "finish_reason": None,
        }],
    }


def _tool_call_delta(name: str = "calculator", call_id: str = "call_1", args: str = "") -> Dict[str, Any]:
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion.chunk",
        "choices": [{
            "index": 0,
            "delta": {
                "role": "assistant",
                "tool_calls": [{
                    "index": 0,
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": args},
                }],
            },
            "finish_reason": None,
        }],
    }


def _finish(reason: str) -> Dict[str, Any]:
    return {
        "id": "chatcmpl-x",
        "object": "chat.completion.chunk",
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": reason,
        }],
    }


class _FakeAsyncByteStream:
    """模拟 httpx 的字节流，按 aiter_lines 行为按行产出。"""

    def __init__(self, chunks: List[bytes]) -> None:
        # 把所有 chunks 拼成一个 buffer，aiter_lines 才会按 \n 切
        self._buffer = b"".join(chunks)

    async def __aenter__(self) -> "_FakeAsyncByteStream":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._buffer.split(b"\n"):
            yield line.decode("utf-8").rstrip("\r")


class _FakeResponse:
    def __init__(self, status_code: int, body: bytes) -> None:
        self.status_code = status_code
        self._body = body
        self._stream = _FakeAsyncByteStream(self._split_sse(body))

    def _split_sse(self, body: bytes) -> List[bytes]:
        # 直接按 aiter_lines 期望的 \n 切行
        return [line + b"\n" for line in body.split(b"\n") if line]

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    @property
    def aiter_lines(self):
        return self._stream.aiter_lines

    async def aread(self) -> bytes:
        return self._body


def _build_response_body(chunks: List[Dict[str, Any]]) -> bytes:
    """把 dict 列表拼成 SSE body。"""
    return b"".join(_sse_chunk(c) for c in chunks)


@pytest.mark.asyncio
async def test_stream_chat_two_round_tool_call(monkeypatch):
    """
    Round 1: model returns tool_calls (no text), finish_reason=tool_calls
    Round 2: model streams natural language, finish_reason=stop

    Expectation: 第二次的文本 delta 全部被 yield,而不是 truncate 在 done 之后。
    """
    service = DoubaoService()
    # 绕开真实 key 校验
    monkeypatch.setattr(service, "api_key", "test-key")
    # 强制使用 calculator（已注册且同步安全）
    assert tool_registry.get("calculator") is not None

    # Round 1: 一次工具调用 calculator，参数 {"expression": "2+3*4"}
    round1_chunks = [
        _tool_call_delta(name="calculator", call_id="call_abc", args='{"expression": "2+3*4"}'),
        _finish("tool_calls"),
    ]
    # Round 2: 纯文本回复
    round2_chunks = [
        _text_delta("计算结果"),
        _text_delta("是 14"),
        _finish("stop"),
    ]

    body1 = _build_response_body(round1_chunks)
    body2 = _build_response_body(round2_chunks)

    call_count = {"n": 0}

    def make_stream(_payload: Dict[str, Any]):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _FakeResponse(200, body1)
        return _FakeResponse(200, body2)

    class _FakeClient:
        def __init__(self, *a: Any, **kw: Any) -> None:
            pass

        async def __aenter__(self) -> "_FakeClient":
            return self

        async def __aexit__(self, *exc: Any) -> None:
            return None

        def stream(self, _method: str, _url: str, **_kw: Any) -> Any:
            return make_stream(_kw.get("json", {}))

    monkeypatch.setattr("app.services.doubao.httpx.AsyncClient", _FakeClient)

    # 收集所有事件
    events: List[Dict[str, Any]] = []
    async for evt in service.stream_chat(message="2+3*4 等于多少", history=None, file_ids=None):
        events.append(evt)

    # 断言：调用了 Ark 两次
    assert call_count["n"] == 2, f"应该发两次请求，实际 {call_count['n']}"

    # 断言：文本 delta 来自第二轮
    text_events = [e for e in events if e.get("type") == "text"]
    assert len(text_events) == 2
    assert text_events[0]["delta"] == "计算结果"
    assert text_events[1]["delta"] == "是 14"

    # 断言：tool_call 和 tool_result 都触发了
    tool_call_events = [e for e in events if e.get("type") == "tool_call"]
    tool_result_events = [e for e in events if e.get("type") == "tool_result"]
    assert len(tool_call_events) == 1
    assert tool_call_events[0]["name"] == "calculator"
    assert tool_call_events[0]["arguments"] == {"expression": "2+3*4"}
    assert len(tool_result_events) == 1
    # calculator 工具的返回值
    assert "14" in str(tool_result_events[0]["result"])

    # 断言：最后是 done
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_chat_no_tool_call(monkeypatch):
    """
    正常路径：不调工具,直接 finish_reason=stop。
    确认改动没破坏原有流程。
    """
    service = DoubaoService()
    monkeypatch.setattr(service, "api_key", "test-key")

    chunks = [
        _text_delta("你好"),
        _text_delta("！"),
        _finish("stop"),
    ]
    body = _build_response_body(chunks)

    class _FakeClient:
        def __init__(self, *a: Any, **kw: Any) -> None: pass
        async def __aenter__(self): return self
        async def __aexit__(self, *exc): return None
        def stream(self, *a, **kw):
            return _FakeResponse(200, body)

    monkeypatch.setattr("app.services.doubao.httpx.AsyncClient", _FakeClient)

    events = []
    async for evt in service.stream_chat(message="hi", history=None, file_ids=None):
        events.append(evt)

    text_events = [e for e in events if e.get("type") == "text"]
    assert text_events == [{"type": "text", "delta": "你好"}, {"type": "text", "delta": "！"}]
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_chat_retry_then_success(monkeypatch):
    """
    Ark 第一次 503 -> 第二次 200，retry 应当成功。
    """
    service = DoubaoService()
    monkeypatch.setattr(service, "api_key", "test-key")
    monkeypatch.setattr("app.services.doubao.asyncio.sleep", AsyncMock())  # 加速重试

    attempt = {"n": 0}

    class _FakeClient:
        def __init__(self, *a: Any, **kw: Any) -> None: pass
        async def __aenter__(self): return self
        async def __aexit__(self, *exc): return None
        def stream(self, *a, **kw):
            attempt["n"] += 1
            if attempt["n"] == 1:
                return _FakeResponse(503, b"")
            body = _build_response_body([_text_delta("ok"), _finish("stop")])
            return _FakeResponse(200, body)

    monkeypatch.setattr("app.services.doubao.httpx.AsyncClient", _FakeClient)

    events = []
    async for evt in service.stream_chat(message="hi", history=None, file_ids=None):
        events.append(evt)

    assert attempt["n"] == 2
    assert any(e.get("type") == "text" and e["delta"] == "ok" for e in events)
    assert events[-1]["type"] == "done"
