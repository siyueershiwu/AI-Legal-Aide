"""
测试 DoubaoService 的多模态附件解析 + messages 构造路径。

覆盖：
- _resolve_attachments：并发、失败跳过、空输入
- _build_messages：纯文本 / image_url / text / 混合 / 无文本 / 历史兼容
- stream_chat 端到端：mock httpx 校验发给 Ark 的 messages 结构
- services.attachments：image / txt / pdf / docx / 不支持类型 / 截断
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

from app.services.doubao import DoubaoService
from tests.test_doubao_tool_loop import (
    _FakeAsyncByteStream,
    _FakeResponse,
    _build_response_body,
    _finish,
    _text_delta,
)


# ============================================================================
# _resolve_attachments
# ============================================================================
@pytest.mark.asyncio
async def test_resolve_attachments_with_none_resolver_returns_empty():
    """attachment_resolver=None → []，兼容旧调用方（file_ids=None）。"""
    svc = DoubaoService()
    parts = await svc._resolve_attachments(["f1", "f2"], attachment_resolver=None)
    assert parts == []


@pytest.mark.asyncio
async def test_resolve_attachments_concat_parts_in_order():
    """多文件 parts 按 file_ids 顺序拼接。"""

    async def resolver(fid: str) -> List[Dict[str, Any]]:
        if fid.startswith("img"):
            return [{"type": "image_url", "image_url": {"url": f"data:..;base64,{fid}"}}]
        return [{"type": "text", "text": f"[{fid}]"}]

    svc = DoubaoService()
    parts = await svc._resolve_attachments(
        ["doc1", "img-1", "doc2", "img-2"], attachment_resolver=resolver
    )
    assert parts == [
        {"type": "text", "text": "[doc1]"},
        {"type": "image_url", "image_url": {"url": "data:..;base64,img-1"}},
        {"type": "text", "text": "[doc2]"},
        {"type": "image_url", "image_url": {"url": "data:..;base64,img-2"}},
    ]


@pytest.mark.asyncio
async def test_resolve_attachments_skips_empty_list_and_exceptions():
    """resolver 返回 [] 或抛异常 → 该附件跳过，不阻断整次请求。"""

    async def flaky_resolver(fid: str) -> List[Dict[str, Any]]:
        if fid == "empty":
            return []
        if fid == "boom":
            raise RuntimeError("storage down")
        return [{"type": "text", "text": fid}]

    svc = DoubaoService()
    parts = await svc._resolve_attachments(
        ["ok1", "empty", "boom", "ok2"], attachment_resolver=flaky_resolver
    )
    assert parts == [
        {"type": "text", "text": "ok1"},
        {"type": "text", "text": "ok2"},
    ]


@pytest.mark.asyncio
async def test_resolve_attachments_empty_ids():
    """空列表 / None → []。"""
    svc = DoubaoService()
    assert await svc._resolve_attachments([], attachment_resolver=None) == []
    assert await svc._resolve_attachments([], lambda f: [{"type": "text", "text": "x"}]) == []


# ============================================================================
# _build_messages
# ============================================================================
def test_build_messages_text_only_backward_compat():
    """无附件 → 沿用旧格式 content: str（首条固定为 RAG system prompt）。"""
    svc = DoubaoService()
    msgs = svc._build_messages("hello", history=None, attachment_parts=None)
    assert msgs[0]["role"] == "system"
    assert "kb_search" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "hello"}


def test_build_messages_with_image_url_only():
    """只有图片 → 多模态数组（首条为 RAG system prompt）。"""
    svc = DoubaoService()
    parts = [{"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}}]
    msgs = svc._build_messages("看这张", history=None, attachment_parts=parts)
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}},
            {"type": "text", "text": "看这张"},
        ],
    }


def test_build_messages_with_text_attachment():
    """文档解析后作为 text part（首条为 RAG system prompt）。"""
    svc = DoubaoService()
    parts = [{"type": "text", "text": "[附件: report.pdf]\n这是正文"}]
    msgs = svc._build_messages("总结一下", history=None, attachment_parts=parts)
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {
        "role": "user",
        "content": [
            {"type": "text", "text": "[附件: report.pdf]\n这是正文"},
            {"type": "text", "text": "总结一下"},
        ],
    }


def test_build_messages_mixed_doc_and_image_in_order():
    """文档 + 图片混合：附件在前、用户文本在末尾（首条为 RAG system prompt）。"""
    svc = DoubaoService()
    parts = [
        {"type": "text", "text": "[附件: a.txt]\nAAA"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,X"}},
    ]
    msgs = svc._build_messages("对比", history=None, attachment_parts=parts)
    assert msgs[0]["role"] == "system"
    assert msgs[1]["content"] == [
        {"type": "text", "text": "[附件: a.txt]\nAAA"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,X"}},
        {"type": "text", "text": "对比"},
    ]


def test_build_messages_with_attachments_no_text():
    """有附件但 message 为空 → content 数组不附加空 text part（首条为 system）。"""
    svc = DoubaoService()
    parts = [{"type": "image_url", "image_url": {"url": "x"}}]
    msgs = svc._build_messages("", history=None, attachment_parts=parts)
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": parts}


def test_build_messages_history_keeps_strings():
    """历史消息保持 content: str 格式（不展开成多模态数组）。首条为 RAG system。"""
    svc = DoubaoService()
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    parts = [{"type": "text", "text": "[附件: a.pdf]\n..."}]
    msgs = svc._build_messages("继续", history=history, attachment_parts=parts)
    assert msgs[0]["role"] == "system"
    assert msgs[1:] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "[附件: a.pdf]\n..."},
                {"type": "text", "text": "继续"},
            ],
        },
    ]


# ============================================================================
# stream_chat 端到端：mock httpx 校验 Ark payload
# ============================================================================
def _patch_httpx_with_text_reply(monkeypatch, reply: str = "看到了") -> Dict[str, Any]:
    """mock httpx 让 Ark 返回单轮纯文本。返回 captured 字典可读到 payload。"""
    import httpx

    body = _build_response_body([_text_delta(reply), _finish("stop")])
    fake_resp = _FakeResponse(200, body)

    class _FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *e): return None
        def stream(self, *a, **kw):
            class _Ctx:
                async def __aenter__(self2): return fake_resp
                async def __aexit__(self2, *e): return None
            return _Ctx()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    captured: Dict[str, Any] = {}
    real_stream_once = DoubaoService._stream_once

    async def _spy(self, messages, tool_schemas):
        captured["messages"] = messages
        async for ev in real_stream_once(self, messages, tool_schemas):
            yield ev

    monkeypatch.setattr(DoubaoService, "_stream_once", _spy)
    return captured


@pytest.mark.asyncio
async def test_stream_chat_image_attachment_becomes_content_array(monkeypatch):
    """图片附件 → 发给 Ark 的 user.content 是多模态数组。"""
    captured = _patch_httpx_with_text_reply(monkeypatch)

    async def resolver(fid: str) -> List[Dict[str, Any]]:
        return [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{fid}"}}]

    svc = DoubaoService()
    events = []
    async for evt in svc.stream_chat(
        message="这张图有什么",
        history=None,
        file_ids=["img-1"],
        attachment_resolver=resolver,
    ):
        events.append(evt)

    msgs = captured["messages"]
    # 首条固定为 RAG system prompt（kb_search 强制指令）
    assert msgs[0]["role"] == "system"
    assert "kb_search" in msgs[0]["content"]
    user_msg = msgs[1]
    assert user_msg["role"] == "user"
    assert user_msg["content"] == [
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,img-1"}},
        {"type": "text", "text": "这张图有什么"},
    ]
    assert events[-1]["type"] == "done"


@pytest.mark.asyncio
async def test_stream_chat_document_attachment_as_text_part(monkeypatch):
    """文档附件 → 发给 Ark 的 user.content 包含 text part（带文件名 header）。"""
    captured = _patch_httpx_with_text_reply(monkeypatch, reply="总结如下")

    async def resolver(fid: str) -> List[Dict[str, Any]]:
        if fid == "doc-1":
            return [{"type": "text", "text": "[附件: report.pdf]\n第一段内容"}]
        return []

    svc = DoubaoService()
    async for _ in svc.stream_chat(
        message="总结这个文档",
        history=None,
        file_ids=["doc-1"],
        attachment_resolver=resolver,
    ):
        pass

    msgs = captured["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[1]["content"] == [
        {"type": "text", "text": "[附件: report.pdf]\n第一段内容"},
        {"type": "text", "text": "总结这个文档"},
    ]


@pytest.mark.asyncio
async def test_stream_chat_mixed_doc_and_image_in_order(monkeypatch):
    """文档+图片混合：按 file_ids 顺序拼接附件，user text 永远在末尾。"""
    captured = _patch_httpx_with_text_reply(monkeypatch)

    async def resolver(fid: str) -> List[Dict[str, Any]]:
        if fid.startswith("doc"):
            return [{"type": "text", "text": f"[附件: {fid}.pdf]\nDOC-{fid}"}]
        return [{"type": "image_url", "image_url": {"url": f"data:..;base64,{fid}"}}]

    svc = DoubaoService()
    async for _ in svc.stream_chat(
        message="综合分析",
        history=None,
        file_ids=["doc-1", "img-1", "doc-2"],
        attachment_resolver=resolver,
    ):
        pass

    msgs = captured["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[1]["content"] == [
        {"type": "text", "text": "[附件: doc-1.pdf]\nDOC-doc-1"},
        {"type": "image_url", "image_url": {"url": "data:..;base64,img-1"}},
        {"type": "text", "text": "[附件: doc-2.pdf]\nDOC-doc-2"},
        {"type": "text", "text": "综合分析"},
    ]


@pytest.mark.asyncio
async def test_stream_chat_no_resolver_keeps_text_string(monkeypatch):
    """attachment_resolver=None → 旧行为：content 是字符串，零回归。"""
    captured = _patch_httpx_with_text_reply(monkeypatch)

    svc = DoubaoService()
    async for _ in svc.stream_chat(message="hi", history=None, file_ids=["x"]):
        pass

    msgs = captured["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[1]["content"] == "hi"


# ============================================================================
# services.attachments：直接测试 file_id → parts 转换
# ============================================================================
class _FakeRecord:
    """最小化 FileRecord：只暴露 attachments 关心的属性。"""

    def __init__(self, *, id: str, file_name: str, content_type: str, object_name: str):
        self.id = id
        self.file_name = file_name
        self.content_type = content_type
        self.object_name = object_name


@pytest.mark.asyncio
async def test_attachments_image_to_base64_data_uri(monkeypatch):
    """图片 → 单个 image_url part，url 是 data URI。"""
    import base64
    from app.services import attachments

    monkeypatch.setattr(
        attachments.storage, "get_data", lambda name: b"\x89PNG\r\n\x1a\nFAKEBYTES"
    )

    class _StubDB:
        class _Repo:
            async def get_by_id(self, fid):
                return _FakeRecord(
                    id=fid, file_name="p.png",
                    content_type="image/png", object_name="p.png",
                )
        def __init__(self): self.file_repo = self._Repo()

    db = type("DB", (), {"file_repo": _StubDB().file_repo})()
    # 上面这一坨嫌复杂，直接用 monkeypatch 替换 FileRepository
    from app.repositories import file_repo as file_repo_mod
    class _FakeFileRepo:
        def __init__(self, _db): pass
        async def get_by_id(self, fid):
            return _FakeRecord(
                id=fid, file_name="p.png",
                content_type="image/png", object_name="p.png",
            )
    monkeypatch.setattr(file_repo_mod, "FileRepository", _FakeFileRepo)

    parts = await attachments.resolve_file_to_parts(db=None, file_id="p-1")
    expected_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nFAKEBYTES").decode("ascii")
    assert parts == [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{expected_b64}"}}
    ]


@pytest.mark.asyncio
async def test_attachments_txt_as_text_part(monkeypatch):
    """TXT 文件 → 单个 text part，header 带文件名。"""
    from app.services import attachments
    from app.repositories import file_repo as file_repo_mod

    class _FakeFileRepo:
        def __init__(self, _db): pass
        async def get_by_id(self, fid):
            return _FakeRecord(
                id=fid, file_name="note.txt",
                content_type="text/plain", object_name="note.txt",
            )
    monkeypatch.setattr(file_repo_mod, "FileRepository", _FakeFileRepo)
    monkeypatch.setattr(attachments.storage, "get_data", lambda name: b"hello\nworld")

    parts = await attachments.resolve_file_to_parts(db=None, file_id="n-1")
    assert parts == [{"type": "text", "text": "[附件: note.txt]\nhello\nworld"}]


@pytest.mark.asyncio
async def test_attachments_pdf_parsed_to_text(monkeypatch):
    """PDF 文件 → document_parser.parse_pdf 结果作为 text part。"""
    from app.services import attachments
    from app.repositories import file_repo as file_repo_mod

    class _FakeFileRepo:
        def __init__(self, _db): pass
        async def get_by_id(self, fid):
            return _FakeRecord(
                id=fid, file_name="report.pdf",
                content_type="application/pdf", object_name="report.pdf",
            )
    monkeypatch.setattr(file_repo_mod, "FileRepository", _FakeFileRepo)
    monkeypatch.setattr(attachments.storage, "get_data", lambda name: b"%PDF-FAKE")
    monkeypatch.setattr(
        attachments.document_parser, "parse_pdf",
        lambda b: "Page 1 text\n\nPage 2 text",
    )

    parts = await attachments.resolve_file_to_parts(db=None, file_id="r-1")
    assert parts == [
        {"type": "text", "text": "[附件: report.pdf]\nPage 1 text\n\nPage 2 text"}
    ]


@pytest.mark.asyncio
async def test_attachments_unsupported_type_returns_empty(monkeypatch):
    """不支持的 content_type → []，不抛异常。"""
    from app.services import attachments
    from app.repositories import file_repo as file_repo_mod

    class _FakeFileRepo:
        def __init__(self, _db): pass
        async def get_by_id(self, fid):
            return _FakeRecord(
                id=fid, file_name="x.zip",
                content_type="application/zip", object_name="x.zip",
            )
    monkeypatch.setattr(file_repo_mod, "FileRepository", _FakeFileRepo)

    parts = await attachments.resolve_file_to_parts(db=None, file_id="z-1")
    assert parts == []


@pytest.mark.asyncio
async def test_attachments_file_not_found_returns_empty(monkeypatch):
    """file_id 不存在 → []。"""
    from app.services import attachments
    from app.repositories import file_repo as file_repo_mod

    class _FakeFileRepo:
        def __init__(self, _db): pass
        async def get_by_id(self, fid): return None
    monkeypatch.setattr(file_repo_mod, "FileRepository", _FakeFileRepo)

    parts = await attachments.resolve_file_to_parts(db=None, file_id="missing")
    assert parts == []


@pytest.mark.asyncio
async def test_attachments_long_text_truncated(monkeypatch):
    """超长文档按 _MAX_TEXT_CHARS 截断。"""
    from app.services import attachments
    from app.repositories import file_repo as file_repo_mod

    class _FakeFileRepo:
        def __init__(self, _db): pass
        async def get_by_id(self, fid):
            return _FakeRecord(
                id=fid, file_name="huge.txt",
                content_type="text/plain", object_name="huge.txt",
            )
    monkeypatch.setattr(file_repo_mod, "FileRepository", _FakeFileRepo)
    monkeypatch.setattr(attachments.storage, "get_data", lambda name: b"X" * (attachments._MAX_TEXT_CHARS + 1000))

    parts = await attachments.resolve_file_to_parts(db=None, file_id="h-1")
    assert len(parts) == 1
    text = parts[0]["text"]
    assert text.startswith("[附件: huge.txt]\n")
    assert text.endswith("[内容已截断...]")
    assert len(text) < attachments._MAX_TEXT_CHARS + 200


@pytest.mark.asyncio
async def test_attachments_parser_error_reported_as_text(monkeypatch):
    """document_parser 报错 → 把错误信息当作文本 part 返回（不抛）。"""
    from app.services import attachments
    from app.repositories import file_repo as file_repo_mod

    class _FakeFileRepo:
        def __init__(self, _db): pass
        async def get_by_id(self, fid):
            return _FakeRecord(
                id=fid, file_name="bad.pdf",
                content_type="application/pdf", object_name="bad.pdf",
            )
    monkeypatch.setattr(file_repo_mod, "FileRepository", _FakeFileRepo)
    monkeypatch.setattr(attachments.storage, "get_data", lambda name: b"%PDF-CORRUPT")
    monkeypatch.setattr(
        attachments.document_parser, "parse_pdf",
        lambda b: "PDF 解析失败: EOF marker not found",
    )

    parts = await attachments.resolve_file_to_parts(db=None, file_id="b-1")
    assert parts == [
        {"type": "text", "text": "[附件 bad.pdf] PDF 解析失败: EOF marker not found"}
    ]
