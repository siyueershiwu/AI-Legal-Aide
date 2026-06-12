"""从『国家法律法规数据库』(flk.npc.gov.cn) 抓取公开法律文本并入库。

⚠ 重要前提
===========
flk.npc.gov.cn 的公开数据接口并不稳定（接口路径、签名参数、反爬策略随时间
变化），本脚本提供的「在线抓取」模式是一份**参考实现**，遇到 403/验证码/接口
变动时大概率需要现场调整；遇到这种情况请改用 --from-files 模式，把从官网
复制的 markdown 文本放到 data/npc_laws/ 目录后跑脚本入库。

用法
====

准备 Python 环境（项目根目录 backend/）：

    cd backend
    python -m scripts.fetch_npc_laws --help
    python -m scripts.fetch_npc_laws --list-seed        # 打印内置种子清单
    python -m scripts.fetch_npc_laws --from-files      # 扫 data/npc_laws/*.md 入库
    python -m scripts.fetch_npc_laws --from-api         # 在线抓取（需联网，参考实现）

环境变量（已与后端共用 .env 加载）：
    DATABASE_URL    MySQL DSN（异步 aiomysql）
    MINIO_*         MinIO 配置

设计
====
- 单一入口 main()，通过 argparse 分发到两个子命令，互不耦合
- 抓取器有 UA、QPS 限流、指数退避重试，单 IP 限速 0.5 req/s
- 入库走 ingest_file()，复用项目既有的按"第N条"切分 + ChromaDB 写入
  链路，metadata 全部填 law_code/doc_type/version/is_current/effective_date
- 单文件失败不中断整体流程；每个文件落地一个 .md 缓存到 data/npc_laws/cache/
  方便二次复用
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Optional

try:
    import httpx
except ImportError:  # pragma: no cover
    print("缺少 httpx，请先 pip install httpx", file=sys.stderr)
    raise

# ---- 让脚本能 import app.* ----
# python -m scripts.fetch_npc_laws 时，sys.path[0] 已是 backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.knowledge import (  # noqa: E402
    DOC_TYPE_VALUES,
    LAW_CODE_VALUES,
)
from app.repositories.file_repo import FileRepository  # noqa: E402
from app.services.rag.ingest import IngestError, ingest_file  # noqa: E402
from app.services.storage import storage  # noqa: E402

logger = logging.getLogger("fetch_npc_laws")

# ============================================================
# 种子清单（先用最少的人力覆盖高频法律；其它可手动补 data/npc_laws/）
# 字段：law_code（必须命中项目内枚举）、doc_type、title、官方公开 URL
# 留空的 url：脚本会跳过 + 提示用户补充，不会报错。
# ============================================================
SEED_LAWS: list[dict[str, str]] = [
    {
        "law_code": "民法典",
        "doc_type": "statute",
        "title": "中华人民共和国民法典",
        "version": "2020",
        "effective_date": "2021-01-01",
        "issuing_body": "全国人民代表大会",
        "id": "ff808081729d1efe01729d50b5c500bf",
    },
    {
        "law_code": "刑法",
        "doc_type": "statute",
        "title": "中华人民共和国刑法",
        "version": "1997 修订 / 2020 修正",
        "effective_date": "1997-10-01",
        "issuing_body": "全国人民代表大会",
        "id": "",  # TODO: 填 flk.npc.gov.cn 法律 ID（详情页 URL 里 ?id= 后那段）
    },
    {
        "law_code": "劳动法",
        "doc_type": "statute",
        "title": "中华人民共和国劳动法",
        "version": "1994 制定 / 2018 修正",
        "effective_date": "1995-01-01",
        "issuing_body": "全国人民代表大会常务委员会",
        "id": "",  # TODO
    },
    {
        "law_code": "劳动合同法",
        "doc_type": "statute",
        "title": "中华人民共和国劳动合同法",
        "version": "2007 制定 / 2012 修正",
        "effective_date": "2008-01-01",
        "issuing_body": "全国人民代表大会常务委员会",
        "id": "",  # TODO
    },
    {
        "law_code": "治安管理处罚法",
        "doc_type": "statute",
        "title": "中华人民共和国治安管理处罚法",
        "version": "2005 制定 / 2012 修正",
        "effective_date": "2006-03-01",
        "issuing_body": "全国人民代表大会常务委员会",
        "id": "",  # TODO
    },
    {
        "law_code": "个人信息保护法",
        "doc_type": "statute",
        "title": "中华人民共和国个人信息保护法",
        "version": "2021",
        "effective_date": "2021-11-01",
        "issuing_body": "全国人民代表大会常务委员会",
        "id": "",  # TODO
    },
    {
        "law_code": "网络安全法",
        "doc_type": "statute",
        "title": "中华人民共和国网络安全法",
        "version": "2016",
        "effective_date": "2017-06-01",
        "issuing_body": "全国人民代表大会常务委员会",
        "id": "",  # TODO
    },
    {
        "law_code": "数据安全法",
        "doc_type": "statute",
        "title": "中华人民共和国数据安全法",
        "version": "2021",
        "effective_date": "2021-09-01",
        "issuing_body": "全国人民代表大会常务委员会",
        "id": "",  # TODO
    },
    {
        "law_code": "宪法",
        "doc_type": "statute",
        "title": "中华人民共和国宪法",
        "version": "1982 制定 / 2018 修正",
        "effective_date": "1982-12-04",
        "issuing_body": "全国人民代表大会",
        "id": "",  # TODO
    },
    {
        "law_code": "行政处罚法",
        "doc_type": "statute",
        "title": "中华人民共和国行政处罚法",
        "version": "1996 制定 / 2021 修订",
        "effective_date": "1996-10-01",
        "issuing_body": "全国人民代表大会常务委员会",
        "id": "",  # TODO
    },
    {
        "law_code": "民事诉讼法",
        "doc_type": "statute",
        "title": "中华人民共和国民事诉讼法",
        "version": "1991 制定 / 2023 修正",
        "effective_date": "1991-04-09",
        "issuing_body": "全国人民代表大会常务委员会",
        "id": "",  # TODO
    },
    {
        "law_code": "刑事诉讼法",
        "doc_type": "statute",
        "title": "中华人民共和国刑事诉讼法",
        "version": "1979 制定 / 2018 修正",
        "effective_date": "1980-01-01",
        "issuing_body": "全国人民代表大会常务委员会",
        "id": "",  # TODO
    },
    {
        "law_code": "公司法",
        "doc_type": "statute",
        "title": "中华人民共和国公司法",
        "version": "1993 制定 / 2023 修订",
        "effective_date": "1994-07-01",
        "issuing_body": "全国人民代表大会常务委员会",
        "id": "",  # TODO
    },
]

# 标记哪些 id 还是占位（脚本会跳过）
_PLACEHOLDER_MARK = "TODO"

# flk.npc.gov.cn 内部 JSON API
# 详情页 https://flk.npc.gov.cn/detail?id=<id>  ←  这个 id 拿来当下面的 bbbs 参数
FLK_DETAIL_API = "https://flk.npc.gov.cn/law-search/search/flfgDetails?bbbs={law_id}"
# 下载端点：返回 JSON，里面 data.url 是带签名的 OBS 链接（X-Amz-Expires=3599，
# ~1 小时有效），需要立刻 GET 拿 docx 流
FLK_DOWNLOAD_API = "https://flk.npc.gov.cn/law-search/download/pc?format=docx&bbbs={law_id}"

# 缓存目录：每个文件按 law_code-slug.md 落地
CACHE_DIR = BACKEND_DIR / "data" / "npc_laws" / "cache"


# ============================================================
# 工具
# ============================================================
def _slugify_law_code(law_code: str) -> str:
    """'中华人民共和国民法典' → 'mfd'（民法典）
    直接用 LAW_CODE_VALUES 里既有的短名做文件名后缀；
    若用户传了枚举之外的法律名，则哈希成短串避免中文路径问题。
    """
    short_map = {
        "民法典": "mfd",
        "刑法": "xf",
        "劳动法": "ldf",
        "劳动合同法": "ldhtf",
        "治安管理处罚法": "zacf",
        "个人信息保护法": "grxxbhf",
        "网络安全法": "wlaqf",
        "数据安全法": "sjaqf",
        "宪法": "xf_xian",   # 与刑法 xf 冲突，加后缀
        "行政处罚法": "xzcf",
        "民事诉讼法": "msssf",
        "刑事诉讼法": "xsssf",
        "公司法": "gsf",
        "其他": "other",
    }
    return short_map.get(law_code, law_code[:8])


def _validate_seed(seed: dict[str, str]) -> None:
    """种子元数据必须在枚举内，否则跳过并警告。"""
    if seed["law_code"] not in LAW_CODE_VALUES:
        raise ValueError(
            f"law_code={seed['law_code']!r} 不在项目支持的法律列表 {LAW_CODE_VALUES}"
        )
    if seed["doc_type"] not in DOC_TYPE_VALUES:
        raise ValueError(
            f"doc_type={seed['doc_type']!r} 不在项目支持的资料类型 {DOC_TYPE_VALUES}"
        )


# 树节点标题里的层级关键词（与 law_chunker.py 里的检测保持一致）
_HIERARCHY_KEYWORDS = (
    "编", "章", "节", "篇", "卷", "附则",
)
# 树根 → 「第N条」叶子之间往往夹杂 「目录」/「附注」 之类的元数据节点
# 它们的 title 不属于正文，应当跳过。判定：不含「第」字 且 children 为空 的
# 小节性 title 视为目录/附注/前言。


def _looks_like_article_node(title: str) -> bool:
    """判断节点标题是否就是「第N条」一类条文标题。

    例：'第一条', '第二百一十六条', '附则', '第一章 总则'  →  True
        '目录', '附注', '中华人民共和国民法典'         →  False
    """
    t = title.strip()
    if not t:
        return False
    # 「第N条」模式
    if t.startswith("第") and ("条" in t):
        return True
    # 章节类（即便没有 children 也要保留作 hierarchy 前缀）
    if any(t.startswith(kw) for kw in _HIERARCHY_KEYWORDS):
        return True
    return False


def _flk_node_to_markdown(node: dict, depth: int = 0) -> str:
    """递归把一个 flk 树节点转 markdown。

    - 标题含「第N条」或「编/章/节/篇」 → 当作层级标题
    - depth 0: 整个树的 root.title 是法律名（不写进 markdown）
    - depth 1+: 标题用 # 标记
    """
    title = (node.get("title") or "").strip()
    children = node.get("children") or []
    lines: list[str] = []

    if depth >= 1 and title:
        # 跳过「目录 / 附注 / 中华人民共和国民法典」之类根级元数据
        if _looks_like_article_node(title) or any(
            title.startswith(kw) for kw in _HIERARCHY_KEYWORDS
        ):
            # 标题层级：# 数 = depth（最大控到 6，markdown 限制）
            level = min(depth, 6)
            lines.append(f"{'#' * level} {title}")
            lines.append("")

    for child in children:
        child_md = _flk_node_to_markdown(child, depth + 1)
        if child_md:
            lines.append(child_md)
    return "\n".join(lines).rstrip() + "\n"


def _flk_json_to_markdown(data: dict) -> str:
    """把 flk API 返回的 data 字典转成完整 markdown 文档。

    - 用 data.title 做 H1
    - 把 content 树展平成 H2..H6
    - 头部加元信息（施行日期 / 公布日期 / 制定机关 / 时效性）
    """
    law_title = (data.get("title") or "").strip()
    parts: list[str] = []
    parts.append(f"# {law_title}")
    parts.append("")
    # 元信息块
    meta_lines: list[str] = []
    sxrq = data.get("sxrq")
    gbrq = data.get("gbrq")
    zdjg = data.get("zdjgName")
    sxx = data.get("sxx")
    if zdjg:
        meta_lines.append(f"- 制定机关：{zdjg}")
    if gbrq:
        meta_lines.append(f"- 公布日期：{gbrq}")
    if sxrq:
        meta_lines.append(f"- 施行日期：{sxrq}")
    if sxx is not None:
        # 0=已废止 1=已修订 3=现行
        status_map = {0: "已废止", 1: "已修订", 2: "尚未生效", 3: "现行有效"}
        meta_lines.append(f"- 效力状态：{status_map.get(sxx, f'状态码{sxx}')}")
    if meta_lines:
        parts.extend(meta_lines)
        parts.append("")
        parts.append("---")
        parts.append("")

    content = data.get("content") or {}
    body = _flk_node_to_markdown(content, depth=0)
    parts.append(body)
    return "\n".join(parts).rstrip() + "\n"


def _docx_to_markdown(docx_bytes: bytes, title_hint: str = "") -> str:
    """把 flk 下载的 .docx 解析成 markdown。

    - paragraph 按顺序拼成正文（每个 para 一段）
    - 跳过完全空行
    - 标题 hint（来自 SEED_LAWS）作为 H1
    """
    try:
        from docx import Document  # python-docx
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "解析 docx 需要 python-docx（已在 requirements.txt 里）。"
            "请 `pip install python-docx` 后重试。"
        ) from e

    import io
    doc = Document(io.BytesIO(docx_bytes))
    parts: list[str] = []
    parts.append(f"# {title_hint}" if title_hint else "# (无标题)")
    parts.append("")
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        parts.append(t)
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


# ============================================================
# 抓取器（UA / QPS / 重试）
# ============================================================
class _TokenBucket:
    """简单 QPS 限流：每秒最多 `rate` 个请求。"""

    def __init__(self, rate: float) -> None:
        self._interval = 1.0 / max(rate, 0.01)
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def take(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


# flk.npc.gov.cn 前端走的是普通 HTML 渲染，公开列表有 JS 异步请求。
# 经验上 front-end 项目里有一组以 /api/ 开头的 JSON 接口（路径随版本会变），
# 此处给一个 best-effort 抓取，失败交给上层重试/降级。
_API_BASE = "https://flk.npc.gov.cn"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class NpcLawFetcher:
    rate: float = 0.5           # 默认 0.5 req/s（≈1 个/2 秒）
    timeout: float = 30.0
    max_retries: int = 3
    backoff: float = 2.0
    bucket: _TokenBucket = field(init=False)

    def __post_init__(self) -> None:
        self.bucket = _TokenBucket(self.rate)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "NpcLawFetcher":
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": _USER_AGENT, "Referer": _API_BASE + "/"},
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch(self, url: str) -> str:
        assert self._client is not None
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            await self.bucket.take()
            try:
                resp = await self._client.get(url)
            except httpx.HTTPError as e:
                last_err = e
                logger.warning("[%d/%d] 网络错误 %s: %s", attempt + 1, self.max_retries, url, e)
            else:
                if resp.status_code == 200:
                    return resp.text
                # 5xx / 429 → 重试；4xx → 直接抛
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_err = RuntimeError(f"HTTP {resp.status_code}")
                    logger.warning(
                        "[%d/%d] %s 暂态 %d，等待重试",
                        attempt + 1, self.max_retries, url, resp.status_code,
                    )
                else:
                    raise RuntimeError(
                        f"GET {url} 失败 status={resp.status_code} body={resp.text[:200]}"
                    )
            if attempt < self.max_retries:
                # 指数退避 + 抖动（0.5x ~ 1.5x）
                sleep_for = self.backoff ** attempt + random.uniform(0, 1)
                await asyncio.sleep(sleep_for)
        raise RuntimeError(f"超过最大重试次数 {self.max_retries}: {url} ({last_err})")

    async def fetch_detail_text(self, url: str) -> str:
        """抓详情页 HTML 并把可见文本近似成 markdown。

        简化做法：去 script/style、合并多余空行。原页面是 Next.js 渲染，
        文本基本都在 <pre> / <div class="..."> 里，re 用宽松匹配。
        """
        html = await self.fetch(url)
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S | re.I)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", "\n", text)
        # 实体替换（极简）
        text = (
            text.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", "\"")
        )
        # 合并空行
        text = re.sub(r"\n[ \t]*\n+", "\n\n", text)
        return text.strip()

    async def fetch_flk_json(self, law_id: str) -> dict:
        """调 flk 内部 JSON API 拿法律全文（结构化树）。"""
        url = FLK_DETAIL_API.format(law_id=law_id)
        body = await self.fetch(url)
        data = json.loads(body)
        if data.get("code") != 200 or "data" not in data:
            raise RuntimeError(
                f"flk API 返回异常: code={data.get('code')}, msg={data.get('msg')!r}"
            )
        return data["data"]

    async def fetch_flk_docx_bytes(self, law_id: str) -> bytes:
        """两步走：① 调 download API 拿带签名的 OBS 链接 ② GET 拿 docx 字节流。

        签名 URL 1 小时有效，脚本一拿到就立刻用，不缓存。
        """
        # Step 1: 拿签名 URL
        api_url = FLK_DOWNLOAD_API.format(law_id=law_id)
        body = await self.fetch(api_url)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"flk download API 返回非 JSON: {body[:200]!r}") from e
        if payload.get("code") != 200 or "data" not in payload:
            raise RuntimeError(
                f"flk download API 异常: code={payload.get('code')}, msg={payload.get('msg')!r}"
            )
        signed_url = payload["data"].get("url")
        if not signed_url:
            raise RuntimeError(f"flk download API 没返回 data.url: {payload['data']!r}")
        # Step 2: 立刻拉 docx（签名会过期）
        logger.info("  → 签名 URL 已获取，下载 docx …")
        return await self.fetch_raw(signed_url)

    async def fetch_raw(self, url: str) -> bytes:
        """低层 GET，拿原始字节流（用于下载 docx 等二进制）。"""
        assert self._client is not None
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            await self.bucket.take()
            try:
                resp = await self._client.get(url)
            except httpx.HTTPError as e:
                last_err = e
                logger.warning("[%d/%d] 网络错误 %s: %s", attempt + 1, self.max_retries, url, e)
            else:
                if resp.status_code == 200:
                    return resp.content
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_err = RuntimeError(f"HTTP {resp.status_code}")
                    logger.warning(
                        "[%d/%d] %s 暂态 %d", attempt + 1, self.max_retries, url, resp.status_code,
                    )
                else:
                    raise RuntimeError(
                        f"GET {url} 失败 status={resp.status_code} body={resp.text[:200]}"
                    )
            if attempt < self.max_retries:
                sleep_for = self.backoff ** attempt + random.uniform(0, 1)
                await asyncio.sleep(sleep_for)
        raise RuntimeError(f"超过最大重试次数 {self.max_retries}: {url} ({last_err})")


# ============================================================
# 入库
# ============================================================
async def _upload_text_to_storage(
    *,
    db: AsyncSession,
    title: str,
    content: str,
    owner_id: Optional[str] = None,
) -> str:
    """把 markdown 文本写到 MinIO + 落 FileRecord，返回 file_id。"""
    file_id = str(uuid.uuid4())
    object_name = f"knowledge/npc_laws/{file_id}.md"
    storage.upload_data(object_name, content.encode("utf-8"), content_type="text/markdown")

    file_repo = FileRepository(db)
    record = await file_repo.create(
        file_id=file_id,
        object_name=object_name,
        file_name=f"{title}.md",
        content_type="text/markdown",
        size=len(content.encode("utf-8")),
        user_id=owner_id,
    )
    await db.commit()
    return record.id


async def _ingest_one(
    *,
    db: AsyncSession,
    seed: dict[str, str],
    markdown: str,
    is_repealed: bool = False,
    owner_id: Optional[str] = None,
) -> str:
    """单条法律入库：写存储 → 写 FileRecord → 调 ingest_file。"""
    _validate_seed(seed)
    file_id = await _upload_text_to_storage(
        db=db, title=seed["title"], content=markdown, owner_id=owner_id,
    )
    try:
        effective = date.fromisoformat(seed["effective_date"]) if seed.get("effective_date") else None
    except ValueError:
        logger.warning("seed.effective_date 格式错: %r, 置为 None", seed.get("effective_date"))
        effective = None

    doc = await ingest_file(
        db,
        file_id=file_id,
        title=seed["title"],
        law_code=seed["law_code"],
        doc_type=seed["doc_type"],
        version=seed.get("version", "current"),
        is_current=not is_repealed,
        effective_date=effective,
        repealed_date=date.today() if is_repealed else None,
        issuing_body=seed.get("issuing_body") or None,
        article_range=None,  # 由 law_chunker 自动推算（写入 metadata 即可）
        source_type="manual",
        owner_id=owner_id,
    )
    await db.commit()
    return doc.id


# ============================================================
# 子命令
# ============================================================
async def cmd_list_seed(_args: argparse.Namespace) -> int:
    print(f"# 内置种子 {len(SEED_LAWS)} 条")
    print(json.dumps(SEED_LAWS, ensure_ascii=False, indent=2))
    return 0


async def cmd_from_files(args: argparse.Namespace) -> int:
    """扫 data/npc_laws/<law_code-slug>.md 入库，文件名 = slug，标题从文件首行读。"""
    src_dir = (BACKEND_DIR / args.dir).resolve() if not Path(args.dir).is_absolute() else Path(args.dir)
    if not src_dir.is_dir():
        logger.error("目录不存在: %s", src_dir)
        return 2

    # slug → law_code 反查
    slug_to_law = {f"{_slugify_law_code(s['law_code'])}.md": s for s in SEED_LAWS}
    files = sorted(src_dir.glob("*.md"))
    if not files:
        logger.warning("目录里没有 .md 文件: %s", src_dir)
        return 1

    success = 0
    failed: list[tuple[Path, str]] = []
    for fp in files:
        seed = slug_to_law.get(fp.name)
        if seed is None:
            # 兜底：未匹配的走 "其他"，doc_type 默认为 statute
            logger.warning("%s 不在种子清单，按 '其他' 入库", fp.name)
            seed = {
                "law_code": "其他",
                "doc_type": "statute",
                "title": fp.stem,
                "version": "未指定",
            }
        try:
            content = fp.read_text(encoding="utf-8")
            if not content.strip():
                raise RuntimeError("文件内容为空")
            async with AsyncSessionLocal() as db:
                doc_id = await _ingest_one(
                    db=db, seed=seed, markdown=content, is_repealed=args.repealed,
                )
            logger.info("✓ %s → %s", fp.name, doc_id)
            success += 1
        except (IngestError, Exception) as e:  # noqa: BLE001
            logger.error("✗ %s: %s", fp.name, e)
            failed.append((fp, str(e)))

    logger.info("\n==== 汇总 ====")
    logger.info("成功 %d, 失败 %d", success, len(failed))
    for fp, err in failed:
        logger.info("  失败: %s — %s", fp.name, err)
    return 0 if not failed else 3


async def cmd_from_api(args: argparse.Namespace) -> int:
    """在线抓取（参考实现）。

    实际可用性依赖 flk.npc.gov.cn 的接口稳定性；若全部失败请改用 --from-files。
    抓到的 markdown 落到 CACHE_DIR，下次重跑会复用缓存（除非 --no-cache）。
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    seeds = SEED_LAWS
    if args.only:
        wanted = set(args.only)
        seeds = [s for s in SEED_LAWS if s["law_code"] in wanted]
        if not seeds:
            logger.error("--only 没匹配到任何 seed: %s", args.only)
            return 2

    success = 0
    failed: list[tuple[str, str]] = []
    skipped: list[str] = []
    async with NpcLawFetcher(rate=args.rate, max_retries=args.retries) as fetcher:
        for seed in seeds:
            slug = _slugify_law_code(seed["law_code"])
            law_id = (seed.get("id") or "").strip()
            if not law_id or _PLACEHOLDER_MARK in law_id:
                logger.warning(
                    "⊘ 跳过 %s：id 字段为空（请到 SEED_LAWS 补真实 flk.npc.gov.cn 法律 ID）",
                    seed["title"],
                )
                skipped.append(seed["title"])
                continue
            cache_fp = CACHE_DIR / f"{slug}.md"
            if cache_fp.exists() and not args.no_cache:
                markdown = cache_fp.read_text(encoding="utf-8")
                logger.info("⟳ 复用缓存 %s (%d 字符)", cache_fp.name, len(markdown))
            else:
                try:
                    logger.info("→ 抓取 flk API law_id=%s …", law_id)
                    docx_bytes = await fetcher.fetch_flk_docx_bytes(law_id)
                    markdown = _docx_to_markdown(docx_bytes, title_hint=seed["title"])
                except Exception as e:  # noqa: BLE001
                    logger.error("✗ 抓取失败 %s: %s", seed["title"], e)
                    failed.append((seed["title"], str(e)))
                    continue
                cache_fp.write_text(markdown, encoding="utf-8")
                logger.info("✓ 落缓存 %s (%d 字符)", cache_fp.name, len(markdown))

            try:
                async with AsyncSessionLocal() as db:
                    doc_id = await _ingest_one(
                        db=db, seed=seed, markdown=markdown, is_repealed=args.repealed,
                    )
                logger.info("✓ 入库 %s → %s", seed["title"], doc_id)
                success += 1
            except (IngestError, Exception) as e:  # noqa: BLE001
                logger.error("✗ 入库失败 %s: %s", seed["title"], e)
                failed.append((seed["title"], str(e)))

    logger.info("\n==== 汇总 ====")
    logger.info("成功 %d, 失败 %d, 跳过 %d", success, len(failed), len(skipped))
    for t, e in failed:
        logger.info("  失败: %s — %s", t, e)
    for t in skipped:
        logger.info("  跳过: %s（url 字段为空，编辑 SEED_LAWS 补全后重跑）", t)
    if not failed and not skipped:
        return 0
    if not failed and skipped:
        return 0  # 跳过不算失败
    return 3


# ============================================================
# argparse
# ============================================================
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="从国家法律法规数据库抓取 / 从本地 md 入库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list-seed", help="打印内置种子清单（13 部法律）")
    p_list.set_defaults(func=cmd_list_seed)

    p_files = sub.add_parser("from-files", help="扫本地 markdown 目录入库")
    p_files.add_argument(
        "--dir", default="data/npc_laws",
        help="相对 backend/ 的目录路径（默认 data/npc_laws/）",
    )
    p_files.add_argument(
        "--repealed", action="store_true", help="把这次入库标为已废止（仅备查）",
    )
    p_files.set_defaults(func=cmd_from_files)

    p_api = sub.add_parser("from-api", help="在线抓取（参考实现，依赖 flk.npc.gov.cn 接口）")
    p_api.add_argument(
        "--only", nargs="+", default=None,
        help="只跑指定 law_code（默认全部种子）",
    )
    p_api.add_argument(
        "--rate", type=float, default=0.5,
        help="每秒最大请求数（默认 0.5）",
    )
    p_api.add_argument(
        "--retries", type=int, default=3, help="失败重试次数",
    )
    p_api.add_argument(
        "--no-cache", action="store_true", help="忽略本地缓存强制重抓",
    )
    p_api.add_argument(
        "--repealed", action="store_true", help="把这次入库标为已废止（仅备查）",
    )
    p_api.set_defaults(func=cmd_from_api)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(args.func(args))
    except KeyboardInterrupt:
        logger.warning("用户中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
