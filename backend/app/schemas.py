from typing import Literal
from pydantic import BaseModel, Field


INTENT_TYPE = Literal["chat", "coding", "unknown"]
RUN_STATUS = Literal["queued", "running", "done", "failed"]
ATTEMPT_STATUS = Literal["running", "done", "failed"]
ATTEMPT_OUTPUT_STREAM = Literal["stdout", "stderr", "error"]


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="用户输入")
    context: str | None = Field(default=None, description="对话上下文")
    

class ChatResponse(BaseModel):
    ok: bool = True
    intent: INTENT_TYPE
    output: str
    error: str | None = None


class LLMDiagnosticsResponse(BaseModel):
    configured: bool
    api_key_present: bool
    base_url: str | None = None
    resolved_url: str | None = None
    model: str | None = None
    timeout_seconds: int
    checked_remote: bool = False
    request_ok: bool | None = None
    status_code: int | None = None
    response_preview: str | None = None
    error_message: str | None = None


class RunCreateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="任务输入")
    context: str | None = Field(default=None, description="任务上下文")


class RunAttemptResponse(BaseModel):
    attempt_number: int
    generator: str
    repair_round: int = 0
    status: ATTEMPT_STATUS
    summary: str
    source_file_name: str | None = None
    attempt_file_name: str | None = None
    script_rel_path: str | None = None
    command: str | None = None
    cwd: str | None = None
    returncode: int | None = None
    stdout: str | None = None
    stdout_length: int = 0
    stdout_truncated: bool = False
    stderr: str | None = None
    stderr_length: int = 0
    stderr_truncated: bool = False
    error: str | None = None
    error_length: int = 0
    error_truncated: bool = False
    script_available: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None


class RunAttemptListResponse(BaseModel):
    run_id: str
    attempt_count: int = 0
    attempts: list[RunAttemptResponse] = Field(default_factory=list)


class RunResponse(BaseModel):
    run_id: str
    status: RUN_STATUS
    output: str
    created_at: str
    updated_at: str
    generator: str | None = None
    attempt_count: int = 0
    repair_attempted: bool = False
    repair_count: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    prompt: str | None = None
    context: str | None = None
    command: str | None = None
    returncode: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    log_path: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    attempts: list[RunAttemptResponse] = Field(default_factory=list)


class RunSummaryResponse(BaseModel):
    run_id: str
    status: RUN_STATUS
    summary: str
    prompt_preview: str | None = None
    output_preview: str | None = None
    created_at: str
    updated_at: str
    generator: str | None = None
    attempt_count: int = 0
    repair_attempted: bool = False
    repair_count: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    error_preview: str | None = None
    latest_attempt_summary: str | None = None


class RunSummaryListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[RunSummaryResponse] = Field(default_factory=list)


class RunLogResponse(BaseModel):
    run_id: str
    log_path: str | None = None
    content: str


class RunAttemptScriptResponse(BaseModel):
    run_id: str
    attempt_number: int
    attempt_file_name: str | None = None
    script_rel_path: str | None = None
    content: str


class RunAttemptOutputChunkResponse(BaseModel):
    run_id: str
    attempt_number: int
    stream: ATTEMPT_OUTPUT_STREAM
    offset: int
    limit: int
    total_length: int
    has_more: bool
    content: str
