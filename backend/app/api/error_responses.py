from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from ..schemas import ApiErrorInfo, ApiErrorResponse


DEFAULT_ERROR_CODE_BY_STATUS: dict[int, str] = {
    400: "bad_request",
    403: "permission_denied",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    500: "internal_error",
}


COMMON_ERROR_RESPONSES: dict[int, dict[str, object]] = {
    status_code: {"model": ApiErrorResponse}
    for status_code in (400, 403, 404, 409, 422, 500)
}


def default_error_code(status_code: int) -> str:
    return DEFAULT_ERROR_CODE_BY_STATUS.get(status_code, "request_error")


def build_api_error_payload(
    status_code: int,
    *,
    message: str,
    code: str | None = None,
    path: str | None = None,
    details: Any = None,
) -> dict[str, object]:
    response = ApiErrorResponse(
        error=ApiErrorInfo(
            code=code or default_error_code(status_code),
            message=message,
            path=path,
            details=details,
        ),
        detail=message,
    )
    return response.model_dump(mode="json")


def build_api_error_response(
    status_code: int,
    *,
    message: str,
    code: str | None = None,
    path: str | None = None,
    details: Any = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=build_api_error_payload(
            status_code,
            message=message,
            code=code,
            path=path,
            details=details,
        ),
    )


def raise_api_http_error(
    status_code: int,
    *,
    message: str,
    code: str | None = None,
    details: Any = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": code or default_error_code(status_code),
            "message": message,
            "details": details,
        },
    )
