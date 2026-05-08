from collections.abc import Mapping
from typing import Literal

from .roleplay import emit_roleplay_state
from .workflow_nodes import AGENT_ROLEPLAY_NODE
from ..schemas import INTENT_TYPE
from ..services.chat_action.intent import detect_run_action, extract_run_reference
from ..tools.workspace_tools import (
    build_workspace_tool_context,
    execute_workspace_tool_plan,
    plan_workspace_tool,
)
from .workflow_results import WorkflowAgentResult, invoke_graph_with_result


AGENT_ROUTE_BY_INTENT: dict[str, str] = {
    "coding": "coding_node",
    "chat": "chat_node",
    "unknown": "unknown_node",
}
RUN_ACTION_CREATE: Literal["create"] = "create"
RUN_ACTION_INSPECT: Literal["inspect"] = "inspect"
RUN_ACTION_RETRY: Literal["retry"] = "retry"
RUN_ACTION_RERUN: Literal["rerun"] = "rerun"
RUN_ACTION_CANCEL: Literal["cancel"] = "cancel"
RUN_CONTROL_ACTIONS = {
    RUN_ACTION_RETRY,
    RUN_ACTION_RERUN,
    RUN_ACTION_CANCEL,
}


def describe_run_action(action: str) -> str:
    return {
        RUN_ACTION_CREATE: "创建",
        RUN_ACTION_INSPECT: "查看",
        RUN_ACTION_RETRY: "重试",
        RUN_ACTION_RERUN: "重新运行",
        RUN_ACTION_CANCEL: "取消",
    }.get(action, "处理")


def select_agent_next_node(intent: str | None) -> str:
    return AGENT_ROUTE_BY_INTENT.get(str(intent or "").strip(), "unknown_node")


def select_coding_next_node(state: Mapping[str, object]) -> str:
    run_action = str(state.get("run_action") or "").strip()
    if run_action == RUN_ACTION_INSPECT:
        return "run_snapshot_node"
    if run_action in RUN_CONTROL_ACTIONS:
        return "run_control_node"
    return "workspace_tool_node"


def build_run_creation_output(*, run_id: str, status: str) -> str:
    return build_run_creation_output_with_snapshot(run_id=run_id, status=status)


def build_run_creation_output_with_snapshot(
    *,
    run_id: str,
    status: str,
    snapshot_summary: str | None = None,
    next_action: str | None = None,
) -> str:
    lines = [
        "已通过 LangGraph 创建代码任务，并交给 `/runs` 链路处理。",
        "",
        f"run_id: {run_id}",
        f"status: {status}",
    ]
    if snapshot_summary:
        lines.append(f"当前快照: {snapshot_summary}")
    if next_action:
        lines.append(f"下一步: {next_action}")
    lines.extend(
        [
            "",
            f"你可以通过 `GET /runs/{run_id}` 查询任务状态，"
            f"也可以通过 `GET /runs/{run_id}/snapshot` 查看结构化快照，并通过 `/messages` 接收桌宠状态反馈。",
        ]
    )
    return "\n".join(lines)


def build_unknown_intent_output(prompt: str) -> str:
    return (
        "抱歉，我暂时还不能很好地判断你的意图。\n\n"
        f"你输入的内容是：{prompt}\n\n"
        "你可以继续补充信息，或者明确说明你是想聊天还是想让我帮你处理代码任务。"
    )


def build_run_snapshot_output(
    *,
    run_id: str,
    status: str,
    snapshot_summary: str,
    next_action: str,
) -> str:
    return "\n".join(
        [
            "我读取了这个代码任务的当前状态。",
            "",
            f"run_id: {run_id}",
            f"status: {status}",
            f"当前快照: {snapshot_summary}",
            f"下一步: {next_action}",
            "",
            f"你可以继续通过 `GET /runs/{run_id}/snapshot` 查看结构化快照，"
            f"也可以通过 `GET /runs/{run_id}/attempts` 或 `/messages` 继续观察执行进展。",
        ]
    )


def build_run_snapshot_progress_output(
    *,
    run_id: str,
    status: str,
    snapshot_summary: str,
    next_action: str,
    latest_attempt_summary: str | None = None,
    cancel_requested: bool = False,
) -> str:
    if status == "queued":
        title = "我读取了这个代码任务的中间状态，当前还在排队。"
    elif cancel_requested:
        title = "我读取了这个代码任务的中间状态，当前已经收到取消请求。"
    else:
        title = "我读取了这个代码任务的中间状态，当前正在执行。"

    lines = [
        title,
        "",
        f"run_id: {run_id}",
        f"status: {status}",
        f"当前快照: {snapshot_summary}",
    ]
    if latest_attempt_summary:
        lines.append(f"最近一次尝试: {latest_attempt_summary}")
    lines.extend(
        [
            f"下一步: {next_action}",
            "",
            f"你可以继续通过 `GET /runs/{run_id}/snapshot` 查看结构化快照，"
            f"也可以通过 `GET /runs/{run_id}/attempts` 或 `/messages` 继续观察执行进展。",
        ]
    )
    return "\n".join(lines)


def build_run_terminal_output(
    *,
    run_id: str,
    status: str,
    summary_text: str,
    next_action: str,
) -> str:
    return "\n".join(
        [
            "我读取了这个代码任务的最终结果。",
            "",
            f"run_id: {run_id}",
            f"status: {status}",
            f"最终总结: {summary_text}",
            f"下一步: {next_action}",
            "",
            f"你可以通过 `GET /runs/{run_id}` 或 `GET /runs/{run_id}/snapshot` 继续查看结果详情，"
            f"也可以按需要继续执行 retry / rerun。",
        ]
    )


def build_run_control_output(
    *,
    action: str,
    run_id: str,
    status: str,
    snapshot_summary: str,
    next_action: str,
    source_run_id: str | None = None,
) -> str:
    title = {
        RUN_ACTION_RETRY: "我已为这个代码任务创建重试任务。",
        RUN_ACTION_RERUN: "我已为这个代码任务创建重新运行任务。",
        RUN_ACTION_CANCEL: "我已处理这个代码任务的取消请求。",
    }.get(action, "我已处理这个代码任务的控制请求。")
    lines = [title, ""]
    if source_run_id:
        lines.append(f"source_run_id: {source_run_id}")
    lines.extend(
        [
            f"run_id: {run_id}",
            f"status: {status}",
            f"当前快照: {snapshot_summary}",
            f"下一步: {next_action}",
            "",
            f"你可以通过 `GET /runs/{run_id}/snapshot` 查看结构化快照，"
            f"也可以通过 `GET /runs/{run_id}/attempts` 或 `/messages` 继续观察执行进展。",
        ]
    )
    return "\n".join(lines)


def build_run_control_failure_output(
    *,
    action: str,
    run_id: str | None,
    error: str,
) -> str:
    lines = [f"我暂时没能完成这个代码任务的{describe_run_action(action)}操作。"]
    if run_id:
        lines.extend(["", f"run_id: {run_id}"])
    lines.extend(["", f"原因: {error}"])
    return "\n".join(lines)


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
    trace_items = state.get("workflow_trace")
    trace: list[dict[str, object]] = []
    if isinstance(trace_items, list):
        trace = [
            dict(item)
            for item in trace_items
            if isinstance(item, Mapping)
        ]
    trace.append(
        {
            "step": len(trace) + 1,
            "node": node,
            "event": event,
            "ui_status": ui_status,
            "details": dict(details) if details else None,
        }
    )
    next_state = dict(state)
    next_state["workflow_trace"] = trace
    return next_state


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def merge_context_sections(*sections: object) -> str | None:
    normalized_sections = [
        text
        for section in sections
        if (text := _normalize_optional_text(section)) is not None
    ]
    if not normalized_sections:
        return None
    return "\n\n".join(normalized_sections)


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


def build_coding_requested_state(state: Mapping[str, object]) -> dict[str, object]:
    prompt = str(state.get("user_input") or "")
    run_action = detect_run_action(prompt)
    target_run_id = extract_run_reference(prompt) if run_action != RUN_ACTION_CREATE else None
    tool_plan = plan_workspace_tool(prompt) if run_action == RUN_ACTION_CREATE else None
    workspace_tool_name = None
    workspace_tool_reason = None
    if isinstance(tool_plan, Mapping):
        workspace_tool_name = _normalize_optional_text(tool_plan.get("tool_name"))
        workspace_tool_reason = _normalize_optional_text(tool_plan.get("reason"))

    next_state = merge_agent_state(
        state,
        workspace_tool_plan=tool_plan,
        workspace_tool_name=workspace_tool_name,
        workspace_tool_reason=workspace_tool_reason,
        workspace_tool_error=None,
        workspace_tool_context=None,
        run_action=run_action,
        target_run_id=target_run_id,
        ui_status="coding_requested",
    )
    return append_workflow_trace(
        next_state,
        node="coding_node",
        event="coding_request_prepared",
        ui_status="coding_requested",
        details={
            "run_action": run_action,
            "target_run_id": target_run_id,
            "workspace_tool_name": workspace_tool_name,
        },
    )


def build_workspace_tool_state(state: Mapping[str, object]) -> dict[str, object]:
    tool_plan = state.get("workspace_tool_plan")
    if not isinstance(tool_plan, Mapping):
        next_state = merge_agent_state(
            state,
            workspace_tool_name=None,
            workspace_tool_reason="No workspace tool plan was selected.",
            workspace_tool_error=None,
            workspace_tool_context=None,
            ui_status="workspace_tool_skipped",
        )
        return append_workflow_trace(
            next_state,
            node="workspace_tool_node",
            event="workspace_tool_skipped",
            ui_status="workspace_tool_skipped",
        )

    tool_result = execute_workspace_tool_plan(tool_plan)
    tool_name = _normalize_optional_text(tool_result.get("tool_name"))
    tool_reason = _normalize_optional_text(tool_result.get("reason"))
    tool_error = _normalize_optional_text(tool_result.get("error"))
    tool_context = build_workspace_tool_context(tool_result)

    context = state.get("context")
    if tool_error is None and tool_context is not None:
        context = merge_context_sections(context, tool_context)

    ui_status = "workspace_tool_failed" if tool_error else "workspace_tool_ready"
    next_state = merge_agent_state(
        state,
        context=context,
        workspace_tool_name=tool_name,
        workspace_tool_reason=tool_reason,
        workspace_tool_error=tool_error,
        workspace_tool_context=tool_context,
        ui_status=ui_status,
    )
    return append_workflow_trace(
        next_state,
        node="workspace_tool_node",
        event="workspace_tool_failed" if tool_error else "workspace_tool_applied",
        ui_status=ui_status,
        details={
            "tool_name": tool_name,
            "has_error": tool_error is not None,
        },
    )


def build_run_creation_failure_state(
    state: Mapping[str, object],
    *,
    error: str,
) -> dict[str, object]:
    next_state = merge_agent_state(
        state,
        output=f"代码任务创建失败：{error}",
        error=error,
        run_action=RUN_ACTION_CREATE,
        ui_status="run_create_failed",
    )
    return append_workflow_trace(
        next_state,
        node="run_tool_node",
        event="run_create_failed",
        ui_status="run_create_failed",
        details={"error": error},
    )


def build_run_creation_success_state(
    state: Mapping[str, object],
    *,
    run_id: str,
    status: str,
    snapshot_summary: str | None = None,
    next_action: str | None = None,
) -> dict[str, object]:
    next_state = merge_agent_state(
        state,
        output=build_run_creation_output_with_snapshot(
            run_id=run_id,
            status=status,
            snapshot_summary=snapshot_summary,
            next_action=next_action,
        ),
        run_id=run_id,
        run_status=status,
        run_action=RUN_ACTION_CREATE,
        run_summary=snapshot_summary,
        run_next_action=next_action,
        error=None,
        ui_status="run_queued",
    )
    return append_workflow_trace(
        next_state,
        node="run_tool_node",
        event="run_created",
        ui_status="run_queued",
        details={"run_id": run_id, "status": status},
    )


def build_run_snapshot_success_state(
    state: Mapping[str, object],
    *,
    run_id: str,
    status: str,
    snapshot_summary: str,
    next_action: str,
) -> dict[str, object]:
    next_state = merge_agent_state(
        state,
        output=build_run_snapshot_output(
            run_id=run_id,
            status=status,
            snapshot_summary=snapshot_summary,
            next_action=next_action,
        ),
        run_id=run_id,
        run_status=status,
        run_action=RUN_ACTION_INSPECT,
        run_summary=snapshot_summary,
        run_next_action=next_action,
        error=None,
        ui_status="run_snapshot_ready",
    )
    return append_workflow_trace(
        next_state,
        node="run_snapshot_node",
        event="run_snapshot_ready",
        ui_status="run_snapshot_ready",
        details={"run_id": run_id, "status": status},
    )


def build_run_snapshot_progress_state(
    state: Mapping[str, object],
    *,
    run_id: str,
    status: str,
    snapshot_summary: str,
    next_action: str,
    latest_attempt_summary: str | None = None,
    cancel_requested: bool = False,
) -> dict[str, object]:
    next_state = merge_agent_state(
        state,
        output=build_run_snapshot_progress_output(
            run_id=run_id,
            status=status,
            snapshot_summary=snapshot_summary,
            next_action=next_action,
            latest_attempt_summary=latest_attempt_summary,
            cancel_requested=cancel_requested,
        ),
        run_id=run_id,
        run_status=status,
        run_action=RUN_ACTION_INSPECT,
        run_summary=snapshot_summary,
        run_next_action=next_action,
        error=None,
        ui_status="run_snapshot_in_progress",
    )
    return append_workflow_trace(
        next_state,
        node="run_snapshot_node",
        event="run_snapshot_in_progress",
        ui_status="run_snapshot_in_progress",
        details={
            "run_id": run_id,
            "status": status,
            "cancel_requested": cancel_requested,
        },
    )


def build_run_terminal_summary_state(
    state: Mapping[str, object],
    *,
    run_id: str,
    status: str,
    summary_text: str,
    next_action: str,
    output: str | None = None,
) -> dict[str, object]:
    next_state = merge_agent_state(
        state,
        output=output or build_run_terminal_output(
            run_id=run_id,
            status=status,
            summary_text=summary_text,
            next_action=next_action,
        ),
        run_id=run_id,
        run_status=status,
        run_action=RUN_ACTION_INSPECT,
        run_summary=summary_text,
        run_next_action=next_action,
        error=None,
        ui_status="run_snapshot_terminal",
    )
    return append_workflow_trace(
        next_state,
        node="run_snapshot_node",
        event="run_snapshot_terminal",
        ui_status="run_snapshot_terminal",
        details={"run_id": run_id, "status": status},
    )


def build_run_snapshot_failure_state(
    state: Mapping[str, object],
    *,
    run_id: str | None,
    error: str,
) -> dict[str, object]:
    target_run_id = run_id or str(state.get("target_run_id") or "").strip() or None
    lines = ["我暂时没能读取到这个代码任务的状态。"]
    if target_run_id:
        lines.extend(["", f"run_id: {target_run_id}"])
    lines.extend(["", f"原因: {error}"])
    next_state = merge_agent_state(
        state,
        output="\n".join(lines),
        run_id=target_run_id,
        run_action=RUN_ACTION_INSPECT,
        error=error,
        ui_status="run_snapshot_failed",
    )
    return append_workflow_trace(
        next_state,
        node="run_snapshot_node",
        event="run_snapshot_failed",
        ui_status="run_snapshot_failed",
        details={"run_id": target_run_id, "error": error},
    )


def build_run_control_success_state(
    state: Mapping[str, object],
    *,
    action: str,
    run_id: str,
    status: str,
    snapshot_summary: str,
    next_action: str,
    source_run_id: str | None = None,
) -> dict[str, object]:
    next_state = merge_agent_state(
        state,
        output=build_run_control_output(
            action=action,
            run_id=run_id,
            status=status,
            snapshot_summary=snapshot_summary,
            next_action=next_action,
            source_run_id=source_run_id,
        ),
        run_id=run_id,
        run_status=status,
        run_action=action,
        run_summary=snapshot_summary,
        run_next_action=next_action,
        error=None,
        ui_status="run_control_done",
    )
    return append_workflow_trace(
        next_state,
        node="run_control_node",
        event="run_control_done",
        ui_status="run_control_done",
        details={"action": action, "run_id": run_id, "status": status},
    )


def build_run_control_failure_state(
    state: Mapping[str, object],
    *,
    action: str,
    run_id: str | None,
    error: str,
) -> dict[str, object]:
    target_run_id = run_id or str(state.get("target_run_id") or "").strip() or None
    next_state = merge_agent_state(
        state,
        output=build_run_control_failure_output(
            action=action,
            run_id=target_run_id,
            error=error,
        ),
        run_id=target_run_id,
        run_action=action,
        error=error,
        ui_status="run_control_failed",
    )
    return append_workflow_trace(
        next_state,
        node="run_control_node",
        event="run_control_failed",
        ui_status="run_control_failed",
        details={"action": action, "run_id": target_run_id, "error": error},
    )


def build_unknown_intent_state(
    state: Mapping[str, object],
    *,
    prompt: str,
) -> dict[str, object]:
    next_state = merge_agent_state(
        state,
        output=build_unknown_intent_output(prompt),
        error=None,
        ui_status="unknown_done",
    )
    return append_workflow_trace(
        next_state,
        node="unknown_node",
        event="unknown_intent_done",
        ui_status="unknown_done",
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
        ui_status=_normalize_optional_text(state.get("ui_status")),
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
