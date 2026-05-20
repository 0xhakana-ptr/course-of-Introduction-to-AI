from typing import Annotated

from fastapi import Depends

from .error_responses import raise_api_http_error
from .query_params import (
    AttemptOutputLimitQuery,
    AttemptOutputOffsetQuery,
    AttemptOutputStreamQuery,
)
from ..schemas import (
    RunAttemptListResponse,
    RunAttemptOutputChunkResponse,
    RunAttemptResponse,
    RunAttemptScriptResponse,
    RunLogResponse,
    RunResponse,
    RunStateSnapshotResponse,
)
from ..services.run import (
    get_run,
    get_run_attempt,
    get_run_attempt_output_chunk,
    get_run_attempt_script,
    get_run_attempts,
    get_run_log,
    get_run_snapshot,
)


def require_run(run_id: str) -> RunResponse:
    run = get_run(run_id)
    if run is None:
        raise_api_http_error(404, message="run not found", code="run_not_found")
    return run


def require_run_attempts(run_id: str) -> RunAttemptListResponse:
    attempts = get_run_attempts(run_id)
    if attempts is None:
        raise_api_http_error(404, message="run not found", code="run_not_found")
    return attempts


def require_run_attempt(run_id: str, attempt_number: int) -> RunAttemptResponse:
    attempt = get_run_attempt(run_id, attempt_number)
    if attempt is None:
        raise_api_http_error(404, message="attempt not found", code="attempt_not_found")
    return attempt


def require_run_attempt_script(run_id: str, attempt_number: int) -> RunAttemptScriptResponse:
    script = get_run_attempt_script(run_id, attempt_number)
    if script is None:
        raise_api_http_error(
            404,
            message="attempt script not found",
            code="attempt_script_not_found",
        )
    return script


def require_run_attempt_output(
    run_id: str,
    attempt_number: int,
    stream: AttemptOutputStreamQuery = "stdout",
    offset: AttemptOutputOffsetQuery = 0,
    limit: AttemptOutputLimitQuery = 4000,
) -> RunAttemptOutputChunkResponse:
    output = get_run_attempt_output_chunk(
        run_id=run_id,
        attempt_number=attempt_number,
        stream=stream,
        offset=offset,
        limit=limit,
    )
    if output is None:
        raise_api_http_error(
            404,
            message="attempt output not found",
            code="attempt_output_not_found",
        )
    return output


def require_run_log(run_id: str) -> RunLogResponse:
    run_log = get_run_log(run_id)
    if run_log is None:
        raise_api_http_error(404, message="run not found", code="run_not_found")
    return run_log


def require_run_snapshot(run_id: str) -> RunStateSnapshotResponse:
    snapshot = get_run_snapshot(run_id)
    if snapshot is None:
        raise_api_http_error(404, message="run not found", code="run_not_found")
    return snapshot


RunDependency = Annotated[RunResponse, Depends(require_run)]
RunAttemptsDependency = Annotated[RunAttemptListResponse, Depends(require_run_attempts)]
RunAttemptDependency = Annotated[RunAttemptResponse, Depends(require_run_attempt)]
RunAttemptScriptDependency = Annotated[RunAttemptScriptResponse, Depends(require_run_attempt_script)]
RunAttemptOutputDependency = Annotated[RunAttemptOutputChunkResponse, Depends(require_run_attempt_output)]
RunLogDependency = Annotated[RunLogResponse, Depends(require_run_log)]
RunSnapshotDependency = Annotated[RunStateSnapshotResponse, Depends(require_run_snapshot)]
