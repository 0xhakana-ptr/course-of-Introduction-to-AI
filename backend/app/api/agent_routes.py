from fastapi import APIRouter

from .error_responses import COMMON_ERROR_RESPONSES
from ..agent_workflow.diagnostics import (
    preview_agent_workflow,
    run_agent_workflow_diagnostics,
)
from ..schemas import AgentDiagnosticsRequest, AgentDiagnosticsResponse, AgentRunDiagnosticsResponse


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


@router.post("/diagnostics/run", response_model=AgentRunDiagnosticsResponse)
async def agent_diagnostics_run_route(req: AgentDiagnosticsRequest):
    return await run_agent_workflow_diagnostics(
        prompt=req.prompt,
        context=req.context,
        intent=req.intent,
    )
