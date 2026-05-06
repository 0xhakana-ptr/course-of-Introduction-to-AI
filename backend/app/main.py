import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query

from .core.config import settings
from .core.logging_config import configure_logging
from .llm.client import diagnose_llm
from .message_queue import message_queue
from .schemas import (
    ATTEMPT_OUTPUT_STREAM,
    ClearMessagesResponse,
    ChatRequest,
    ChatResponse,
    LLMDiagnosticsResponse,
    MessagesResponse,
    RunAttemptListResponse,
    RunAttemptOutputChunkResponse,
    RunAttemptResponse,
    RunAttemptScriptResponse,
    RunCreateRequest,
    RunLogResponse,
    RunResponse,
    RunSummaryListResponse,
)
from .services.chat_interface import generate_chat_response
from .services.run_interface import (
    RunActionError,
    StartupRecoveryResult,
    cancel_run,
    create_run,
    execute_run,
    get_run,
    get_run_attempt,
    get_run_attempts,
    get_run_attempt_output_chunk,
    get_run_attempt_script,
    get_run_log,
    list_runs,
    list_run_summaries,
    recover_interrupted_runs,
    rerun_run,
    retry_run,
)


configure_logging()
logger = logging.getLogger(__name__)


def serialize_startup_recovery(result: StartupRecoveryResult | None) -> dict[str, object] | None:
    if result is None:
        return None
    return {
        "checked_at": result.checked_at,
        "scanned_count": result.scanned_count,
        "recovered_count": result.recovered_count,
        "recovered_run_ids": result.recovered_run_ids,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.startup_recovery = recover_interrupted_runs()
    recovery = app.state.startup_recovery
    if recovery.recovered_count > 0:
        logger.warning(
            "Startup recovery completed: recovered_count=%s scanned_count=%s",
            recovery.recovered_count,
            recovery.scanned_count,
        )
    else:
        logger.info("Startup recovery completed: scanned_count=%s", recovery.scanned_count)
    yield


app = FastAPI(title="AI Chat Backend", version=settings.app_version, lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "backend",
        "version": settings.app_version,
        "startup_recovery": serialize_startup_recovery(
            getattr(app.state, "startup_recovery", None)
        ),
    }


@app.get("/llm/diagnostics", response_model=LLMDiagnosticsResponse)
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


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    prompt = req.prompt.strip()
    context = (req.context or "").strip() or None

    result = await generate_chat_response(prompt, context)
    return ChatResponse(
        ok=result.ok,
        intent=result.intent,
        output=result.output,
        error=result.error,
    )


@app.post("/runs", response_model=RunResponse)
async def create_run_route(req: RunCreateRequest, background_tasks: BackgroundTasks):
    prompt = req.prompt.strip()
    context = (req.context or "").strip() or None
    run = create_run(prompt, context)
    background_tasks.add_task(execute_run, run.run_id)
    return run


@app.get("/runs", response_model=list[RunResponse])
async def list_runs_route():
    return list_runs()


@app.get("/runs/summary", response_model=RunSummaryListResponse)
async def list_run_summaries_route(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    return list_run_summaries(offset=offset, limit=limit)


@app.get("/runs/{run_id}", response_model=RunResponse)
async def get_run_route(run_id: str):
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/runs/{run_id}/attempts", response_model=RunAttemptListResponse)
async def get_run_attempts_route(run_id: str):
    attempts = get_run_attempts(run_id)
    if attempts is None:
        raise HTTPException(status_code=404, detail="run not found")
    return attempts


@app.get("/runs/{run_id}/attempts/{attempt_number}", response_model=RunAttemptResponse)
async def get_run_attempt_route(run_id: str, attempt_number: int):
    attempt = get_run_attempt(run_id, attempt_number)
    if attempt is None:
        raise HTTPException(status_code=404, detail="attempt not found")
    return attempt


@app.get("/runs/{run_id}/attempts/{attempt_number}/script", response_model=RunAttemptScriptResponse)
async def get_run_attempt_script_route(run_id: str, attempt_number: int):
    script = get_run_attempt_script(run_id, attempt_number)
    if script is None:
        raise HTTPException(status_code=404, detail="attempt script not found")
    return script


@app.get("/runs/{run_id}/attempts/{attempt_number}/output", response_model=RunAttemptOutputChunkResponse)
async def get_run_attempt_output_route(
    run_id: str,
    attempt_number: int,
    stream: ATTEMPT_OUTPUT_STREAM = Query(default="stdout"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=4000, ge=1, le=20000),
):
    output = get_run_attempt_output_chunk(
        run_id=run_id,
        attempt_number=attempt_number,
        stream=stream,
        offset=offset,
        limit=limit,
    )
    if output is None:
        raise HTTPException(status_code=404, detail="attempt output not found")
    return output


@app.get("/runs/{run_id}/logs", response_model=RunLogResponse)
async def get_run_log_route(run_id: str):
    run_log = get_run_log(run_id)
    if run_log is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run_log


@app.post("/runs/{run_id}/retry", response_model=RunResponse)
async def retry_run_route(run_id: str, background_tasks: BackgroundTasks):
    try:
        run = retry_run(run_id)
    except RunActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    background_tasks.add_task(execute_run, run.run_id)
    return run


@app.post("/runs/{run_id}/rerun", response_model=RunResponse)
async def rerun_run_route(run_id: str, background_tasks: BackgroundTasks):
    try:
        run = rerun_run(run_id)
    except RunActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    background_tasks.add_task(execute_run, run.run_id)
    return run


@app.post("/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel_run_route(run_id: str):
    try:
        return cancel_run(run_id)
    except RunActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


# ========== 消息队列 API ==========

@app.get("/messages", response_model=MessagesResponse)
async def get_messages(since_id: str | None = Query(default=None)):
    """获取消息队列中的消息
    
    Args:
        since_id: 从哪个消息 ID 开始获取
        
    Returns:
        消息列表
    """
    messages = message_queue.get_messages(since_id)
    return MessagesResponse(
        ok=True,
        messages=messages,
        count=len(messages),
    )

@app.delete("/messages", response_model=ClearMessagesResponse)
async def clear_messages():
    """清空消息队列"""
    message_queue.clear()
    return ClearMessagesResponse(
        ok=True,
        message="消息队列已清空",
    )
