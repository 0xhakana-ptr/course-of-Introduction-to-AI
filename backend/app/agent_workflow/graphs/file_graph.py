from __future__ import annotations

from collections.abc import Mapping

from langgraph.graph import END, StateGraph

from ..actions import default_action_registry
from ..actions.models import AgentActionResult
from ..contracts.workflow_results import invoke_graph_with_result
from ..state.trace_runtime import build_workflow_trace_entry, coerce_workflow_trace_items
from .file_context import file_state_from_action_result, merge_file_context
from .file_result import FileWorkflowResult
from .file_state import FileGraphState
from ..state.utils_shared import normalize_text


FILE_START_NODE = "file_start_node"
FILE_EXECUTOR_NODE = "file_executor_node"
FILE_OBSERVER_NODE = "file_observer_node"
FILE_FINISH_NODE = "file_finish_node"
FILE_FAILURE_NODE = "file_failure_node"
SUPPORTED_FILE_ACTIONS = frozenset(
    {
        "workspace.read",
        "workspace.write",
        "workspace.list",
        "workspace.move",
        "workspace.copy",
        "workspace.delete",
        "workspace.search",
        "workspace.export_desktop",
    }
)



def _merge_state(
    state: Mapping[str, object],
    **updates: object,
) -> dict[str, object]:
    return {**state, **updates}


def _append_file_trace(
    state: Mapping[str, object],
    *,
    node: str,
    event: str,
    ui_status: str,
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
    return _merge_state(state, workflow_trace=trace)


def _coerce_action_result(value: object) -> dict[str, object]:
    if isinstance(value, AgentActionResult):
        return value.as_dict()
    return dict(value) if isinstance(value, Mapping) else {}


def file_start_node(state: FileGraphState) -> FileGraphState:
    action_name = normalize_text(state.get("file_action_name"))
    if action_name not in SUPPORTED_FILE_ACTIONS:
        return _append_file_trace(
            _merge_state(
                state,
                error=f"unsupported file action: {action_name or '<missing>'}",
                ui_status="file_workflow_failed",
                stop_reason="failed",
            ),
            node=FILE_START_NODE,
            event="file_action_rejected",
            ui_status="file_workflow_failed",
            details={"file_action_name": action_name},
        )

    return _append_file_trace(
        _merge_state(
            state,
            ui_status="file_workflow_started",
            stop_reason=None,
        ),
        node=FILE_START_NODE,
        event="file_workflow_started",
        ui_status="file_workflow_started",
        details={"file_action_name": action_name},
    )


def file_executor_node(state: FileGraphState) -> FileGraphState:
    action_name = normalize_text(state.get("file_action_name"))
    action_input = dict(state.get("file_action_input") or {})
    result = default_action_registry.execute(action_name, action_input)
    result_payload = result.as_dict()
    error = None if result.ok else result.error or result.summary
    return _append_file_trace(
        _merge_state(
            state,
            action_result=result_payload,
            output=result.summary,
            error=error,
            ui_status="file_action_done" if result.ok else "file_action_failed",
        ),
        node=FILE_EXECUTOR_NODE,
        event="file_action_executed" if result.ok else "file_action_failed",
        ui_status="file_action_done" if result.ok else "file_action_failed",
        details={
            "file_action_name": action_name,
            "ok": result.ok,
        },
    )


def file_observer_node(state: FileGraphState) -> FileGraphState:
    action_name = normalize_text(state.get("file_action_name"))
    action_input = dict(state.get("file_action_input") or {})
    action_result = _coerce_action_result(state.get("action_result"))
    file_state = merge_file_context(
        state.get("file_context"),
        file_state_from_action_result(
            action_name,
            action_input,
            action_result,
        ),
    )
    return _append_file_trace(
        _merge_state(
            state,
            file_state=file_state,
            ui_status="file_observed",
        ),
        node=FILE_OBSERVER_NODE,
        event="file_action_observed",
        ui_status="file_observed",
        details={"file_state": file_state},
    )


def file_finish_node(state: FileGraphState) -> FileGraphState:
    return _append_file_trace(
        _merge_state(
            state,
            ui_status="file_workflow_completed",
            stop_reason="completed",
        ),
        node=FILE_FINISH_NODE,
        event="file_workflow_completed",
        ui_status="file_workflow_completed",
    )


def file_failure_node(state: FileGraphState) -> FileGraphState:
    return _append_file_trace(
        _merge_state(
            state,
            ui_status="file_workflow_failed",
            stop_reason="failed",
        ),
        node=FILE_FAILURE_NODE,
        event="file_workflow_failed",
        ui_status="file_workflow_failed",
        details={"error": state.get("error")},
    )


def _route_after_start(state: FileGraphState) -> str:
    if normalize_text(state.get("error")):
        return FILE_FAILURE_NODE
    return FILE_EXECUTOR_NODE


def _route_after_executor(state: FileGraphState) -> str:
    if normalize_text(state.get("error")):
        return FILE_FAILURE_NODE
    return FILE_OBSERVER_NODE


def build_file_workflow_graph():
    graph = StateGraph(FileGraphState)
    graph.add_node(FILE_START_NODE, file_start_node)
    graph.add_node(FILE_EXECUTOR_NODE, file_executor_node)
    graph.add_node(FILE_OBSERVER_NODE, file_observer_node)
    graph.add_node(FILE_FINISH_NODE, file_finish_node)
    graph.add_node(FILE_FAILURE_NODE, file_failure_node)
    graph.set_entry_point(FILE_START_NODE)
    graph.add_conditional_edges(
        FILE_START_NODE,
        _route_after_start,
        {
            FILE_EXECUTOR_NODE: FILE_EXECUTOR_NODE,
            FILE_FAILURE_NODE: FILE_FAILURE_NODE,
        },
    )
    graph.add_conditional_edges(
        FILE_EXECUTOR_NODE,
        _route_after_executor,
        {
            FILE_OBSERVER_NODE: FILE_OBSERVER_NODE,
            FILE_FAILURE_NODE: FILE_FAILURE_NODE,
        },
    )
    graph.add_edge(FILE_OBSERVER_NODE, FILE_FINISH_NODE)
    graph.add_edge(FILE_FINISH_NODE, END)
    graph.add_edge(FILE_FAILURE_NODE, END)
    return graph.compile()


def run_file_workflow(
    prompt: str,
    *,
    context: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
    file_action_name: str,
    file_action_input: Mapping[str, object] | None = None,
    file_context: Mapping[str, object] | None = None,
) -> FileWorkflowResult:
    initial_state: FileGraphState = {
        "turn_id": turn_id,
        "session_id": session_id,
        "user_input": prompt,
        "context": context,
        "file_action_name": file_action_name,
        "file_action_input": dict(file_action_input or {}),
        "file_context": dict(file_context or {}),
        "workflow_trace": [],
    }
    return invoke_graph_with_result(
        build_file_workflow_graph(),
        initial_state=initial_state,
        on_success=FileWorkflowResult.from_state,
        on_error=FileWorkflowResult.from_error,
    )
