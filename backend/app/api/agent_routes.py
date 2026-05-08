from fastapi import APIRouter

from .error_responses import COMMON_ERROR_RESPONSES
from ..agent_workflow.diagnostics import preview_agent_workflow
from ..schemas import AgentDiagnosticsRequest, AgentDiagnosticsResponse


router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    responses=COMMON_ERROR_RESPONSES,
)


@router.post("/diagnostics/preview", response_model=AgentDiagnosticsResponse)
async def agent_diagnostics_preview_route(req: AgentDiagnosticsRequest):
    return preview_agent_workflow(
        prompt=req.prompt,
        context=req.context,
        intent=req.intent,
    )
