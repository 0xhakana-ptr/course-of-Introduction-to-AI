import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..services.run_action.types import RunActionError


logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RunActionError)
    async def handle_run_action_error(request: Request, exc: RunActionError):
        logger.warning(
            "Run action error: path=%s status=%s detail=%s",
            request.url.path,
            exc.status_code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(PermissionError)
    async def handle_permission_error(request: Request, exc: PermissionError):
        logger.warning(
            "Permission error: path=%s detail=%s",
            request.url.path,
            str(exc),
        )
        return JSONResponse(
            status_code=403,
            content={"detail": str(exc) or "permission denied"},
        )
