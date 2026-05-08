import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from .error_responses import build_api_error_response
from ..services.run_action.types import RunActionError


logger = logging.getLogger(__name__)


def _normalize_http_error_detail(detail: object) -> tuple[str | None, str, object | None]:
    if isinstance(detail, dict):
        code_value = detail.get("code")
        code = str(code_value).strip() if code_value is not None else None
        message_value = detail.get("message")
        if message_value is None:
            message_value = detail.get("detail")
        message = str(message_value).strip() if message_value is not None else ""
        return code or None, message or "request failed", detail.get("details")

    message = str(detail).strip() if detail is not None else ""
    return None, message or "request failed", None


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RunActionError)
    async def handle_run_action_error(request: Request, exc: RunActionError):
        logger.warning(
            "Run action error: path=%s status=%s code=%s detail=%s",
            request.url.path,
            exc.status_code,
            exc.code,
            exc.message,
        )
        return build_api_error_response(
            exc.status_code,
            message=exc.message,
            code=exc.code,
            path=request.url.path,
        )

    @app.exception_handler(PermissionError)
    async def handle_permission_error(request: Request, exc: PermissionError):
        logger.warning(
            "Permission error: path=%s detail=%s",
            request.url.path,
            str(exc),
        )
        return build_api_error_response(
            403,
            message=str(exc) or "permission denied",
            code="permission_denied",
            path=request.url.path,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        code, message, details = _normalize_http_error_detail(exc.detail)
        logger.warning(
            "HTTP exception: path=%s status=%s code=%s detail=%s",
            request.url.path,
            exc.status_code,
            code,
            message,
        )
        return build_api_error_response(
            exc.status_code,
            message=message,
            code=code,
            path=request.url.path,
            details=details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(request: Request, exc: RequestValidationError):
        logger.warning(
            "Validation error: path=%s errors=%s",
            request.url.path,
            exc.errors(),
        )
        return build_api_error_response(
            422,
            message="请求参数校验失败。",
            code="validation_error",
            path=request.url.path,
            details=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        logger.exception(
            "Unexpected exception: path=%s type=%s",
            request.url.path,
            exc.__class__.__name__,
        )
        return build_api_error_response(
            500,
            message="服务器内部错误。",
            code="internal_error",
            path=request.url.path,
        )
