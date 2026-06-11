"""
calculator 工具的安全求值测试
"""
import pytest

from app.services.tools import safe_calculate


class TestSafeCalculateBasic:
    """基础算术"""

    def test_add(self):
        assert safe_calculate("1 + 2") == 3

    def test_sub(self):
        assert safe_calculate("10 - 4") == 6

    def test_mul(self):
        assert safe_calculate("3 * 4") == 12

    def test_div(self):
        assert safe_calculate("10 / 4") == 2.5

    def test_floor_div(self):
        assert safe_calculate("10 // 3") == 3

    def test_mod(self):
        assert safe_calculate("10 % 3") == 1

    def test_pow(self):
        assert safe_calculate("2 ** 10") == 1024

    def test_unary(self):
        assert safe_calculate("-5") == -5
        assert safe_calculate("+5") == 5

    def test_precedence(self):
        assert safe_calculate("2 + 3 * 4") == 14
        assert safe_calculate("(2 + 3) * 4") == 20

    def test_float(self):
        assert safe_calculate("0.1 + 0.2") == pytest.approx(0.3)


class TestSafeCalculateRejection:
    """白名单拒绝"""

    def test_empty(self):
        with pytest.raises(ValueError):
            safe_calculate("")

    def test_too_long(self):
        with pytest.raises(ValueError):
            safe_calculate("1" * 2000)

    @pytest.mark.parametrize(
        "expr",
        [
            "__import__('os').system('rm -rf /')",
            "open('/etc/passwd').read()",
            "eval('1+1')",
            "exec('print(1)')",
            "[].__class__",
        ],
    )
    def test_no_name_access(self, expr):
        with pytest.raises(ValueError):
            safe_calculate(expr)


class TestSafeCalculateDoS:
    """资源耗尽防护"""

    def test_huge_pow_blocked(self):
        with pytest.raises((ValueError, OverflowError)):
            safe_calculate("9 ** 9999999")

    def test_deep_nesting_blocked(self):
        # 构造真正递归深的表达式：1+(1+(1+(1+...)))
        expr = "1" + ("+1" * 60)
        with pytest.raises(ValueError):
            safe_calculate(expr)

    def test_too_many_nodes_blocked(self):
        # 构造 300 个常量相加
        expr = " + ".join(["1"] * 300)
        with pytest.raises(ValueError):
            safe_calculate(expr)

    def test_huge_constant_blocked(self):
        with pytest.raises(ValueError):
            safe_calculate(str(10**20))
