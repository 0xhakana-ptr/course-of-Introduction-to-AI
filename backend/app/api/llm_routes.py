from fastapi import APIRouter, Query

from .error_responses import COMMON_ERROR_RESPONSES
from ..llm.client import diagnose_llm
from ..schemas import LLMDiagnosticsResponse


router = APIRouter(
    prefix="/llm",
    tags=["llm"],
    responses=COMMON_ERROR_RESPONSES,
)


@router.get("/diagnostics", response_model=LLMDiagnosticsResponse)
async def llm_diagnostics_route(
    check_remote: bool = Query(default=False),
):
    result = await diagnose_llm(check_remote=check_remote)
    return LLMDiagnosticsResponse(
        configured=result.configured,
        api_key_present=result.api_key_present,
        base_url=result.base_url,
        resolved_url=result.resolved_url,
        model=result.model,
        timeout_seconds=result.timeout_seconds,
        fallback_configured=result.fallback_configured,
        fallback_base_url=result.fallback_base_url,
        fallback_resolved_url=result.fallback_resolved_url,
        fallback_model=result.fallback_model,
        fallback_timeout_seconds=result.fallback_timeout_seconds,
        checked_remote=result.checked_remote,
        request_ok=result.request_ok,
        status_code=result.status_code,
        response_preview=result.response_preview,
        error_message=result.error_message,
        provider_used=result.provider_used,
        fallback_used=result.fallback_used,
    )
