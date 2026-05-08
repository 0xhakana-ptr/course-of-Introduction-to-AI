from fastapi import APIRouter, BackgroundTasks

from .error_responses import COMMON_ERROR_RESPONSES
from .query_params import RunListLimitQuery, RunListOffsetQuery
from .route_support import normalize_prompt_and_context, schedule_run_execution
from .run_dependencies import (
    RunAttemptDependency,
    RunAttemptOutputDependency,
    RunAttemptsDependency,
    RunAttemptScriptDependency,
    RunDependency,
    RunLogDependency,
)
from ..schemas import (
    RunAttemptListResponse,
    RunAttemptOutputChunkResponse,
    RunAttemptResponse,
    RunAttemptScriptResponse,
    RunCreateRequest,
    RunLogResponse,
    RunResponse,
    RunSummaryListResponse,
)
from ..services.run_interface import (
    cancel_run,
    create_run,
    list_run_summaries,
    list_runs,
    rerun_run,
    retry_run,
)


router = APIRouter(
    prefix="/runs",
    tags=["runs"],
    responses=COMMON_ERROR_RESPONSES,
)


@router.post("", response_model=RunResponse)
async def create_run_route(req: RunCreateRequest, background_tasks: BackgroundTasks):
    prompt, context = normalize_prompt_and_context(req.prompt, req.context)
    run = create_run(prompt, context)
    schedule_run_execution(background_tasks, run.run_id)
    return run


@router.get("", response_model=list[RunResponse])
async def list_runs_route():
    return list_runs()


@router.get("/summary", response_model=RunSummaryListResponse)
async def list_run_summaries_route(
    offset: RunListOffsetQuery = 0,
    limit: RunListLimitQuery = 20,
):
    return list_run_summaries(offset=offset, limit=limit)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run_route(run: RunDependency):
    return run


@router.get("/{run_id}/attempts", response_model=RunAttemptListResponse)
async def get_run_attempts_route(attempts: RunAttemptsDependency):
    return attempts


@router.get("/{run_id}/attempts/{attempt_number}", response_model=RunAttemptResponse)
async def get_run_attempt_route(attempt: RunAttemptDependency):
    return attempt


@router.get("/{run_id}/attempts/{attempt_number}/script", response_model=RunAttemptScriptResponse)
async def get_run_attempt_script_route(script: RunAttemptScriptDependency):
    return script


@router.get("/{run_id}/attempts/{attempt_number}/output", response_model=RunAttemptOutputChunkResponse)
async def get_run_attempt_output_route(output: RunAttemptOutputDependency):
    return output


@router.get("/{run_id}/logs", response_model=RunLogResponse)
async def get_run_log_route(run_log: RunLogDependency):
    return run_log


@router.post("/{run_id}/retry", response_model=RunResponse)
async def retry_run_route(run_id: str, background_tasks: BackgroundTasks):
    run = retry_run(run_id)
    schedule_run_execution(background_tasks, run.run_id)
    return run


@router.post("/{run_id}/rerun", response_model=RunResponse)
async def rerun_run_route(run_id: str, background_tasks: BackgroundTasks):
    run = rerun_run(run_id)
    schedule_run_execution(background_tasks, run.run_id)
    return run


@router.post("/{run_id}/cancel", response_model=RunResponse)
async def cancel_run_route(run_id: str):
    return cancel_run(run_id)
