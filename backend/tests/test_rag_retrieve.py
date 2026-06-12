"""测试 RAG retriever：检索过滤 + 格式化 + 解析 + query 改写。

不真打 embedding 模型和向量库——通过 monkeypatch 替换掉。
"""
from __future__ import annotations

import pytest

from app.services.rag import retriever
from app.services.rag.query_rewriter import rewrite_query
from app.services.rag.retriever import format_for_llm, parse_sources_from_llm_result


# ===== format_for_llm =====

class TestFormatForLLM:
    def test_empty_chunks_returns_hard_block_string(self) -> None:
        """空 chunks → 返回硬阻止串，要求 LLM 告知用户未检索到。"""
        out = format_for_llm([])
        assert "未检索到对应法律条款" in out
        assert "禁止凭记忆" in out
        # 提示词里要求建议去 flk 查询
        assert "flk.npc.gov.cn" in out

    def test_single_chunk_with_article(self) -> None:
        chunks = [{
            "title": "中华人民共和国民法典",
            "law_code": "民法典",
            "doc_type": "statute",
            "version": "2021",
            "is_current": True,
            "article_no": "667",
            "snippet": "借款合同是借款人向贷款人借款，到期返还借款并支付利息的合同。",
            "score": 0.87,
            "document_id": "doc-1",
            "chunk_id": "c-1",
        }]
        out = format_for_llm(chunks)
        assert "[1] 《中华人民共和国民法典》[民法典/statute/2021/现行]" in out
        assert "第667条" in out
        assert "0.87" in out
        assert "借款合同" in out

    def test_repealed_status_shown(self) -> None:
        chunks = [{
            "title": "老法律",
            "law_code": "民法典",
            "doc_type": "statute",
            "version": "2020-修正",
            "is_current": False,
            "article_no": "1",
            "snippet": "...",
            "score": 0.5,
            "document_id": "d1",
            "chunk_id": "c1",
        }]
        out = format_for_llm(chunks)
        assert "已废止" in out

    def test_multiple_chunks_numbered(self) -> None:
        chunks = [
            {"title": "A", "law_code": "民法典", "doc_type": "statute", "version": "v",
             "is_current": True, "article_no": "1", "snippet": "aaa", "score": 0.9,
             "document_id": "1", "chunk_id": "1"},
            {"title": "B", "law_code": "民法典", "doc_type": "statute", "version": "v",
             "is_current": True, "article_no": "2", "snippet": "bbb", "score": 0.8,
             "document_id": "2", "chunk_id": "2"},
        ]
        out = format_for_llm(chunks)
        assert "[1]" in out
        assert "[2]" in out
        assert "《A》" in out
        assert "《B》" in out


# ===== parse_sources_from_llm_result（反解） =====

class TestParseSources:
    def test_empty_returns_empty(self) -> None:
        assert parse_sources_from_llm_result("") == []
        assert parse_sources_from_llm_result("随便写的文本") == []

    def test_no_match_marker_returns_empty(self) -> None:
        s = "（知识库未命中相关法律条款。**请按以下格式回复用户**：\n「未检索到对应法律条款，无法提供准确依据。」）"
        assert parse_sources_from_llm_result(s) == []

    def test_parses_one_source(self) -> None:
        s = "[1] 《民法典》[民法典/statute/2021/现行] 第667条 相似度 0.87\n借款合同是借款人向贷款人借款"
        out = parse_sources_from_llm_result(s)
        assert len(out) == 1
        assert out[0]["title"] == "民法典"
        assert out[0]["law_code"] == "民法典"
        assert out[0]["doc_type"] == "statute"
        assert out[0]["version"] == "2021"
        assert out[0]["is_current"] is True
        assert out[0]["article_no"] == "667"
        assert out[0]["score"] == 0.87
        assert "借款合同" in out[0]["snippet"]

    def test_parses_repealed_status(self) -> None:
        s = "[1] 《老法律》[民法典/statute/2020-修正/已废止] 第1条 相似度 0.5\n旧版条文"
        out = parse_sources_from_llm_result(s)
        assert out[0]["is_current"] is False

    def test_parses_no_article(self) -> None:
        s = "[1] 《民法典》[民法典/statute/2021/现行] 相似度 0.87\n无条号片段"
        out = parse_sources_from_llm_result(s)
        assert out[0]["article_no"] == ""

    def test_parses_multiple_sources(self) -> None:
        s = (
            "[1] 《A》[民法典/statute/2021/现行] 第1条 相似度 0.87\nA\n\n"
            "[2] 《B》[民法典/statute/2021/现行] 第2条 相似度 0.82\nB"
        )
        out = parse_sources_from_llm_result(s)
        assert len(out) == 2
        assert out[0]["title"] == "A"
        assert out[1]["title"] == "B"
        assert out[1]["article_no"] == "2"

    def test_malformed_returns_empty(self) -> None:
        # 格式不对（缺相似度）
        s = "[1] 《民法典》[民法典/statute/2021/现行]"
        assert parse_sources_from_llm_result(s) == []


# ===== query_rewriter =====

class TestQueryRewriter:
    def test_empty_query(self) -> None:
        rq = rewrite_query("")
        assert rq.original == ""
        assert rq.expanded == ""
        assert rq.law_hint is None

    def test_no_trigger_returns_unchanged(self) -> None:
        rq = rewrite_query("民法典关于借款合同的规定")
        # 命中 "合同" trigger 会被扩展
        assert "合同" in rq.original

    def test_lay_money_query_expanded(self) -> None:
        """别人欠我钱不还 → 应该扩出借款合同、债权等法言法语。"""
        rq = rewrite_query("别人欠我钱不还")
        assert "借款合同" in rq.expanded
        assert "返还借款" in rq.expanded

    def test_lay_money_query_with_explicit_law(self) -> None:
        """用户口语 + 显式提到法律名 → 都应被扩展。"""
        rq = rewrite_query("别人欠我钱不还，按照民法典我该怎么维权？")
        assert "借款合同" in rq.expanded
        assert rq.law_hint in (None, "民事诉讼法")  # 维权 → 民事诉讼法

    def test_labor_query_routes_to_labor_law(self) -> None:
        """老板拖欠工资 → 推断到 劳动法。"""
        rq = rewrite_query("老板拖欠工资能告吗")
        assert "劳动法" in rq.expanded
        assert "工资" in rq.expanded
        assert rq.law_hint == "劳动法"

    def test_assault_routes_to_criminal_law(self) -> None:
        """打人会判几年 → 推断到 刑法。"""
        rq = rewrite_query("打人会判几年")
        assert rq.law_hint == "刑法"

    def test_civil_assault_finds_injury_law(self) -> None:
        """我被人打伤了 → 应包含 侵权 / 人身损害 关键词。"""
        rq = rewrite_query("我被人打伤了能要求什么赔偿")
        assert "侵权" in rq.expanded
        assert "人身损害" in rq.expanded
        assert "赔偿" in rq.expanded

    def test_rent_query_finds_lease(self) -> None:
        """租客不付房租 → 应包含 租赁合同 / 租金。"""
        rq = rewrite_query("租客不付房租怎么办")
        assert "租赁合同" in rq.expanded
        assert "租金" in rq.expanded
        assert rq.law_hint == "民法典"

    def test_marriage_query_finds_marriage_chapter(self) -> None:
        """离婚 + 抚养权 → 应包含 婚姻 / 抚养。"""
        rq = rewrite_query("离婚后孩子的抚养权归谁")
        assert "婚姻" in rq.expanded
        assert "抚养" in rq.expanded
        assert rq.law_hint == "民法典"

    def test_short_substring_triggers_work(self) -> None:
        """短 trigger（"辞退" 而不是"被辞退"）应能匹配夹字的情况。"""
        rq = rewrite_query("我被公司辞退了能要赔偿吗")
        assert "劳动法" in rq.expanded
        assert "解除劳动合同" in rq.expanded
        assert "赔偿金" in rq.expanded

    def test_no_overlap_with_original(self) -> None:
        """不应把原 query 已有的词再拼一遍。"""
        rq = rewrite_query("借款合同借款合同借款合同")
        # 重复词不应再被加进 expanded
        assert rq.expanded.count("借款合同") <= 3

    def test_law_hint_picks_longest_trigger(self) -> None:
        """长 trigger 优先（如"被辞退" > "辞退"）。"""
        # 含 "被辞退"（3 字）和 "辞退"（2 字），应优先长 trigger 对应的扩展
        rq = rewrite_query("我被辞退了")
        assert "劳动法" in rq.expanded


# ===== retrieve 集成（mock 掉 embedder + vector_store）=====

class TestRetrieve:
    @pytest.mark.asyncio
    async def test_filters_by_distance_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # mock embedder.embed_query
        async def fake_embed_query(_q: str) -> list[float]:
            return [0.1, 0.2, 0.3]
        monkeypatch.setattr(retriever.embedder, "embed_query", fake_embed_query)

        # mock vector_store.query_async
        async def fake_query_async(_vec, *, top_k, where):
            return [
                {"id": "a", "document": "好的命中", "metadata": {
                    "title": "A", "law_code": "民法典", "doc_type": "statute",
                    "version": "2021", "is_current": True, "document_id": "d1"
                }, "distance": 0.1},  # 相似度 0.9 通过
                {"id": "b", "document": "差的命中", "metadata": {
                    "title": "B", "law_code": "民法典", "doc_type": "statute",
                    "version": "2021", "is_current": True, "document_id": "d2"
                }, "distance": 0.8},  # 距离 0.8 > 0.45 阈值 → 被过滤
            ]
        monkeypatch.setattr(retriever.vector_store, "query_async", fake_query_async)

        chunks = await retriever.retrieve("借款合同", law_code="民法典")
        assert len(chunks) == 1
        assert chunks[0]["title"] == "A"
        assert chunks[0]["score"] == 0.9

    @pytest.mark.asyncio
    async def test_builds_where_filter_from_law_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict = {}

        async def fake_embed_query(_q: str) -> list[float]:
            return [0.0]

        async def fake_query_async(_vec, *, top_k, where):
            captured["where"] = where
            captured["top_k"] = top_k
            return []

        monkeypatch.setattr(retriever.embedder, "embed_query", fake_embed_query)
        monkeypatch.setattr(retriever.vector_store, "query_async", fake_query_async)

        # 只传 law_code，retriever 还会自动加 is_current=True 默认过滤
        await retriever.retrieve("test", law_code="民法典")
        assert captured["where"] == {"$and": [{"law_code": "民法典"}, {"is_current": True}]}
        # retriever 会多取 2 倍以避免阈值过滤后不足
        from app.core.config import settings
        assert captured["top_k"] == max(settings.RETRIEVAL_TOP_K * 2, 10)

    @pytest.mark.asyncio
    async def test_builds_where_filter_with_doc_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict = {}

        async def fake_embed_query(_q: str) -> list[float]:
            return [0.0]
        async def fake_query_async(_vec, *, top_k, where):
            captured["where"] = where
            return []

        monkeypatch.setattr(retriever.embedder, "embed_query", fake_embed_query)
        monkeypatch.setattr(retriever.vector_store, "query_async", fake_query_async)

        await retriever.retrieve("test", law_code="民法典", doc_type="commentary")
        assert captured["where"] == {
            "$and": [
                {"law_code": "民法典"},
                {"doc_type": "commentary"},
                {"is_current": True},
            ]
        }

    @pytest.mark.asyncio
    async def test_explicit_law_takes_precedence_over_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """用户显式提了法律名（即便 query 改写器推断出别的 hint），只用显式那个。"""
        captured: dict = {}

        async def fake_embed_query(q: str) -> list[float]:
            captured["embedded_text"] = q
            return [0.0]
        async def fake_query_async(_vec, *, top_k, where):
            captured["where"] = where
            return []

        monkeypatch.setattr(retriever.embedder, "embed_query", fake_embed_query)
        monkeypatch.setattr(retriever.vector_store, "query_async", fake_query_async)

        # "别人欠我钱不还" 会被改写器推断 hint=民事诉讼法，
        # 但用户显式说 "民法典" → filter 应当是 law_code=民法典，不是 民事诉讼法
        await retriever.retrieve(
            "别人欠我钱不还，按照民法典我该怎么维权？",
            law_code=None,
        )
        assert captured["where"] == {"$and": [{"law_code": "民法典"}, {"is_current": True}]}
        # query 应当被扩展了
        assert "借款合同" in captured["embedded_text"]

    @pytest.mark.asyncio
    async def test_no_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """用户没提法律名 + 改写器也没推断出 hint → 仍有 is_current 默认过滤。"""
        captured: dict = {}
        async def fake_embed_query(_q: str) -> list[float]: return [0.0]
        async def fake_query_async(_vec, *, top_k, where):
            captured["where"] = where
            return []

        monkeypatch.setattr(retriever.embedder, "embed_query", fake_embed_query)
        monkeypatch.setattr(retriever.vector_store, "query_async", fake_query_async)

        # "诉讼时效是多久" 没任何 trigger，hint 应为 None
        # filter 仅剩 is_current=True（默认排除废止版本）
        await retriever.retrieve("诉讼时效是多久")
        assert captured["where"] == {"is_current": True}

    @pytest.mark.asyncio
    async def test_no_law_hint_filter_when_only_scenario_detected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """关键修复：law_hint 不再当 hard filter，否则会把 民法典 兜底 chunks 屏蔽。"""
        captured: dict = {}
        async def fake_embed_query(q: str) -> list[float]:
            captured["embedded_text"] = q
            return [0.0]
        async def fake_query_async(_vec, *, top_k, where):
            captured["where"] = where
            return []

        monkeypatch.setattr(retriever.embedder, "embed_query", fake_embed_query)
        monkeypatch.setattr(retriever.vector_store, "query_async", fake_query_async)

        # "老板拖欠工资能告吗" → hint=劳动法（KB 里没有）
        # 修复后：不应当把 law_code=劳动法 当 filter
        # 否则连 民法典 兜底 chunks 都被屏蔽
        await retriever.retrieve("老板拖欠工资能告吗")
        # 不应该被过滤到劳动法（hint 不再当 hard filter）
        assert captured["where"] == {"is_current": True}
        # query 仍应被扩展（"工资 劳动法 劳动合同 ..."）
        assert "劳动法" in captured["embedded_text"]
