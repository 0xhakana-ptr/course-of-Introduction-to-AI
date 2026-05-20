from __future__ import annotations

from typing import TypedDict


class FileGraphState(TypedDict, total=False):
    turn_id: str | None
    session_id: str | None
    user_input: str
    context: str | None
    output: str
    error: str | None
    ui_status: str | None
    stop_reason: str | None
    workflow_trace: list[dict[str, object]]
    file_action_name: str | None
    file_action_input: dict[str, object]
    file_context: dict[str, object]
    action_result: dict[str, object] | None
    file_state: dict[str, object]
