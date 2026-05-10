import logging
from collections.abc import Mapping

from ...schemas import INTENT_TYPE
from ..output.roleplay import emit_roleplay_state
from ..trace.runtime import build_workflow_trace_entry, coerce_workflow_trace_items
from ..contracts.workflow_nodes import AGENT_ROLEPLAY_NODE
from ..contracts.workflow_results import WorkflowAgentResult, invoke_graph_with_result


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


def normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def merge_context_sections(*sections: object) -> str | None:
    normalized_sections = [
        text
        for section in sections
        if (text := normalize_optional_text(section)) is not None
    ]
    if not normalized_sections:
        return None
    return "\n\n".join(normalized_sections)


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


def build_routed_state(
    state: Mapping[str, object],
    *,
    intent: str,
) -> dict[str, object]:
    next_state = merge_agent_state(
        state,
        intent=intent,
        ui_status="routed",
    )
    return append_workflow_trace(
        next_state,
        node="router",
        event="intent_routed",
        ui_status="routed",
        details={"intent": intent},
    )


def build_chat_result_state(
    state: Mapping[str, object],
    *,
    output: str,
    error: str | None,
) -> dict[str, object]:
    ui_status = "chat_failed" if error else "chat_done"
    next_state = merge_agent_state(
        state,
        output=output,
        error=error,
        ui_status=ui_status,
    )
    return append_workflow_trace(
        next_state,
        node="chat_node",
        event="llm_response_ready" if error is None else "llm_response_failed",
        ui_status=ui_status,
        details={"has_error": error is not None},
    )


def emit_agent_roleplay_state(
    state: Mapping[str, object],
    *,
    node_name: str = AGENT_ROLEPLAY_NODE,
) -> dict[str, object]:
    traced_state = append_workflow_trace(
        state,
        node="roleplay_node",
        event="roleplay_emit",
        ui_status=normalize_optional_text(state.get("ui_status")),
        details={"node_name": node_name},
    )
    return emit_roleplay_state(
        traced_state,
        default_node_name=node_name,
    )


def build_agent_initial_state(
    *,
    prompt: str,
    context: str | None,
    session_id: str | None,
    emit_chat_message: bool,
    intent: INTENT_TYPE | None = None,
) -> dict[str, object]:
    state: dict[str, object] = {
        "user_input": prompt,
        "context": context,
        "session_id": session_id,
        "emit_chat_message": emit_chat_message,
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
    }
    if intent is not None:
        state["intent"] = intent
    return state


def invoke_agent_graph(
    graph: object,
    *,
    prompt: str,
    context: str | None,
    session_id: str | None,
    intent: INTENT_TYPE | None,
    emit_chat_message: bool,
) -> WorkflowAgentResult:
    initial_state = build_agent_initial_state(
        prompt=prompt,
        context=context,
        session_id=session_id,
        emit_chat_message=emit_chat_message,
        intent=intent,
    )
    return invoke_graph_with_result(
        graph,
        initial_state=initial_state,
        on_success=lambda result: WorkflowAgentResult.from_state(
            result,
            default_intent=intent or "unknown",
        ),
        on_error=lambda exc, state: WorkflowAgentResult.from_error(
            exc,
            state,
            default_intent=intent or "unknown",
        ),
    )
