from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from .messaging.event_types import AGENT_EVENT_SOURCE, AGENT_EVENT_STAGE, AGENT_EVENT_TYPE


INTENT_TYPE = Literal["chat", "coding", "unknown"]
AGENT_DIAGNOSTICS_MODE = Literal["loop"]
AGENT_ROUTE_SCOPE = Literal["primary_loop"]
RUN_STATUS = Literal["queued", "running", "done", "failed", "cancelled"]
ATTEMPT_STATUS = Literal["running", "done", "failed", "cancelled"]
ATTEMPT_OUTPUT_STREAM = Literal["stdout", "stderr", "error"]
MESSAGE_TYPE = Literal["quip", "expression", "motion", "chat", "error", "status"]
MESSAGE_CHANNEL = Literal[
    "agent:quip",
    "agent:expression",
    "agent:motion",
    "agent:chat",
    "agent:error",
    "agent:status",
]
MESSAGE_ROLE = Literal["user", "assistant", "system"]
MESSAGE_STATUS = Literal["idle", "running", "paused", "done", "error", "cancelled"]
EXPRESSION_MODE = Literal["set", "add"]
WORKSPACE_TOOL_CATEGORY = Literal["context", "execution"]
WORKSPACE_TOOL_OUTPUT_KIND = Literal[
    "overview_text",
    "entry_listing",
    "file_preview",
    "command_result",
    "file_write",
]
WORKSPACE_TOOL_ERROR_CODE = Literal[
    "WORKSPACE_TOOL_UNREGISTERED",
    "WORKSPACE_TOOL_EXECUTION_FAILED",
    "WORKSPACE_TOOL_TARGET_UNSUPPORTED",
    "WORKSPACE_TOOL_TARGET_DISABLED",
]


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="用户输入")
    context: str | None = Field(default=None, description="对话上下文")
    session_id: str | None = Field(default=None, description="会话 ID；不传则由后端创建")
    

class ChatResponse(BaseModel):
    ok: bool = True
    intent: INTENT_TYPE
    output: str
    error: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    runtime_mode: str | None = None
    route_scope: AGENT_ROUTE_SCOPE | None = None
    runtime_warning: str | None = None


class ClearConversationResponse(BaseModel):
    ok: bool = True
    session_id: str
    cleared: bool
    message: str


class ConversationSessionInfo(BaseModel):
    session_id: str
    message_count: int = 0
    recent_message_count: int = 0
    compressed_message_count: int = 0
    has_compressed_context: bool = False
    has_summary_cache: bool = False
    summary_preview: str | None = None
    context_strategy_version: int | None = None
    last_message_at: str | None = None
    updated_at: str | None = None


class ConversationMessageItem(BaseModel):
    role: MESSAGE_ROLE
    content: str
    created_at: str | None = None


class ConversationSessionMetadataResponse(ConversationSessionInfo):
    ok: bool = True
    exists: bool


class ConversationSessionListResponse(BaseModel):
    ok: bool = True
    total: int = 0
    offset: int = 0
    limit: int = 0
    items: list[ConversationSessionInfo] = Field(default_factory=list)


class ConversationSessionContextResponse(ConversationSessionInfo):
    ok: bool = True
    exists: bool
    context_text: str | None = None
    context_char_count: int = 0
    compressed_summary: str | None = None
    recent_messages: list[ConversationMessageItem] = Field(default_factory=list)


class MessageEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: str | None = Field(default=None, alias="_id")
    queue_timestamp: str | None = Field(default=None, alias="_timestamp")
    channel: MESSAGE_CHANNEL | None = Field(default=None, alias="_channel")
    type: MESSAGE_TYPE
    event_type: AGENT_EVENT_TYPE | None = None
    event_source: AGENT_EVENT_SOURCE | None = None
    event_stage: AGENT_EVENT_STAGE | None = None
    frontend_visible: bool | None = None
    timestamp: str | None = None
    node_name: str | None = None
    metadata: dict[str, Any] | None = None
    content: str | None = None
    role: MESSAGE_ROLE | None = None
    expression: str | None = None
    motion: str | None = None
    mode: EXPRESSION_MODE | None = None
    intensity: float | None = None
    code: str | None = None
    message: str | None = None
    details: Any | None = None
    status: MESSAGE_STATUS | None = None
    progress: int | None = None


class MessagesResponse(BaseModel):
    ok: bool = True
    messages: list[MessageEnvelope] = Field(default_factory=list)
    count: int = 0


class ClearMessagesResponse(BaseModel):
    ok: bool = True
    message: str


class ApiErrorInfo(BaseModel):
    code: str
    message: str
    path: str | None = None
    details: Any | None = None


class ApiErrorResponse(BaseModel):
    ok: Literal[False] = False
    error: ApiErrorInfo
    detail: str


class LLMDiagnosticsResponse(BaseModel):
    configured: bool
    api_key_present: bool
    base_url: str | None = None
    chat_completions_url: str | None = None
    resolved_url: str | None = None
    provider_profile: str = "openai"
    model: str | None = None
    timeout_seconds: int
    fallback_configured: bool = False
    fallback_base_url: str | None = None
    fallback_chat_completions_url: str | None = None
    fallback_resolved_url: str | None = None
    fallback_provider_profile: str | None = None
    fallback_model: str | None = None
    fallback_timeout_seconds: int | None = None
    checked_remote: bool = False
    request_ok: bool | None = None
    status_code: int | None = None
    response_preview: str | None = None
    error_message: str | None = None
    provider_used: str | None = None
    fallback_used: bool = False


class AgentDiagnosticsRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="待诊断的用户输入")
    context: str | None = Field(default=None, description="可选上下文")
    intent: INTENT_TYPE | None = Field(default=None, description="可选意图提示")


class AgentWorkflowTraceEntry(BaseModel):
    step: int
    node: str
    node_label: str | None = None
    phase: str | None = None
    event: str
    event_type: AGENT_EVENT_TYPE | None = None
    event_source: AGENT_EVENT_SOURCE | None = None
    event_stage: AGENT_EVENT_STAGE | None = None
    frontend_visible: bool | None = None
    event_label: str | None = None
    status_level: str | None = None
    message: str | None = None
    ui_status: str | None = None
    details: dict[str, Any] | None = None


class AgentWorkflowDebugSummary(BaseModel):
    trace_count: int = 0
    first_node: str | None = None
    first_node_label: str | None = None
    last_node: str | None = None
    last_node_label: str | None = None
    terminal_node: str | None = None
    terminal_node_label: str | None = None
    last_event: str | None = None
    last_ui_status: str | None = None
    last_phase: str | None = None
    failure_node: str | None = None
    failure_node_label: str | None = None
    failure_event: str | None = None
    failure_phase: str | None = None
    failure_code: str | None = None
    failure_domain: str | None = None
    blocked: bool = False
    error_present: bool = False


class AgentWorkflowRuntimeEventSummary(BaseModel):
    event_count: int = 0
    error_event_count: int = 0
    frontend_visible_count: int = 0
    last_event_type: str | None = None
    last_event_source: str | None = None
    last_event_stage: str | None = None
    event_type_counts: dict[str, int] = Field(default_factory=dict)
    event_source_counts: dict[str, int] = Field(default_factory=dict)
    event_stage_counts: dict[str, int] = Field(default_factory=dict)


class AgentWorkflowErrorContext(BaseModel):
    message: str | None = None
    error_type: str | None = None
    summary: str | None = None
    error_code: str | None = None
    failure_domain: str | None = None
    failure_node: str | None = None
    failure_node_label: str | None = None
    failure_event: str | None = None
    failure_phase: str | None = None
    last_ui_status: str | None = None
    suggested_next_step: str | None = None


class WorkspaceToolDescriptorInfo(BaseModel):
    name: str
    title: str
    description: str
    category: WORKSPACE_TOOL_CATEGORY
    output_kind: WORKSPACE_TOOL_OUTPUT_KIND
    input_keys: list[str] = Field(default_factory=list)


class WorkspaceToolPlanInfo(BaseModel):
    tool_name: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    terminal: bool | None = None


class WorkspaceToolInfo(BaseModel):
    name: str | None = None
    title: str | None = None
    reason: str | None = None
    category: WORKSPACE_TOOL_CATEGORY | None = None
    output_kind: WORKSPACE_TOOL_OUTPUT_KIND | None = None
    error_code: WORKSPACE_TOOL_ERROR_CODE | None = None
    descriptor: WorkspaceToolDescriptorInfo | None = None
    plan: WorkspaceToolPlanInfo | None = None


class AgentDiagnosticsResponse(BaseModel):
    ok: bool = True
    prompt: str
    intent: INTENT_TYPE
    diagnostics_mode: AGENT_DIAGNOSTICS_MODE = "loop"
    route_scope: AGENT_ROUTE_SCOPE = "primary_loop"
    selected_route: str
    action_name: str | None = None
    action_category: str | None = None
    action_safety_level: str | None = None
    requires_confirmation: bool | None = None
    run_action: str | None = None
    target_run_id: str | None = None
    workspace_tool_name: str | None = None
    workspace_tool_reason: str | None = None
    workspace_tool_category: WORKSPACE_TOOL_CATEGORY | None = None
    workspace_tool_output_kind: WORKSPACE_TOOL_OUTPUT_KIND | None = None
    workspace_tool_error_code: WORKSPACE_TOOL_ERROR_CODE | None = None
    workspace_tool_descriptor: WorkspaceToolDescriptorInfo | None = None
    workspace_tool_plan: WorkspaceToolPlanInfo | None = None
    workspace_tool: WorkspaceToolInfo | None = None
    ui_status: str | None = None
    planned_nodes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    debug_summary: AgentWorkflowDebugSummary | None = None
    runtime_event_summary: AgentWorkflowRuntimeEventSummary | None = None
    error_context: AgentWorkflowErrorContext | None = None
    workflow_trace: list[AgentWorkflowTraceEntry] = Field(default_factory=list)


class AgentRunDiagnosticsResponse(BaseModel):
    ok: bool = True
    prompt: str
    intent: INTENT_TYPE
    diagnostics_mode: AGENT_DIAGNOSTICS_MODE = "loop"
    route_scope: AGENT_ROUTE_SCOPE = "primary_loop"
    selected_route: str
    action_name: str | None = None
    action_category: str | None = None
    action_safety_level: str | None = None
    requires_confirmation: bool | None = None
    run_action: str | None = None
    executable: bool = False
    executed: bool = False
    blocked_reason: str | None = None
    run_id: str | None = None
    run_status: str | None = None
    output: str | None = None
    error: str | None = None
    workspace_tool_name: str | None = None
    workspace_tool_reason: str | None = None
    workspace_tool_category: WORKSPACE_TOOL_CATEGORY | None = None
    workspace_tool_output_kind: WORKSPACE_TOOL_OUTPUT_KIND | None = None
    workspace_tool_error_code: WORKSPACE_TOOL_ERROR_CODE | None = None
    workspace_tool_descriptor: WorkspaceToolDescriptorInfo | None = None
    workspace_tool_plan: WorkspaceToolPlanInfo | None = None
    workspace_tool: WorkspaceToolInfo | None = None
    ui_status: str | None = None
    planned_nodes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    debug_summary: AgentWorkflowDebugSummary | None = None
    runtime_event_summary: AgentWorkflowRuntimeEventSummary | None = None
    error_context: AgentWorkflowErrorContext | None = None
    workflow_trace: list[AgentWorkflowTraceEntry] = Field(default_factory=list)


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


class RunDetailSection(BaseModel):
    key: str
    title: str
    summary: str | None = None
    content: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    technical: bool = False


class RunResponse(BaseModel):
    run_id: str
    status: RUN_STATUS
    output: str
    created_at: str
    updated_at: str
    source_run_id: str | None = None
    trigger_mode: str | None = None
    cancel_requested: bool = False
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
    detail_sections: list[RunDetailSection] = Field(default_factory=list)


class RunStateSnapshotResponse(BaseModel):
    run_id: str
    status: RUN_STATUS
    summary: str
    next_action: str
    terminal: bool = False
    in_progress: bool = False
    cancel_requested: bool = False
    attempt_count: int = 0
    repair_count: int = 0
    latest_attempt_number: int | None = None
    latest_attempt_status: ATTEMPT_STATUS | None = None
    latest_attempt_summary: str | None = None
    updated_at: str | None = None


class RunSummaryResponse(BaseModel):
    run_id: str
    status: RUN_STATUS
    summary: str
    prompt_preview: str | None = None
    output_preview: str | None = None
    created_at: str
    updated_at: str
    source_run_id: str | None = None
    trigger_mode: str | None = None
    cancel_requested: bool = False
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
