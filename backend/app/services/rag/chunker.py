"""文本切分 + 去重。

策略: 段落 → 句号 → 硬切 三级回退。优先保留段落/句子边界，
避免把一段剧情对话或一项数值描述切断。

注: 当前版本未实现跨 chunk 重叠 (sliding window)。段落/句号切分已
保留大部分语义边界，对 RAG 检索够用。如果未来发现「数值描述被切断」
的 case，再加 sliding window (chunk[i] 末尾 N 字进 chunk[i+1] 开头)。
"""
from __future__ import annotations

import hashlib
import re
from typing import List

# 切分优先级: 双换行（段落） > 单换行 > 句号/问号/感叹号（中文+英文） > 硬切
_PARAGRAPH_RE = re.compile(r"\n\s*\n+")
_SENTENCE_RE = re.compile(r"(?<=[。！？!?])\s*|(?<=[.．])\s+")


def split_text(text: str, chunk_size: int = 500, overlap: int = 0) -> List[str]:
    """按段落→句号→硬切 三级回退。保留自然边界。

    Args:
        text: 原始文本
        chunk_size: 单 chunk 字符上限
        overlap: 保留参数接口（暂未实现 sliding window，见模块 docstring）

    Returns:
        切分后的 chunk 列表
    """
    del overlap  # 暂未使用
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    # 第一级: 段落
    paragraphs = [p.strip() for p in _PARAGRAPH_RE.split(text) if p.strip()]
    chunks: list[str] = []

    for para in paragraphs:
        if len(para) > chunk_size:
            # 段落本身就超过 chunk_size → 走二级句号切
            chunks.extend(_split_long_paragraph(para, chunk_size))
            continue
        chunks.append(para)
    return chunks


def _split_long_paragraph(para: str, chunk_size: int) -> List[str]:
    """二级: 按句号切"""
    sentences = [s.strip() for s in _SENTENCE_RE.split(para) if s.strip()]
    chunks: list[str] = []
    buf = ""
    for s in sentences:
        if len(s) > chunk_size:
            # 三级: 硬切
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.extend(_hard_split(s, chunk_size))
            continue
        candidate = (buf + s).strip() if buf else s
        if len(candidate) <= chunk_size:
            buf = candidate
        else:
            if buf:
                chunks.append(buf)
            buf = s
    if buf:
        chunks.append(buf)
    return chunks


def _hard_split(text: str, chunk_size: int) -> List[str]:
    """三级: 硬切，固定窗口。"""
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def chunk_hash(text: str) -> str:
    """sha256 前 16 字符（64 bit 足够碰撞避免）。"""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def deduplicate_chunks(chunks: List[str]) -> List[str]:
    """跨 chunk 去重。返回去重后的 chunk 列表。"""
    seen: set[str] = set()
    out: list[str] = []
    for c in chunks:
        h = chunk_hash(c)
        if h in seen:
            continue
        seen.add(h)
        out.append(c)
    return out
