import logging
from collections.abc import Mapping
from uuid import uuid4

from ...schemas import INTENT_TYPE
from .trace_runtime import build_workflow_trace_entry, coerce_workflow_trace_items


logger = logging.getLogger(__name__)


def merge_agent_state(
    state: Mapping[str, object],
    *,
    ui_status: str | None = None,
    **updates: object,
) -> dict[str, object]:
    next_state = {
        **state,
        **updates,
    }
    if ui_status is not None:
        next_state["ui_status"] = ui_status
    return next_state


def append_workflow_trace(
    state: Mapping[str, object],
    *,
    node: str,
    event: str,
    ui_status: str | None = None,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    trace = coerce_workflow_trace_items(state.get("workflow_trace"))
    trace.append(
        build_workflow_trace_entry(
            step=len(trace) + 1,
            node=node,
            event=event,
            ui_status=ui_status,
            details=details,
            frontend_visible=False,
        )
    )
    logger.debug(
        "Workflow trace appended: step=%s node=%s event=%s ui_status=%s details=%s",
        trace[-1]["step"],
        node,
        event,
        ui_status,
        dict(details) if details else None,
    )
    next_state = dict(state)
    next_state["workflow_trace"] = trace
    return next_state


def build_workflow_node_failure_state(
    state: Mapping[str, object],
    *,
    node_name: str,
    exc: Exception,
) -> dict[str, object]:
    error_text = str(exc).strip() or exc.__class__.__name__
    next_state = merge_agent_state(
        state,
        output=f"Agent 工作流在 `{node_name}` 节点执行失败：{error_text}",
        error=error_text,
        ui_status="workflow_node_failed",
    )
    return append_workflow_trace(
        next_state,
        node=node_name,
        event="node_exception",
        ui_status="workflow_node_failed",
        details={
            "error": error_text,
            "error_type": exc.__class__.__name__,
        },
    )


def build_agent_initial_state(
    *,
    prompt: str,
    context: str | None,
    session_id: str | None,
    emit_chat_message: bool,
    emit_node_events: bool = True,
    intent: INTENT_TYPE | None = None,
) -> dict[str, object]:
    state: dict[str, object] = {
        "user_input": prompt,
        "turn_id": f"turn_{uuid4().hex}",
        "context": context,
        "session_id": session_id,
        "emit_chat_message": emit_chat_message,
        "emit_node_events": emit_node_events,
        "output": "",
        "error": None,
        "run_id": None,
        "run_status": None,
        "run_action": None,
        "target_run_id": None,
        "run_summary": None,
        "run_next_action": None,
        "ui_status": None,
        "workflow_trace": [],
        "workspace_tool_plan": None,
        "workspace_tool_name": None,
        "workspace_tool_reason": None,
        "workspace_tool_descriptor": None,
        "workspace_tool_category": None,
        "workspace_tool_output_kind": None,
        "workspace_tool_error_code": None,
        "workspace_tool_error": None,
        "workspace_tool_context": None,
        "workspace_tool_terminal": False,
    }
    if intent is not None:
        state["intent"] = intent
    return state
