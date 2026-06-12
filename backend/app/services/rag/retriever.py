"""Retriever: 三层检索（条号精准 / 向量召回 / 关联拉取）+ 防幻觉格式化。

设计:
- 第一层【条号精准】: query 里抓 "第N条" → 直接按 (law_code, article_no, is_current)
  查 MySQL 拿正文 chunk；命中即返回，绕过向量检索。
- 第二层【向量召回】: 默认 filter is_current=True；可选 law_code / doc_type；
  距离 > RETRIEVAL_SCORE_THRESHOLD 的丢弃。
- 第三层【关联拉取】: 命中"释义/场景"类 chunk 时，如带 article_no，
  顺手把同 article_no 的"正文 chunk"拉一份塞进上下文（同条法源 + 解读并列）。

format_for_llm: 把 chunks 拼成 [1] [2] 引用块。**未命中时返回硬阻止串**，
要求 LLM 必须告知用户"未检索到对应法律条款"，不得编造法条号。

parse_sources_from_llm_result: 反解 LLM 看到的字符串，提取 sources 事件 payload。
"""
from __future__ import annotations

import re
from typing import Any, Optional

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.repositories.knowledge_repo import KnowledgeRepository
from app.services.rag.embedder import embedder
from app.services.rag.law_chunker import extract_article_refs
from app.services.rag.query_rewriter import rewrite_query
from app.services.rag.vector_store import vector_store

# 引用块行格式: [N] 《title》[law_code/doc_type/version/状态] 第N条 相似度 score
# snippet 用非贪婪 + 前瞻：停在下一个 \n\n[N] 或字符串末尾，避免把后续 source 行吃进去
_SOURCE_LINE_RE = re.compile(
    r"^\[(\d+)\] 《(.+?)》\[([^/\]]+)/([^/\]]+)/([^/\]]+)/([^\]]+)\](?: 第([^\s]+)条)? 相似度 ([\d.]+)\n(.*?)(?=\n\n\[\d+\]|\Z)",
    re.MULTILINE | re.DOTALL,
)

# 用户引用法律全名检测（"民法典" / "刑法" 等）。命中后用于条号精准检索的 law_code 过滤。
# 列表与 LAW_CODE_VALUES 同步；这里独立维护一份避免 import 环。
_LAW_NAME_HINTS: tuple[str, ...] = (
    "民法典", "刑法", "劳动法", "劳动合同法", "治安管理处罚法",
    "个人信息保护法", "网络安全法", "数据安全法", "宪法",
    "行政处罚法", "民事诉讼法", "刑事诉讼法", "公司法",
)


def _detect_law_code(query: str, fallback: Optional[str]) -> Optional[str]:
    """从 query 文本里识别法律名；找不到回落到调用方传入的 fallback。"""
    if not query:
        return fallback
    for name in _LAW_NAME_HINTS:
        if name in query:
            return name
    return fallback


async def retrieve(
    query: str,
    law_code: Optional[str] = None,
    doc_type: Optional[str] = None,
    top_k: Optional[int] = None,
    version: Optional[str] = None,
    include_repealed: bool = False,
) -> list[dict[str, Any]]:
    """三层检索：条号精准 → 向量召回 → 关联拉取。

    Args:
        query: 用户原始问题或关键词
        law_code: 可选限定法律名（如 "民法典"）；不传时尝试从 query 里识别
        doc_type: 可选限定文档类型（statute / commentary / ...）
        top_k: 返回数量
        version: 可选限定版本号（如 "current" / "2020-修正"）
        include_repealed: True 时纳入已废止版本（默认 False 只查现行）

    Returns:
        排序后的 chunks 列表，dict 含 snippet/title/law_code/doc_type/version/
        is_current/article_no/score/document_id/chunk_id。
    """
    if top_k is None:
        top_k = settings.RETRIEVAL_TOP_K

    # === query 改写：白话 → 「口语 + 法言法语」复合 ===
    # 修复「别人欠我钱不还」类口语 query 跨不过 bge 嵌入域的问题。
    # 只对 query 本身做扩展，不动 user 看到的原 query 字符串。
    rewritten = rewrite_query(query)
    embed_query_text = rewritten.expanded
    scenario_law_hint = rewritten.law_hint

    detected_law_code = _detect_law_code(query, law_code)

    # === 第一层: 条号精准命中 ===
    refs = extract_article_refs(query)
    precise_results: list[dict[str, Any]] = []
    if refs and detected_law_code:
        async with AsyncSessionLocal() as session:
            repo = KnowledgeRepository(session)
            for art in refs:
                hits = await repo.chunks_by_article(
                    law_code=detected_law_code,
                    article_no=art,
                    is_current=None if include_repealed else True,
                    limit=2,  # 同一条最多取 2 个 chunk（防止超长条被分多片）
                )
                precise_results.extend(hits)
        # 条号精准命中数已经达标，直接返回（不再走向量）
        if len(precise_results) >= top_k:
            return precise_results[:top_k]

    # === 第二层: 向量召回 ===
    qvec = await embedder.embed_query(embed_query_text)
    filters: list[dict[str, Any]] = []
    if detected_law_code:
        # 用户**显式提到**了法律名 → 用作 hard filter（高置信）
        filters.append({"law_code": detected_law_code})
    # 不再用 scenario_law_hint 当 hard filter：KB 当前可能没收录该法律，
    # 硬过滤会把 民法典 兜底 chunks 一起屏蔽，反而让「老赖」「打人会判几年」
    # 类问题永远 0 命中。让扩展后的 query 在全库向量空间自由召回；
    # 提示词里的 hint 改由 LLM 在 system prompt 上下文里读取。
    if doc_type:
        filters.append({"doc_type": doc_type})
    if version:
        filters.append({"version": version})
    if not include_repealed:
        filters.append({"is_current": True})
    if len(filters) == 1:
        where: dict[str, Any] | None = filters[0]
    elif len(filters) > 1:
        where = {"$and": filters}
    else:
        where = None

    # 多取一些再过滤，避免阈值过滤后不足 top_k
    raw = await vector_store.query_async(qvec, top_k=max(top_k * 2, 10), where=where)
    vector_hits: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = {r["chunk_id"] for r in precise_results}
    for r in raw:
        if r["distance"] > settings.RETRIEVAL_SCORE_THRESHOLD:
            continue
        if r["id"] in seen_chunk_ids:
            continue
        meta = r["metadata"]
        vector_hits.append({
            "snippet": (r["document"] or "")[:500],
            "title": meta.get("title", ""),
            "law_code": meta.get("law_code", ""),
            "doc_type": meta.get("doc_type", ""),
            "version": meta.get("version", ""),
            "is_current": bool(meta.get("is_current", True)),
            "article_no": meta.get("article_no") or "",
            "document_id": meta.get("document_id", ""),
            "chunk_id": r["id"],
            "score": round(1.0 - r["distance"], 3),
        })
        seen_chunk_ids.add(r["id"])
        if len(vector_hits) >= top_k:
            break

    combined = precise_results + vector_hits

    # === 第三层: 关联拉取 ===
    # 向量命中的释义/场景类 chunk 有 article_no 时，把对应正文 chunk 也拉进来
    if combined:
        async with AsyncSessionLocal() as session:
            repo = KnowledgeRepository(session)
            seen_pairs: set[tuple[str, str]] = {
                (c["law_code"], c["article_no"]) for c in combined if c["article_no"]
            }
            for hit in vector_hits:
                if hit["doc_type"] == "statute":
                    continue  # 命中的就是正文，无需关联
                art = hit["article_no"]
                if not art or not hit["law_code"]:
                    continue
                key = (hit["law_code"], art)
                # 同一条款只关联一次，且不和已命中的重复
                if key in seen_pairs and any(
                    c["doc_type"] == "statute" and c["article_no"] == art
                    and c["law_code"] == hit["law_code"]
                    for c in combined
                ):
                    continue
                related = await repo.chunks_by_article(
                    law_code=hit["law_code"],
                    article_no=art,
                    is_current=None if include_repealed else True,
                    limit=1,
                )
                related = [r for r in related if r["doc_type"] == "statute"]
                for r in related:
                    if r["chunk_id"] in seen_chunk_ids:
                        continue
                    combined.append(r)
                    seen_chunk_ids.add(r["chunk_id"])

    return combined[: max(top_k * 2, top_k)]


def format_for_llm(chunks: list[dict[str, Any]]) -> str:
    """把检索结果格式化为 LLM 友好的引用块。

    空列表 → 返回硬阻止串：要求 LLM 必须告知用户"未检索到对应法律条款"，
    不得编造法条号、条文、立法理由。
    """
    if not chunks:
        return (
            "（知识库未命中相关法律条款。**请按以下格式回复用户**：\n"
            "「未检索到对应法律条款，无法提供准确依据。」\n"
            "**禁止凭记忆生成法条号、条文内容、司法解释，禁止脑补立法理由**。\n"
            "如能确定属于已知法律但库内未收录，可建议用户去『国家法律法规数据库 flk.npc.gov.cn』查询。）"
        )
    lines = []
    for i, c in enumerate(chunks):
        status = "现行" if c.get("is_current", True) else "已废止"
        art = c.get("article_no") or ""
        art_suffix = f" 第{art}条" if art else ""
        lines.append(
            f"[{i+1}] 《{c['title']}》[{c['law_code']}/{c['doc_type']}/{c['version']}/{status}]"
            f"{art_suffix} 相似度 {c['score']}\n{c['snippet']}"
        )
    return "\n\n".join(lines)


def parse_sources_from_llm_result(result_str: str) -> list[dict[str, Any]]:
    """反解 LLM 看到的引用块文本，提取结构化 sources（用于 SSE 事件透传）。

    容错: 解析失败时返回空 list（不影响主流程）。
    """
    if not result_str or "未命中相关法律条款" in result_str or "未检索到对应法律条款" in result_str:
        return []
    out: list[dict[str, Any]] = []
    for m in _SOURCE_LINE_RE.finditer(result_str):
        title = m.group(2)
        law_code = m.group(3)
        doc_type = m.group(4)
        version = m.group(5)
        status = m.group(6)
        article = m.group(7) or ""
        score = float(m.group(8))
        snippet = m.group(9).strip()
        out.append({
            "title": title,
            "law_code": law_code,
            "doc_type": doc_type,
            "version": version,
            "is_current": status == "现行",
            "article_no": article,
            "score": score,
            "snippet": snippet[:500],
        })
    return out
