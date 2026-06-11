"""
ToolRegistry 基本行为测试
"""
import pytest

from app.services.tools import tool_registry


class TestToolRegistry:
    def test_builtin_tools_registered(self):
        names = {t.name for t in tool_registry.all()}
        assert {"calculator", "get_time", "weather", "translate", "search"} <= names

    def test_execute_calculator(self):
        result = tool_registry.execute("calculator", {"expression": "2 + 3 * 4"})
        assert result["ok"] is True
        assert "14" in result["result"]

    def test_execute_unknown(self):
        result = tool_registry.execute("nonexistent", {})
        assert result["ok"] is False
        assert "未知工具" in result["error"]

    def test_execute_bad_args(self):
        # calculator 缺 expression 应报错
        result = tool_registry.execute("calculator", {})
        assert result["ok"] is False

    def test_schemas_compatible_with_openai(self):
        schemas = tool_registry.openai_schemas()
        assert isinstance(schemas, list)
        for s in schemas:
            assert s["type"] == "function"
            assert "function" in s
            assert "name" in s["function"]
            assert "description" in s["function"]
            assert "parameters" in s["function"]
