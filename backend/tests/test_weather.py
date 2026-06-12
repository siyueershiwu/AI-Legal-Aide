"""
测试 _weather（Open-Meteo 一站式）的三个分支 + 国际城市回退。

覆盖:
- 成功路径（中文命中,zh 一次返回 results）
- 国际城市回退（zh 返回空,改用 en 搜）
- 城市找不到（zh + en 都没结果）
- HTTP 网络错（httpx.HTTPError 被兜住,不抛给上层）
- 未知 weather_code（不崩溃,显示 "天气码N"）
- raise_for_status 报错（4xx/5xx 视为网络错）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import httpx
import pytest

from app.services.tools import _WEATHER_CODE_ZH, _weather


# ============================================================================
# Fakes
# ============================================================================
class _JsonResponse:
    """模拟 httpx.Response,支持 raise_for_status() 和 .json()."""

    def __init__(
        self,
        status_code: int = 200,
        body: Optional[Dict[str, Any]] = None,
        raise_on_status: Optional[Exception] = None,
    ) -> None:
        self.status_code = status_code
        self._body = body or {}
        self._raise_on_status = raise_on_status

    def raise_for_status(self) -> None:
        if self._raise_on_status is not None:
            raise self._raise_on_status

    def json(self) -> Dict[str, Any]:
        return self._body


class _FakeAsyncClient:
    """模拟 httpx.AsyncClient。

    用法:
        client = _FakeAsyncClient()
        client.queue(_JsonResponse(200, {"results": [...]}))   # geocoding zh
        client.queue(_JsonResponse(200, {"results": [...]}))   # geocoding en (回退)
        client.queue(_JsonResponse(200, {"current": {...}}))   # forecast
        monkeypatch.setattr("app.services.tools.httpx.AsyncClient", lambda *a, **kw: client)
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._queue: List[_JsonResponse] = []
        self.calls: List[Dict[str, Any]] = []  # 记录所有 (url, params) 用于断言
        self._connect_error: Optional[Exception] = None  # 模拟 get() 抛错

    def queue(self, response: _JsonResponse) -> "_FakeAsyncClient":
        self._queue.append(response)
        return self

    def raise_on_get(self, exc: Exception) -> None:
        """让下一次 get() 直接抛错(模拟网络层错误,进不到 raise_for_status)。"""
        self._connect_error = exc

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> _JsonResponse:
        self.calls.append({"url": url, "params": dict(params or {})})
        if self._connect_error is not None:
            exc = self._connect_error
            self._connect_error = None  # 只抛一次,避免死循环
            raise exc
        if not self._queue:
            raise AssertionError(
                f"unexpected get: {url} {params} (queue empty; queued {len(self.calls) - 1} calls already)"
            )
        return self._queue.pop(0)


def _install_client(monkeypatch: pytest.MonkeyPatch) -> _FakeAsyncClient:
    """patch httpx.AsyncClient,返回 fake client 让测试自己 queue 响应。"""
    client = _FakeAsyncClient()
    monkeypatch.setattr("app.services.tools.httpx.AsyncClient", lambda *a, **kw: client)
    return client


def _ok_geo(results: List[Dict[str, Any]]) -> _JsonResponse:
    return _JsonResponse(200, {"results": results})


def _empty_geo() -> _JsonResponse:
    return _JsonResponse(200, {"results": []})


def _ok_forecast(
    *,
    code: int = 0,
    temp: float = 25.0,
    feels: float = 25.5,
    humidity: int = 60,
    wind: float = 5.0,
) -> _JsonResponse:
    return _JsonResponse(200, {
        "current": {
            "time": "2026-06-12T14:00",
            "temperature_2m": temp,
            "apparent_temperature": feels,
            "relative_humidity_2m": humidity,
            "weather_code": code,
            "wind_speed_10m": wind,
            "wind_direction_10m": 90,
        },
    })


# ============================================================================
# 成功路径
# ============================================================================
@pytest.mark.asyncio
async def test_weather_success_chinese_city(monkeypatch):
    """中文城市,zh 一次命中。"""
    client = _install_client(monkeypatch)
    client.queue(_ok_geo([{
        "latitude": 39.9042,
        "longitude": 116.4074,
        "name": "北京",
        "country": "中国",
    }]))
    client.queue(_ok_forecast(code=0, temp=32.5, humidity=28))

    result = await _weather("北京")

    # 断言: 输出含城市名 + 中文天气 + 数值
    assert "北京" in result
    assert "中国" in result
    assert "晴" in result  # code 0
    assert "32.5" in result
    assert "28" in result  # 湿度

    # 断言: 只调了 1 次 geocoding（zh 命中即 break）和 1 次 forecast
    assert len(client.calls) == 2
    geo_call = client.calls[0]
    assert geo_call["url"] == "https://geocoding-api.open-meteo.com/v1/search"
    assert geo_call["params"]["name"] == "北京"
    assert geo_call["params"]["language"] == "zh"
    assert client.calls[1]["url"] == "https://api.open-meteo.com/v1/forecast"


# ============================================================================
# 国际城市回退
# ============================================================================
@pytest.mark.asyncio
async def test_weather_international_fallback_zh_empty_then_en(monkeypatch):
    """zh 返回空,自动回退到 en 搜一次。"""
    client = _install_client(monkeypatch)
    client.queue(_empty_geo())  # zh 无结果
    client.queue(_ok_geo([{    # en 命中
        "latitude": 35.6762,
        "longitude": 139.6503,
        "name": "Tokyo",
        "country": "Japan",
    }]))
    client.queue(_ok_forecast(code=1, temp=26.3, feels=27.5))

    result = await _weather("Tokyo")

    assert "Tokyo" in result
    assert "Japan" in result
    assert "少云" in result  # code 1
    assert "26.3" in result

    # 断言: geocoding 调了 2 次（zh + en）
    assert client.calls[0]["params"]["language"] == "zh"
    assert client.calls[1]["params"]["language"] == "en"
    assert client.calls[2]["url"] == "https://api.open-meteo.com/v1/forecast"


# ============================================================================
# 城市找不到
# ============================================================================
@pytest.mark.asyncio
async def test_weather_city_not_found_both_languages(monkeypatch):
    """zh + en 都没有 → 友好提示,不调 forecast。"""
    client = _install_client(monkeypatch)
    client.queue(_empty_geo())  # zh
    client.queue(_empty_geo())  # en 回退

    result = await _weather("不存在的城市xyz123")

    assert "未找到城市" in result
    assert "不存在的城市xyz123" in result

    # 关键: 没有调 forecast（找不到城市省一次 API call）
    assert len(client.calls) == 2
    assert all("geocoding-api" in c["url"] for c in client.calls)


# ============================================================================
# 网络错
# ============================================================================
@pytest.mark.asyncio
async def test_weather_http_error_is_swallowed(monkeypatch):
    """httpx.HTTPError 被兜住,返回友好错误信息,不抛给上层（LLM 工具调用不崩）。"""
    client = _install_client(monkeypatch)
    client.raise_on_get(httpx.ConnectError("DNS resolution failed", request=MagicMock()))

    result = await _weather("北京")

    assert "天气查询出错" in result
    assert "ConnectError" in result  # 错误类型带出来便于排查
    # 关键: 不抛异常,函数正常 return 字符串


@pytest.mark.asyncio
async def test_weather_raise_for_status_4xx(monkeypatch):
    """geocoding 返回 4xx → raise_for_status 抛 HTTPStatusError,被兜住。"""
    client = _install_client(monkeypatch)
    # httpx.HTTPStatusError 是 HTTPError 子类,会被 except httpx.HTTPError 接住
    response = _JsonResponse(429, {})
    response.request = MagicMock()
    client.queue(_JsonResponse(
        429, {},
        raise_on_status=httpx.HTTPStatusError(
            "429 Too Many Requests", request=MagicMock(), response=response,
        ),
    ))

    result = await _weather("北京")

    assert "天气查询出错" in result
    assert "HTTPStatusError" in result


# ============================================================================
# 未知 weather_code
# ============================================================================
@pytest.mark.asyncio
async def test_weather_unknown_weather_code_does_not_crash(monkeypatch):
    """forecast 返回一个映射表里没有的 code（比如 API 升级加了新值），不应崩。"""
    client = _install_client(monkeypatch)
    client.queue(_ok_geo([{
        "latitude": 0, "longitude": 0, "name": "测试地", "country": "Test",
    }]))
    client.queue(_ok_forecast(code=999))  # 999 不在表里

    result = await _weather("测试地")

    assert "测试地" in result
    assert "天气码999" in result  # 优雅降级


@pytest.mark.asyncio
async def test_weather_code_mapping_covers_common_cases():
    """WMO code 表本身的关键值不能丢（防回归）。"""
    assert _WEATHER_CODE_ZH[0] == "晴"
    assert _WEATHER_CODE_ZH[3] == "阴"
    assert _WEATHER_CODE_ZH[61] == "小雨"
    assert _WEATHER_CODE_ZH[63] == "中雨"
    assert _WEATHER_CODE_ZH[65] == "大雨"
    assert _WEATHER_CODE_ZH[71] == "小雪"
    assert _WEATHER_CODE_ZH[95] == "雷暴"
    # 至少 25 条
    assert len(_WEATHER_CODE_ZH) >= 25
