from fastapi import APIRouter

from .error_responses import COMMON_ERROR_RESPONSES
from .query_params import CheckRemoteQuery
from .route_support import build_llm_diagnostics_response
from ..llm.client import diagnose_llm
from ..schemas import LLMDiagnosticsResponse


router = APIRouter(
    prefix="/llm",
    tags=["llm"],
    responses=COMMON_ERROR_RESPONSES,
)


@router.get("/diagnostics", response_model=LLMDiagnosticsResponse)
async def llm_diagnostics_route(
    check_remote: CheckRemoteQuery = False,
):
    result = await diagnose_llm(check_remote=check_remote)
    return build_llm_diagnostics_response(result)
