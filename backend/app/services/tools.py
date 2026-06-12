"""
工具调用系统 - 真实 API 接入。

工具列表:
- calculator:  安全数学表达式求值
- get_time:    获取当前时间
- weather:     Open-Meteo 实时天气（零密钥）
- translate:   百度翻译
- search:      Tavily Search
- kb_search:   法律条文知识库检索（ChromaDB + bge-small-zh）
"""
from __future__ import annotations

import ast
import hashlib
import logging
import operator
import random
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import httpx

from app.core.config import settings
from app.services.rag.retriever import format_for_llm, retrieve

logger = logging.getLogger(__name__)


# ===== 安全运算器（取代 eval）=====
_MAX_AST_NODES = 200
_MAX_DEPTH = 50
_MAX_ABS_VALUE = 1e15
_BIN_OPS: Dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS: Dict[type, Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _safe_calc(node: ast.AST, depth: int = 0) -> float:
    if depth > _MAX_DEPTH:
        raise ValueError(f"表达式嵌套过深（>{_MAX_DEPTH}）")
    if isinstance(node, ast.Expression):
        return _safe_calc(node.body, depth + 1)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        if abs(node.value) > _MAX_ABS_VALUE:
            raise ValueError(f"数值超出范围（>{_MAX_ABS_VALUE:.0e}）")
        return node.value
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise ValueError(f"不支持的运算符: {op_type.__name__}")
        left = _safe_calc(node.left, depth + 1)
        right = _safe_calc(node.right, depth + 1)
        if op_type is ast.Pow and (isinstance(right, int) and abs(right) > 1000):
            raise ValueError("指数过大（>1000）")
        return _BIN_OPS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"不支持的一元运算符: {op_type.__name__}")
        return _UNARY_OPS[op_type](_safe_calc(node.operand, depth + 1))
    raise ValueError(f"不支持的语法节点: {type(node).__name__}")


def safe_calculate(expression: str) -> float:
    if not expression or len(expression) > 1000:
        raise ValueError("表达式为空或过长")
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"表达式语法错误: {e.msg}")
    node_count = sum(1 for _ in ast.walk(parsed))
    if node_count > _MAX_AST_NODES:
        raise ValueError(f"表达式过于复杂（>{_MAX_AST_NODES} 节点）")
    return _safe_calc(parsed)


# ===== 工具实现 =====

def _calc(expression: str) -> str:
    try:
        return f"计算结果: {safe_calculate(expression)}"
    except Exception as e:
        return f"计算错误: {e}"


def _time() -> str:
    return datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")


# WMO Weather interpretation codes → 中文文案
# 参考 https://open-meteo.com/en/docs 官方 code 表
_WEATHER_CODE_ZH: Dict[int, str] = {
    0: "晴",
    1: "少云",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "中毛毛雨",
    55: "大毛毛雨",
    56: "小冻毛毛雨",
    57: "大冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "小冻雨",
    67: "大冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "米雪",
    80: "小阵雨",
    81: "中阵雨",
    82: "大阵雨",
    85: "小阵雪",
    86: "大阵雪",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴大冰雹",
}


async def _weather(city: str = "北京") -> str:
    """Open-Meteo 实时天气查询（零密钥、零配置、一万次/天免费）。

    Geocoding 流程: 先 language=zh 搜,搜不到再 language=en 回退一次
    （覆盖拼音 / 英文城市名,如 "Tokyo"、"Yokohama"、"New York"）。
    注意: 中文名 "东京" 仍会优先匹配到中国辽宁东京镇,
    日本东京需要输入 "Tokyo" / "日本东京" 才能稳定命中。
    """
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            # 第一步: 城市名 → 经纬度 (Open-Meteo Geocoding,免费无 key)
            gdata = {}
            for lang in ("zh", "en"):
                g_r = await c.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1, "language": lang, "format": "json"},
                )
                g_r.raise_for_status()
                gdata = g_r.json() or {}
                if gdata.get("results"):
                    break
            results = gdata.get("results") or []
            if not results:
                return f"未找到城市「{city}」"
            lat = results[0]["latitude"]
            lng = results[0]["longitude"]
            resolved_name = results[0].get("name", city)
            country = results[0].get("country") or results[0].get("admin1") or ""
            display = (
                f"{resolved_name}({country})"
                if country and country != resolved_name
                else resolved_name
            )

            # 第二步: 经纬度 → 实时天气
            w_r = await c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lng,
                    "current": ",".join([
                        "temperature_2m",
                        "relative_humidity_2m",
                        "apparent_temperature",
                        "weather_code",
                        "wind_speed_10m",
                        "wind_direction_10m",
                    ]),
                    "wind_speed_unit": "kmh",
                    "timezone": "auto",
                },
            )
            w_r.raise_for_status()
            cur = (w_r.json() or {}).get("current") or {}
            code = cur.get("weather_code")
            text = _WEATHER_CODE_ZH.get(code, f"天气码{code}")
            return (
                f"{display}天气: {text}，"
                f"温度{cur.get('temperature_2m')}℃，"
                f"体感{cur.get('apparent_temperature')}℃，"
                f"湿度{cur.get('relative_humidity_2m')}%，"
                f"风速{cur.get('wind_speed_10m')}km/h"
            )
    except httpx.HTTPError as e:
        logger.exception("weather query http error")
        return f"天气查询出错（{type(e).__name__}: {e or '无详细信息'}）"
    except Exception as e:
        logger.exception("weather query error")
        return f"天气查询出错（{type(e).__name__}: {e or '无详细信息'}）"


_LANG_MAP: dict[str, str] = {
    "中文": "zh", "英文": "en", "日语": "jp",
    "韩语": "kor", "法语": "fra", "德语": "de", "西班牙语": "spa",
    "俄语": "ru", "葡萄牙语": "pt", "意大利语": "it",
    "zh": "zh", "en": "en", "jp": "jp", "kor": "kor",
}


async def _translate(text: str, to_lang: str = "中文") -> str:
    """百度翻译 API。"""
    appid = settings.BAIDU_APPID
    secret = settings.BAIDU_SECRET
    if not appid or not secret:
        logger.warning("BAIDU_APPID / BAIDU_SECRET 未配置")
        return f"翻译暂不可用（API Key 未配置）"

    target = _LANG_MAP.get(to_lang, "zh")
    salt = str(random.randint(32768, 65536))
    sign = hashlib.md5(f"{appid}{text}{salt}{secret}".encode()).hexdigest()

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://api.fanyi.baidu.com/api/trans/vip/translate",
                params={
                    "q": text, "from": "auto", "to": target,
                    "appid": appid, "salt": salt, "sign": sign,
                },
            )
            data = r.json()
            if "trans_result" in data:
                dst = data["trans_result"][0]["dst"]
                return f"翻译结果({to_lang}): {dst}"
            err = data.get("error_msg", str(data))
            return f"翻译失败: {err}"
    except Exception as e:
        logger.exception("translate error")
        return f"翻译出错: {e}"


async def _search(query: str) -> str:
    """Tavily Search API - AI 专用搜索引擎。"""
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        logger.warning("TAVILY_API_KEY 未配置")
        return f"搜索暂不可用（API Key 未配置）"

    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                },
            )
            data = r.json()
            results = data.get("results", [])
            if not results:
                return f"未找到「{query}」相关信息"
            lines = []
            for i, res in enumerate(results[:3], 1):
                title = res.get("title", "无标题")
                content = res.get("content", "")[:300]
                url = res.get("url", "")
                lines.append(f"{i}. {title}\n   {content}\n   来源: {url}")
            return "\n\n".join(lines)
    except Exception as e:
        logger.exception("search error")
        return f"搜索出错: {e}"


async def _kb_search(
    query: str,
    law_code: str | None = None,
    doc_type: str | None = None,
    include_repealed: bool = False,
    top_k: int = 5,
) -> str:
    """法律条文知识库检索。ChromaDB + bge-small-zh 嵌入，零密钥。

    三层检索:
    1) 用户问题含 "第N条" → 按 (law_code, article_no) 直接命中 MySQL，绕过向量；
    2) 自然语言问题 → 向量召回，默认 filter is_current=True；
    3) 命中释义/场景 chunk 时，关联拉取同条法源正文一并返回。

    - query: 用户原始问题（可自然语言/口语化）
    - law_code: 可选限定法律名称（如 "民法典"、"刑法"）
    - doc_type: 可选限定文档类型（statute 正文 / interpretation 司法解释 / commentary 释义 / ...）
    - include_repealed: 默认 False 只查现行；用户主动问新旧对比时置 True
    - top_k: 返回 chunk 数（1-10）

    未命中时 format_for_llm 返回硬阻止串，调用方（LLM）必须告知用户
    "未检索到对应法律条款"，禁止编造法条号。
    """
    try:
        chunks = await retrieve(
            query,
            law_code=law_code,
            doc_type=doc_type,
            top_k=top_k,
            include_repealed=include_repealed,
        )
    except Exception as e:
        logger.exception("kb_search error")
        return f"知识库检索出错: {e}"
    return format_for_llm(chunks)


# ===== 注册中心 =====
class ToolDefinition:
    """OpenAI / Ark 兼容的工具定义。"""

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: Dict[str, Any],
        is_async: bool = False,
    ):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters
        self.is_async = is_async

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(ToolDefinition(
            name="calculator",
            description="计算数学表达式，支持 + - * / // % ** 和括号",
            func=_calc,
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，如 '2+3*4'"}
                },
                "required": ["expression"],
            },
        ))
        self.register(ToolDefinition(
            name="get_time",
            description="获取当前日期和时间",
            func=lambda **kw: _time(),
            parameters={"type": "object", "properties": {}},
        ))
        self.register(ToolDefinition(
            name="weather",
            description="查询指定城市的实时天气（温度、湿度、风向等）",
            func=_weather,
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如 '北京'、'上海'"}
                },
                "required": ["city"],
            },
            is_async=True,
        ))
        self.register(ToolDefinition(
            name="translate",
            description="翻译文本到指定语言",
            func=_translate,
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "待翻译文本"},
                    "to_lang": {"type": "string", "description": "目标语言，如 '英文'、'日语'"},
                },
                "required": ["text", "to_lang"],
            },
            is_async=True,
        ))
        self.register(ToolDefinition(
            name="search",
            description="搜索互联网获取最新信息。当你不确定答案或需要实时信息时使用。",
            func=_search,
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，用中文"}
                },
                "required": ["query"],
            },
            is_async=True,
        ))
        self.register(ToolDefinition(
            name="kb_search",
            description=(
                "中国法律条文知识库检索。**用户提出任何法律问题（包括「怎么办」"
                "「能不能」「违不违法」「公司能否扣工资」这类口语化提问）都必须先调用本工具**。"
                "返回 [1][2] 引用块（含法律名/条号/版本/现行状态）；"
                "**回答必须严格基于这些素材，未命中时复述工具返回的硬阻止串告知用户"
                "「未检索到对应法律条款」，禁止凭记忆生成法条号/条文/司法解释/立法理由**。"
                "条款引用必须复述工具返回的原文，并附 [来源N]。"
            ),
            func=_kb_search,
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用户问题原文。含 '第N条' 时会走精准命中；自然语言提问走向量检索。",
                    },
                    "law_code": {
                        "type": "string",
                        "enum": [
                            "民法典", "刑法", "劳动法", "劳动合同法", "治安管理处罚法",
                            "个人信息保护法", "网络安全法", "数据安全法", "宪法",
                            "行政处罚法", "民事诉讼法", "刑事诉讼法", "公司法", "其他",
                        ],
                        "description": "可选：限定具体法律名称。问得明确（如'劳动合同法关于试用期'）时必填。",
                    },
                    "doc_type": {
                        "type": "string",
                        "enum": [
                            "statute", "interpretation", "commentary", "scenario",
                            "boundary", "diff", "repeal_note", "other",
                        ],
                        "description": "可选：限定文档类型。statute=法律正文；interpretation=司法解释；"
                                       "commentary=逐条释义；scenario=场景适用；boundary=适用边界；"
                                       "diff=新旧对比；repeal_note=废止标注。",
                    },
                    "include_repealed": {
                        "type": "boolean",
                        "default": False,
                        "description": "是否纳入已废止版本。仅当用户主动比较新旧版/查询历史法条时置 true。",
                    },
                    "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
            },
            is_async=True,
        ))

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def all(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def openai_schemas(self) -> List[Dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tool = self.get(name)
        if not tool:
            return {"ok": False, "error": f"未知工具: {name}"}
        try:
            result = tool.func(**(arguments or {}))
            return {"ok": True, "result": str(result)}
        except TypeError as e:
            return {"ok": False, "error": f"参数错误: {e}"}
        except Exception as e:
            return {"ok": False, "error": f"执行错误: {e}"}

    async def execute_async(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行工具（支持 async 函数）。"""
        tool = self.get(name)
        if not tool:
            return {"ok": False, "error": f"未知工具: {name}"}
        try:
            if tool.is_async:
                result = await tool.func(**(arguments or {}))
            else:
                result = tool.func(**(arguments or {}))
            return {"ok": True, "result": str(result)}
        except TypeError as e:
            return {"ok": False, "error": f"参数错误: {e}"}
        except Exception as e:
            return {"ok": False, "error": f"执行错误: {e}"}


tool_registry = ToolRegistry()
