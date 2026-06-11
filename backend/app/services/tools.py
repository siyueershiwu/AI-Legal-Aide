"""
工具调用系统 - 完整 OpenAI / Ark 3.0 兼容 schema + 安全的 calculator。
- 删 eval、删 prompt 贴标签
- 工具执行通过 ToolRegistry 中心化
"""
from __future__ import annotations

import ast
import operator
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

# ===== 安全运算器（取代 eval）=====
_MAX_AST_NODES = 200          # 表达式不能超过 200 个 AST 节点
_MAX_DEPTH = 50               # 递归深度不能超过 50
_MAX_ABS_VALUE = 1e15         # 单个数值上限
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
    """递归求值 AST 节点；只接受数字和二元/一元算子"""
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
        # 防止 ** 产生巨型 int（Python 是任意精度，9**9999999 会真算出 95 万位 int）
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
    """数学表达式安全求值。完全脱离 eval。"""
    if not expression or len(expression) > 1000:
        raise ValueError("表达式为空或过长")
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"表达式语法错误: {e.msg}")
    # 节点数限制 - 防 DoS
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


def _weather(city: str = "北京") -> str:
    # TODO: 接入真实天气 API
    return f"{city}今天晴，温度 15-25°C，适宜出行（占位实现）"


def _translate(text: str, to_lang: str = "中文") -> str:
    # TODO: 接入真实翻译 API
    return f"[翻译成{to_lang}]: {text}（占位实现）"


def _search(query: str) -> str:
    # TODO: 接入真实搜索 API
    return f"关于「{query}」: 这是占位搜索结果"


# ===== 注册中心 =====
class ToolDefinition:
    """OpenAI / Ark 3.0 兼容的工具定义"""

    def __init__(self, name: str, description: str, func: Callable, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters

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
        self.register(
            ToolDefinition(
                name="calculator",
                description="计算数学表达式，支持 + - * / // % ** 和括号",
                func=_calc,
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "数学表达式，如 '2+3*4'",
                        }
                    },
                    "required": ["expression"],
                },
            )
        )
        self.register(
            ToolDefinition(
                name="get_time",
                description="获取当前日期和时间",
                func=lambda: _time(),
                parameters={"type": "object", "properties": {}},
            )
        )
        self.register(
            ToolDefinition(
                name="weather",
                description="查询指定城市的天气",
                func=_weather,
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名，如 '北京'"}
                    },
                    "required": ["city"],
                },
            )
        )
        self.register(
            ToolDefinition(
                name="translate",
                description="翻译文本到指定语言",
                func=_translate,
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "待翻译文本"},
                        "to_lang": {
                            "type": "string",
                            "description": "目标语言，如 '英文'",
                        },
                    },
                    "required": ["text", "to_lang"],
                },
            )
        )
        self.register(
            ToolDefinition(
                name="search",
                description="搜索信息",
                func=_search,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
                    },
                    "required": ["query"],
                },
            )
        )

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def all(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def openai_schemas(self) -> List[Dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行工具并返回结构化结果"""
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


tool_registry = ToolRegistry()
