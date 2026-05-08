from typing import TypedDict

from langgraph.graph import END, StateGraph

from ..llm.client import call_llm_sync
from ..schemas import INTENT_TYPE
from ..services.chat_action.intent import detect_intent
from ..services.run_interface import cancel_run, create_run, get_run, get_run_snapshot, rerun_run, retry_run
from .run_summary_graph import summarize_run_record
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
    build_workspace_tool_state,
    emit_agent_roleplay_state,
    invoke_agent_graph,
    select_coding_next_node,
    select_agent_next_node,
)
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
    workspace_tool_error: str | None
    workspace_tool_context: str | None


def _resolve_run_snapshot_fields(
    *,
    run_id: str,
    fallback_status: str,
    fallback_summary: str,
    fallback_next_action: str,
) -> tuple[str, str, str]:
    snapshot = get_run_snapshot(run_id)
    if snapshot is None:
        return fallback_status, fallback_summary, fallback_next_action
    return snapshot.status, snapshot.summary, snapshot.next_action


def router_node(state: AgentState) -> AgentState:
    prompt = state.get("user_input", "")
    intent = state.get("intent") or detect_intent(prompt)
    return build_routed_state(state, intent=intent)


def route_by_intent(state: AgentState) -> str:
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

    status, snapshot_summary, next_action = _resolve_run_snapshot_fields(
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
    target_run_id = str(state.get("target_run_id") or state.get("run_id") or "").strip()
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
        run = get_run(target_run_id)
        summary_text = snapshot.summary
        output: str | None = None
        if run is not None:
            summary_result = summarize_run_record(
                run.model_dump(),
                emit_chat_message=False,
            )
            if summary_result.ok and summary_result.output.strip():
                output = summary_result.output
            if summary_result.summary_text.strip():
                summary_text = summary_result.summary_text

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
    target_run_id = str(state.get("target_run_id") or state.get("run_id") or "").strip()
    if not target_run_id:
        return build_run_control_failure_state(
            state,
            action=action,
            run_id=None,
            error="未提供可操作的 run_id。",
        )

    try:
        if action == RUN_ACTION_RETRY:
            run = retry_run(target_run_id)
        elif action == RUN_ACTION_RERUN:
            run = rerun_run(target_run_id)
        elif action == RUN_ACTION_CANCEL:
            run = cancel_run(target_run_id)
        else:
            return build_run_control_failure_state(
                state,
                action=action,
                run_id=target_run_id,
                error="当前请求不属于支持的 run 控制动作。",
            )
    except Exception as exc:
        return build_run_control_failure_state(
            state,
            action=action,
            run_id=target_run_id,
            error=str(exc),
        )

    fallback_next_action = (
        "等待后台开始执行，然后继续查询任务状态。"
        if action in {RUN_ACTION_RETRY, RUN_ACTION_RERUN}
        else "任务状态已更新，可继续查询任务快照确认最终结果。"
    )
    status, snapshot_summary, next_action = _resolve_run_snapshot_fields(
        run_id=run.run_id,
        fallback_status=run.status,
        fallback_summary=run.output,
        fallback_next_action=fallback_next_action,
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

    workflow.add_node("router", router_node)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("coding_node", coding_node)
    workflow.add_node("workspace_tool_node", workspace_tool_node)
    workflow.add_node("run_tool_node", run_tool_node)
    workflow.add_node("run_snapshot_node", run_snapshot_node)
    workflow.add_node("run_control_node", run_control_node)
    workflow.add_node("unknown_node", unknown_node)
    workflow.add_node("roleplay_node", roleplay_node)

    workflow.set_entry_point("router")
    workflow.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "chat_node": "chat_node",
            "coding_node": "coding_node",
            "unknown_node": "unknown_node",
        },
    )
    workflow.add_edge("chat_node", "roleplay_node")
    workflow.add_conditional_edges(
        "coding_node",
        select_coding_next_node,
        {
            "workspace_tool_node": "workspace_tool_node",
            "run_snapshot_node": "run_snapshot_node",
            "run_control_node": "run_control_node",
        },
    )
    workflow.add_edge("workspace_tool_node", "run_tool_node")
    workflow.add_edge("run_tool_node", "roleplay_node")
    workflow.add_edge("run_snapshot_node", "roleplay_node")
    workflow.add_edge("run_control_node", "roleplay_node")
    workflow.add_edge("unknown_node", "roleplay_node")
    workflow.add_edge("roleplay_node", END)

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
