"""
附件解析服务 - 把已上传文件转成 Chat Completions 多模态 content parts。

支持的输出类型:
  - image_url: 图片走 base64 data URI（不依赖公网可达）
  - text:      文档解析后内联为文本（PDF / DOCX / TXT / MD / CSV）

不在白名单的 content_type 或解析失败的 → 返回 []，不阻断整次请求。

单文档硬上限 _MAX_TEXT_CHARS，超长截断并标 [内容已截断...]。
（豆包 64K 上下文能吃下 ~50K 汉字，给历史/工具/system prompt 留点余量。）
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List

from app.services.document_parser import document_parser
from app.services.storage import storage

logger = logging.getLogger(__name__)

_IMAGE_PREFIX = "image/"
_PARSER_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".csv"}
_MAX_TEXT_CHARS = 50_000

# 解析器失败时的错误前缀（与 document_parser.py 字符串对齐）
_PARSER_ERROR_PREFIXES = ("PDF 解析失败", "Word 解析失败", "不支持的文件类型")


def _to_content_parts(record) -> List[Dict[str, Any]]:
    """FileRecord → 0+ 个 content parts。"""
    content_type = (record.content_type or "").lower()

    # ---- 图片 → image_url (base64 data URI) ----
    if content_type.startswith(_IMAGE_PREFIX):
        try:
            data = storage.get_data(record.object_name)
        except Exception as e:
            logger.warning("read image %s failed: %s", record.id, e)
            return []
        b64 = base64.b64encode(data).decode("ascii")
        return [{
            "type": "image_url",
            "image_url": {"url": f"data:{content_type};base64,{b64}"},
        }]

    # ---- 文档 → text (解析后) ----
    ext = os.path.splitext(record.file_name or "")[1].lower()
    is_parseable = (
        ext in _PARSER_EXTENSIONS
        or content_type.startswith("text/")
        or content_type == "application/pdf"
        or content_type in {
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
    )
    if not is_parseable:
        return []

    try:
        data = storage.get_data(record.object_name)
    except Exception as e:
        logger.warning("read document %s failed: %s", record.id, e)
        return []

    text = document_parser.parse(data, ext)

    # 解析失败时把错误信息当作文本 part 返回，让模型知道附件有问题
    if any(text.startswith(p) for p in _PARSER_ERROR_PREFIXES):
        return [{"type": "text", "text": f"[附件 {record.file_name}] {text}"}]

    if len(text) > _MAX_TEXT_CHARS:
        text = text[:_MAX_TEXT_CHARS] + "\n\n[内容已截断...]"

    return [{"type": "text", "text": f"[附件: {record.file_name}]\n{text}"}]


async def resolve_file_to_parts(db, file_id: str) -> List[Dict[str, Any]]:
    """file_id → 0+ 个多模态 content parts。

    失败（文件不存在 / 存储读不出 / 类型不支持）一律返回 []，
    由上层 stream_chat 跳过该附件，不阻断整次请求。
    """
    from app.repositories.file_repo import FileRepository  # 局部引入避免循环
    record = await FileRepository(db).get_by_id(file_id)
    if not record:
        return []
    return _to_content_parts(record)
