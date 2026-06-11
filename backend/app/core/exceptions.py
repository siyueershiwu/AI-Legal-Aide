"""
全局异常定义 + 处理器注册

约定:
- error.code 一律是字符串（"unauthorized", "not_found", ...）
- HTTP status 走 status_code
- 响应体统一: {success: false, error: {code, message, detail?}}
"""
from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppException(Exception):
    """业务异常基类"""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "app_error",
        detail: Any = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str = "资源"):
        super().__init__(f"{resource}不存在", status.HTTP_404_NOT_FOUND, "not_found")


class PermissionDeniedError(AppException):
    def __init__(self, message: str = "无权访问"):
        super().__init__(message, status.HTTP_403_FORBIDDEN, "permission_denied")


class BadRequestError(AppException):
    def __init__(self, message: str = "请求参数错误"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST, "bad_request")


class UnauthorizedError(AppException):
    """凭据缺失/无效 - 401"""

    def __init__(self, message: str = "未授权"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED, "unauthorized")


def _envelope(code: Any, message: str, status_code: int, detail: Any = None) -> dict:
    body: dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if detail is not None:
        body["error"]["detail"] = detail
    return body


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # 统一 code 为字符串（用 HTTP reason phrase 作稳定代号）
    code_map = {
        400: "bad_request",
        401: "unauthorized",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
    }
    code = code_map.get(exc.status_code, f"http_{exc.status_code}")
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(code, message, exc.status_code),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_envelope("validation_error", "请求参数验证失败", 422, detail=errors),
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(exc.code, exc.message, exc.status_code, detail=exc.detail),
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception path=%s method=%s err=%s\n%s",
        request.url.path,
        request.method,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_envelope("internal_error", "服务器内部错误", 500),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
