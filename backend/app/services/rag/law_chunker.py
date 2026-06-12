"""法律文本切分器：按"第N条"切分，保留编/章/节层级前缀。

设计动机:
- 法条天然以"第N条"为最小语义单元；通用 chunker 按字符长度切会把一条切两半，
  embedding 会丢失法条 ID 与对应内容的强关联。
- 保留 编/章/节 层级前缀（注入到每个 chunk 首部）：让 embedding 自带语义路径，
  也让 LLM 看到 chunk 时立刻知道法律出处。
- article_no 标准化为阿拉伯数字字符串（"第五百八十四条" → "584"），便于
  retriever 精准命中。

输入: 标准化后的法律文本（包含 "第一编/第一章/第一节/第N条" 标题）。
输出: [{text, article_no, hierarchy}]，每条一个 chunk；超过 800 字的条按
款（一、二、三）继续二级切分，二级切片共用 article_no。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

# 中文数字 → 阿拉伯数字（覆盖 0-9999，足够民法典第 1260 条规模）
_CN_NUM = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "百": 100, "千": 1000,
}


def cn_to_int(s: str) -> Optional[int]:
    """中文数字 → int。失败返回 None（不抛异常）。

    支持 "一" / "十" / "十二" / "二十" / "一百二十三" / "一千二百六十"。
    输入既可能是纯中文也可能本来就是阿拉伯数字（如 "584"）。
    """
    if not s:
        return None
    s = s.strip()
    if s.isdigit():
        return int(s)
    if not all(c in _CN_NUM for c in s):
        return None
    # 经典中文数字解析：从左到右累乘累加，遇到 千/百/十 触发进位
    total = 0
    section = 0
    for ch in s:
        n = _CN_NUM[ch]
        if n >= 10:
            # "十" 开头视为 1*10
            if section == 0:
                section = 1
            section *= n
            total += section
            section = 0
        else:
            section = n
    total += section
    return total or None


# 章节标题正则（编/章/节/分则）
_SECTION_RE = re.compile(
    r"^(第[一二三四五六七八九十百千零〇\d]+(?:编|分编|章|节|分则))[\s　]*(.*)$"
)

# 条款起始正则：行首"第N条"（可带"之N"如 第584条之一），后面跟一个空白或冒号
_ARTICLE_RE = re.compile(
    r"^第([一二三四五六七八九十百千零〇\d]+)(?:条|条之[一二三四五六七八九十\d]+)"
)


@dataclass
class LawChunk:
    """单条法条切片。"""
    text: str            # 注入了 hierarchy 前缀后的完整文本
    article_no: str      # 标准化阿拉伯数字字符串（"584"）；找不到时为 ""
    hierarchy: str       # 层级路径，如 "第三编 合同 > 第十二章 借款合同"


def _normalize_article_no(raw: str) -> str:
    """'五百八十四' / '584' → '584'。"""
    n = cn_to_int(raw)
    return str(n) if n is not None else raw.strip()


def split_law_text(text: str, law_title: str = "", soft_limit: int = 800) -> List[LawChunk]:
    """按条切分法律文本。

    Args:
        text: 法律全文（已用 \\n 分行；编/章/节 / 第N条 必须独立成行）
        law_title: 法律名称（如 "民法典"），用于注入 hierarchy 前缀
        soft_limit: 单条字符上限，超过后按"款"二次切；不切到字符级（法条
                    保留完整意思优先）

    Returns:
        LawChunk 列表，每条一个或多个 chunk（同 article_no）
    """
    if not text:
        return []

    lines = [ln.rstrip() for ln in text.splitlines()]

    hierarchy_stack: list[str] = []  # ["第三编 合同", "第十二章 借款合同", ...]
    chunks: list[LawChunk] = []

    current_article_no = ""
    current_buf: list[str] = []
    current_hierarchy = ""

    def flush_article() -> None:
        nonlocal current_buf, current_article_no, current_hierarchy
        if not current_buf:
            return
        body = "\n".join(current_buf).strip()
        if not body:
            current_buf = []
            return
        prefix_parts = [p for p in [law_title, current_hierarchy] if p]
        prefix = "【" + " > ".join(prefix_parts) + "】\n" if prefix_parts else ""
        full = prefix + body
        if len(full) <= soft_limit:
            chunks.append(LawChunk(
                text=full,
                article_no=current_article_no,
                hierarchy=current_hierarchy,
            ))
        else:
            # 按"款"切：行首 "一、" / "（一）" / "1." 视为款的起始
            for sub in _split_by_clause(body, soft_limit):
                chunks.append(LawChunk(
                    text=prefix + sub,
                    article_no=current_article_no,
                    hierarchy=current_hierarchy,
                ))
        current_buf = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if current_buf:
                current_buf.append("")
            continue

        # 1) 章节标题：更新层级栈
        sec_m = _SECTION_RE.match(line)
        if sec_m:
            flush_article()  # 切到新章节前先收尾上一条
            current_article_no = ""
            level_text = sec_m.group(1)  # "第三编"
            level_title = sec_m.group(2).strip()
            label = f"{level_text} {level_title}".strip()
            # 根据 编/章/节 在栈中替换对应层级
            level_kind = _section_kind(level_text)
            # 截断栈到该层级之上（编=0, 章=1, 节=2）
            while hierarchy_stack and _section_kind_index(hierarchy_stack[-1]) >= level_kind:
                hierarchy_stack.pop()
            hierarchy_stack.append(label)
            current_hierarchy = " > ".join(hierarchy_stack)
            continue

        # 2) 条款起始：切到新条
        art_m = _ARTICLE_RE.match(line)
        if art_m:
            flush_article()
            current_article_no = _normalize_article_no(art_m.group(1))
            current_buf.append(line)
            continue

        # 3) 正文行：累积进当前条
        current_buf.append(line)

    flush_article()
    return chunks


# === 辅助 ===

def _section_kind(label: str) -> int:
    """编=0, 分编=0, 章=1, 节=2, 分则=0；用于截断 hierarchy_stack。"""
    if "编" in label or "分则" in label:
        return 0
    if "章" in label:
        return 1
    if "节" in label:
        return 2
    return 9  # 未知，最末


def _section_kind_index(stack_entry: str) -> int:
    # stack_entry 形如 "第三编 合同"
    first_token = stack_entry.split(" ", 1)[0]
    return _section_kind(first_token)


# 款切分：行首 一、 / 二、 / （一） / (一) / 1. / 2、
_CLAUSE_HEAD_RE = re.compile(
    r"^(?:[一二三四五六七八九十]+、|[（(][一二三四五六七八九十]+[)）]|\d+[\.、])"
)


def _split_by_clause(body: str, soft_limit: int) -> List[str]:
    """超长条按"款"二次切分；款仍超长就按段落硬切，绝不切到句子中间。"""
    lines = body.splitlines()
    groups: list[list[str]] = [[]]
    for ln in lines:
        if _CLAUSE_HEAD_RE.match(ln.strip()) and groups[-1]:
            groups.append([ln])
        else:
            groups[-1].append(ln)

    out: list[str] = []
    buf = ""
    for g in groups:
        seg = "\n".join(g).strip()
        if not seg:
            continue
        if len(seg) > soft_limit:
            # 单款仍超长：按段落硬切（保留最后一段不切到行中间）
            if buf:
                out.append(buf)
                buf = ""
            out.extend(_paragraph_split(seg, soft_limit))
            continue
        candidate = (buf + "\n" + seg).strip() if buf else seg
        if len(candidate) <= soft_limit:
            buf = candidate
        else:
            if buf:
                out.append(buf)
            buf = seg
    if buf:
        out.append(buf)
    return out or [body]


def _paragraph_split(text: str, limit: int) -> List[str]:
    """段落硬切兜底。"""
    paras = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    out: list[str] = []
    buf = ""
    for p in paras:
        if len(p) > limit:
            if buf:
                out.append(buf)
                buf = ""
            for i in range(0, len(p), limit):
                out.append(p[i : i + limit])
            continue
        candidate = (buf + "\n" + p).strip() if buf else p
        if len(candidate) <= limit:
            buf = candidate
        else:
            if buf:
                out.append(buf)
            buf = p
    if buf:
        out.append(buf)
    return out or [text]


# === 条号识别（query 端用，retriever 调用）===

# 用户提问里出现的条号引用样式：
#   "民法典第584条" / "民法典 第五百八十四条" / "刑法第二百三十二条" / "584条"
_QUERY_ARTICLE_RE = re.compile(
    r"第([一二三四五六七八九十百千零〇]+|\d+)条"
)


def extract_article_refs(query: str) -> list[str]:
    """从用户提问里抓"第N条"，返回标准化阿拉伯数字字符串列表（去重保序）。"""
    if not query:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _QUERY_ARTICLE_RE.finditer(query):
        n = _normalize_article_no(m.group(1))
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out
