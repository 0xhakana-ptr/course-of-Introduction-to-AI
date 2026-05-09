from typing import TypedDict

from langgraph.graph import END, StateGraph

from ..llm.client import call_llm_sync
from ..schemas import INTENT_TYPE
from ..services.chat_action.intent import detect_intent
from .agent_graph_support import (
    configure_agent_graph_edges,
    register_agent_graph_nodes,
)
from ..services.run_interface import cancel_run, create_run, get_run, get_run_snapshot, rerun_run, retry_run
from .agent_run_support import (
    build_run_control_fallback_next_action,
    execute_run_control_action,
    resolve_run_snapshot_fields,
    resolve_target_run_id,
    resolve_terminal_run_summary,
)
from .agent_support import (
    RUN_ACTION_CANCEL,
    RUN_ACTION_RERUN,
    RUN_ACTION_RETRY,
    build_chat_result_state,
    build_coding_requested_state,
    build_routed_state,
    build_run_control_failure_state,
    build_run_control_success_state,
    build_run_creation_failure_state,
    build_run_creation_success_state,
    build_run_snapshot_failure_state,
    build_run_snapshot_progress_state,
    build_run_terminal_summary_state,
    build_unknown_intent_state,
    build_workflow_node_failure_state,
    build_workspace_tool_state,
    emit_agent_roleplay_state,
    invoke_agent_graph,
    select_coding_next_node,
    select_agent_next_node,
)
from .run_summary_graph import summarize_run_record
from .workflow_results import WorkflowAgentResult


class AgentState(TypedDict, total=False):
    user_input: str
    context: str | None
    session_id: str | None
    intent: INTENT_TYPE
    emit_chat_message: bool
    output: str
    error: str | None
    run_id: str | None
    run_status: str | None
    run_action: str | None
    target_run_id: str | None
    run_summary: str | None
    run_next_action: str | None
    ui_status: str | None
    workflow_trace: list[dict[str, object]]
    workspace_tool_plan: dict[str, object] | None
    workspace_tool_name: str | None
    workspace_tool_reason: str | None
    workspace_tool_descriptor: dict[str, object] | None
    workspace_tool_category: str | None
    workspace_tool_output_kind: str | None
    workspace_tool_error_code: str | None
    workspace_tool_error: str | None
    workspace_tool_context: str | None

def router_node(state: AgentState) -> AgentState:
    prompt = state.get("user_input", "")
    intent = state.get("intent") or detect_intent(prompt)
    return build_routed_state(state, intent=intent)


def route_by_intent(state: AgentState) -> str:
    if str(state.get("ui_status") or "").strip() == "workflow_node_failed":
        return "roleplay_node"
    return select_agent_next_node(state.get("intent"))


def chat_node(state: AgentState) -> AgentState:
    prompt = state.get("user_input", "")
    result = call_llm_sync(prompt, state.get("context"))
    return build_chat_result_state(
        state,
        output=result.output,
        error=result.error if not result.ok else None,
    )


def coding_node(state: AgentState) -> AgentState:
    return build_coding_requested_state(state)


def workspace_tool_node(state: AgentState) -> AgentState:
    return build_workspace_tool_state(state)


def run_tool_node(state: AgentState) -> AgentState:
    try:
        run = create_run(
            prompt=state.get("user_input", ""),
            context=state.get("context"),
        )
    except Exception as exc:
        return build_run_creation_failure_state(state, error=str(exc))

    status, snapshot_summary, next_action = resolve_run_snapshot_fields(
        get_snapshot=get_run_snapshot,
        run_id=run.run_id,
        fallback_status=run.status,
        fallback_summary="任务已创建，等待后台执行。",
        fallback_next_action="等待后台开始执行，然后继续查询任务状态。",
    )
    return build_run_creation_success_state(
        state,
        run_id=run.run_id,
        status=status,
        snapshot_summary=snapshot_summary,
        next_action=next_action,
    )


def run_snapshot_node(state: AgentState) -> AgentState:
    target_run_id = resolve_target_run_id(state)
    if not target_run_id:
        return build_run_snapshot_failure_state(
            state,
            run_id=None,
            error="未提供可查询的 run_id。",
        )

    snapshot = get_run_snapshot(target_run_id)
    if snapshot is None:
        return build_run_snapshot_failure_state(
            state,
            run_id=target_run_id,
            error="未找到对应的代码任务。",
        )

    if snapshot.terminal:
        summary_text, output = resolve_terminal_run_summary(
            run_id=target_run_id,
            snapshot_summary=snapshot.summary,
            load_run=get_run,
            summarize_run=summarize_run_record,
        )
        return build_run_terminal_summary_state(
            state,
            run_id=target_run_id,
            status=snapshot.status,
            summary_text=summary_text,
            next_action=snapshot.next_action,
            output=output,
        )

    return build_run_snapshot_progress_state(
        state,
        run_id=target_run_id,
        status=snapshot.status,
        snapshot_summary=snapshot.summary,
        next_action=snapshot.next_action,
        latest_attempt_summary=snapshot.latest_attempt_summary,
        cancel_requested=snapshot.cancel_requested,
    )


def run_control_node(state: AgentState) -> AgentState:
    action = str(state.get("run_action") or "").strip()
    target_run_id = resolve_target_run_id(state)
    if not target_run_id:
        return build_run_control_failure_state(
            state,
            action=action,
            run_id=None,
            error="未提供可操作的 run_id。",
        )

    try:
        run = execute_run_control_action(
            action=action,
            target_run_id=target_run_id,
            retry_action=retry_run,
            rerun_action=rerun_run,
            cancel_action=cancel_run,
        )
    except ValueError as exc:
        return build_run_control_failure_state(
            state,
            action=action,
            run_id=target_run_id,
            error=str(exc),
        )
    except Exception as exc:
        return build_run_control_failure_state(
            state,
            action=action,
            run_id=target_run_id,
            error=str(exc),
        )

    status, snapshot_summary, next_action = resolve_run_snapshot_fields(
        get_snapshot=get_run_snapshot,
        run_id=run.run_id,
        fallback_status=run.status,
        fallback_summary=run.output,
        fallback_next_action=build_run_control_fallback_next_action(action),
    )
    return build_run_control_success_state(
        state,
        action=action,
        run_id=run.run_id,
        status=status,
        snapshot_summary=snapshot_summary,
        next_action=next_action,
        source_run_id=target_run_id if run.run_id != target_run_id else None,
    )


def unknown_node(state: AgentState) -> AgentState:
    prompt = state.get("user_input", "")
    return build_unknown_intent_state(state, prompt=prompt)


def roleplay_node(state: AgentState) -> AgentState:
    return emit_agent_roleplay_state(state)

def create_agent_graph():
    workflow = StateGraph(AgentState)

    register_agent_graph_nodes(
        workflow,
        node_handlers={
            "router": router_node,
            "chat_node": chat_node,
            "coding_node": coding_node,
            "workspace_tool_node": workspace_tool_node,
            "run_tool_node": run_tool_node,
            "run_snapshot_node": run_snapshot_node,
            "run_control_node": run_control_node,
            "unknown_node": unknown_node,
            "roleplay_node": roleplay_node,
        },
        failure_builder=build_workflow_node_failure_state,
    )
    configure_agent_graph_edges(
        workflow,
        route_by_intent=route_by_intent,
        select_coding_next_node=select_coding_next_node,
        end_node=END,
    )

    return workflow.compile()


agent_graph = create_agent_graph()


def run_agent(
    prompt: str,
    context: str | None = None,
    *,
    session_id: str | None = None,
    intent: INTENT_TYPE | None = None,
    emit_chat_message: bool = True,
) -> WorkflowAgentResult:
    return invoke_agent_graph(
        agent_graph,
        prompt=prompt,
        context=context,
        session_id=session_id,
        intent=intent,
        emit_chat_message=emit_chat_message,
    )
