from __future__ import annotations

from typing import TypedDict


class CodingGraphState(TypedDict, total=False):
    turn_id: str | None
    session_id: str | None
    user_input: str
    context: str | None
    intent: str
    output: str
    error: str | None
    ui_status: str | None
    stop_reason: str | None
    workflow_trace: list[dict[str, object]]
    tasks_list: list[str]
    current_task: str | None
    target_files: list[str]
    raw_error_ref: str | None
    error_summary: str | None
    repair_count: int
    max_debug_steps: int
    artifact_refs: list[str]
    coding_state: dict[str, object]
    workspace_action_name: str | None
    workspace_action_input: dict[str, object]
    run_action_name: str | None
    run_action_input: dict[str, object]
    coder_plan: dict[str, object] | None
    debugger_plan: dict[str, object] | None
    executor_action_name: str | None
    executor_action_input: dict[str, object]
    action_result: dict[str, object] | None
