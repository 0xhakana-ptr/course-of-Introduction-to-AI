from fastapi import APIRouter, Request

from .error_responses import COMMON_ERROR_RESPONSES
from ..core.config import settings
from ..services.run_interface import StartupRecoveryResult


router = APIRouter(
    tags=["health"],
    responses=COMMON_ERROR_RESPONSES,
)


def serialize_startup_recovery(result: StartupRecoveryResult | None) -> dict[str, object] | None:
    if result is None:
        return None
    return {
        "checked_at": result.checked_at,
        "scanned_count": result.scanned_count,
        "recovered_count": result.recovered_count,
        "recovered_run_ids": result.recovered_run_ids,
    }


@router.get("/health")
async def health(request: Request):
    return {
        "ok": True,
        "service": "backend",
        "version": settings.app_version,
        "startup_recovery": serialize_startup_recovery(
            getattr(request.app.state, "startup_recovery", None)
        ),
    }
