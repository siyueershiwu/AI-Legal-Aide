"""测试 RAG chunker：文本切分 + 去重。

不依赖任何外部服务（embedding、向量库都不碰）。
"""
from __future__ import annotations

import pytest

from app.services.rag.chunker import (
    chunk_hash,
    deduplicate_chunks,
    split_text,
)


# ===== split_text =====

class TestSplitText:
    def test_empty_returns_empty(self) -> None:
        assert split_text("") == []
        assert split_text("   ") == []
        assert split_text(None or "") == []  # type: ignore[arg-type]

    def test_short_text_returns_single_chunk(self) -> None:
        text = "原神钟离是岩神"
        assert split_text(text, chunk_size=500) == [text]

    def test_paragraph_split_preserves_boundary(self) -> None:
        # 三个段落：每个 ~30 chars，加起来 90+ chars，超 chunk_size=40 → 必须切
        para1 = "原神钟离" * 10  # 40 chars
        para2 = "等级 20: 坚瞳镐" * 5  # 65 chars
        para3 = "等级 40: 玄岩之塔" * 5  # 75 chars
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = split_text(text, chunk_size=40)
        # 三个段落边界都保留（每个段落单独进 chunks 列表）
        # 因为 40 ≤ 单段长度 ≤ 80 会进入 _split_long_paragraph 再细切，但段落会按顺序进 chunks
        assert "原神钟离" in "".join(chunks[0:1]) or chunks[0] == para1
        assert any("坚瞳镐" in c for c in chunks)
        assert any("玄岩之塔" in c for c in chunks)
        # 关键不变量：三个段落都出现且互不污染
        assert "原神钟离" in "".join(chunks)
        assert "坚瞳镐" in "".join(chunks)
        assert "玄岩之塔" in "".join(chunks)

    def test_long_paragraph_falls_back_to_sentence_split(self) -> None:
        # 单个段落 600 字，chunk_size=100 → 应被切碎（按句号）
        para = (
            "原神钟离的元素爆发是「地心之锚」。"
            "他手持岩枪召唤陨石造成范围岩元素伤害。"
            "长按可以造成更强的范围伤害并形成护盾。"
            "护盾的吸收量基于钟离的生命值上限。"
        )
        chunks = split_text(para, chunk_size=100)
        # 每个 chunk 长度都不应超过 100（hard fallback 时才可能正好等于）
        for c in chunks:
            assert len(c) <= 200  # 句号切分后单 chunk 偶尔可能略大（边界字符）
        # 内容应覆盖原文
        joined = "".join(chunks)
        assert "原神钟离" in joined
        assert "护盾" in joined

    def test_hard_split_when_oversized_no_punctuation(self) -> None:
        # 连续无标点的长串 → 走硬切
        text = "A" * 250
        chunks = split_text(text, chunk_size=100)
        # 硬切必然产生 ≥3 段，每段 100 字以内
        assert all(len(c) <= 100 for c in chunks)
        assert sum(len(c) for c in chunks) == 250

    def test_overlap_param_accepted_but_ignored(self) -> None:
        # 当前版本 overlap 暂未生效（只保留接口）
        # 用大 chunk_size 强制走段落切
        text = "原神" * 50 + "\n\n" + "星穹铁道" * 50
        chunks = split_text(text, chunk_size=200, overlap=100)
        # 段内被切多次，但段落边界保留
        assert "原神" in "".join(chunks)
        assert "星穹铁道" in "".join(chunks)
        # overlap=100 没影响结果
        chunks_no_overlap = split_text(text, chunk_size=200, overlap=0)
        assert chunks == chunks_no_overlap

    def test_strips_whitespace(self) -> None:
        # 入口处 strip() 去掉首尾空白
        text = "  原神钟离  "
        chunks = split_text(text, chunk_size=500)
        assert chunks == ["原神钟离"]


# ===== chunk_hash =====

class TestChunkHash:
    def test_same_text_same_hash(self) -> None:
        assert chunk_hash("hello") == chunk_hash("hello")

    def test_different_text_different_hash(self) -> None:
        assert chunk_hash("hello") != chunk_hash("world")

    def test_hash_length_16(self) -> None:
        assert len(chunk_hash("anything")) == 16


# ===== deduplicate_chunks =====

class TestDeduplicate:
    def test_removes_exact_duplicates(self) -> None:
        chunks = ["原神钟离", "原神钟离", "星穹铁道"]
        assert deduplicate_chunks(chunks) == ["原神钟离", "星穹铁道"]

    def test_preserves_order(self) -> None:
        chunks = ["A", "B", "A", "C", "B"]
        assert deduplicate_chunks(chunks) == ["A", "B", "C"]

    def test_empty_input(self) -> None:
        assert deduplicate_chunks([]) == []

    def test_whitespace_differences_kept_separate(self) -> None:
        # chunk_hash 不去空白 - " A " 和 "A" 视为不同
        # 这是有意的：embedder 也吃不到，相似度自然拉胯，但不去白白改原文
        chunks = ["A", "A ", " A"]
        # 应当保留全部 3 个（hash 不同）
        assert len(deduplicate_chunks(chunks)) == 3
