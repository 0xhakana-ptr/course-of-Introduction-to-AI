from fastapi import BackgroundTasks, FastAPI, HTTPException, Query

from backend.app.core.config import settings
from backend.app.schemas import (
    ATTEMPT_OUTPUT_STREAM,
    ChatRequest,
    ChatResponse,
    RunAttemptListResponse,
    RunAttemptOutputChunkResponse,
    RunAttemptResponse,
    RunAttemptScriptResponse,
    RunCreateRequest,
    RunLogResponse,
    RunResponse,
)
from backend.app.services.chat_service import generate_chat_response
from backend.app.services.run_service import (
    create_run,
    execute_run,
    get_run,
    get_run_attempt,
    get_run_attempts,
    get_run_attempt_output_chunk,
    get_run_attempt_script,
    get_run_log,
    list_runs,
)


app = FastAPI(title="AI Chat Backend", version=settings.app_version)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "backend",
        "version": settings.app_version
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    prompt = req.prompt.strip()
    context = (req.context or "").strip() or None

    intent, output = await generate_chat_response(prompt, context)
    return ChatResponse(intent=intent, output=output)


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
