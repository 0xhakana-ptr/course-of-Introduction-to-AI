# -*- coding: utf-8 -*-
"""Central limit constants for the backend application.

Every hardcoded numeric/text limit across the agent workflow, services,
and tools layers must be defined here as the single source of truth.
No module should define its own copy of these values.

Value guidelines:
- Frontend/UI text: generous for full chat output display
- LLM debug previews: large enough to capture full reasoning traces
- Planner limits: room for complex multi-file code generation tasks
- Worker payloads: conservative to prevent raw errors leaking
- Run outputs: large chunks for long stdout/stderr
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Text / preview limits
# ---------------------------------------------------------------------------

# Frontend-facing text: generous for long-form code explanations and chat.
FRONTEND_TEXT_MAX: int = 4000
FRONTEND_SINGLE_LINE_MAX: int = 400

# Worker-side payload text: balanced to prevent raw error/data leaks
# while allowing meaningful context.
WORKER_TEXT_MAX: int = 3000

# LLM output previews: used in debug logs and error diagnostics.
LLM_PREVIEW_MAX: int = 1200
LLM_PLANNER_OUTPUT_PREVIEW_MAX: int = 1500
LLM_PLANNER_TARGET_FILES_MAX: int = 600
LLM_PLANNER_MAX_TOKENS: int = 2000
LLM_REPAIR_COMMAND_PREVIEW_MAX: int = 600

# Summary previews: inline previews in chat messages and status cards.
SUMMARY_PREVIEW_MAX: int = 500
SUMMARY_OUTCOME_MAX: int = 800
SUMMARY_SINGLE_LINE_MAX: int = 500
SUMMARY_RUN_MAX: int = 1000

# API-level previews: returned in structured API responses.
API_DIAGNOSTICS_PREVIEW_MAX: int = 1500
API_RESULT_PREVIEW_MAX: int = 1200

# Run attempt output: chunked delivery to frontend.
RUN_ATTEMPT_OUTPUT_PREVIEW_MAX: int = 4000
RUN_ATTEMPT_OUTPUT_CHUNK_DEFAULT: int = 8000
RUN_ATTEMPT_OUTPUT_CHUNK_MAX: int = 50000
STARTUP_RECOVERY_PREVIEW_MAX: int = 20

# ---------------------------------------------------------------------------
# Coding planner limits
# ---------------------------------------------------------------------------

PLANNER_MAX_TASKS: int = 10
PLANNER_TASK_TEXT_MAX: int = 800
PLANNER_REASON_TEXT_MAX: int = 800
PLANNER_TEXT_VALUE_MAX: int = 8000

# ---------------------------------------------------------------------------
# Worker limits
# ---------------------------------------------------------------------------

WORKER_ARTIFACT_SUMMARY_MAX: int = 1500
WORKER_ERROR_SUMMARY_MAX: int = 2000

# ---------------------------------------------------------------------------
# Forbidden keys for frontend and worker payloads
# ---------------------------------------------------------------------------

FORBIDDEN_KEYS_FRONTEND_ONLY: frozenset[str] = frozenset({
    "artifact_refs",
    "code_diff",
    "current_code",
    "current_code_or_patch",
    "current_code_or_patch_ref",
    "debug_trace",
    "full_code",
    "raw_error",
    "raw_error_ref",
    "stack_trace",
    "stderr",
    "stdout",
    "tool_internal_stack_trace",
    "workflow_trace",
})

FORBIDDEN_KEYS_WORKER_ONLY: frozenset[str] = frozenset({
    "action_result",
    "artifact_content",
    "code_diff",
    "current_code",
    "current_code_or_patch",
    "debug_trace",
    "full_code",
    "llm_prompt",
    "raw_error",
    "raw_error_ref",
    "stack_trace",
    "stderr",
    "stdout",
    "tool_internal_stack_trace",
    "workflow_trace",
})
