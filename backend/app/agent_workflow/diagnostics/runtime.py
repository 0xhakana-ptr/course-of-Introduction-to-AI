from functools import partial

from anyio import to_thread

from ...schemas import (
    AgentDiagnosticsResponse,
    AgentRunDiagnosticsResponse,
    AgentWorkflowDebugSummary,
    AgentWorkflowErrorContext,
    INTENT_TYPE,
)
from ...services.chat_action.intent import detect_intent
from ..agent_support import (
    append_workflow_trace,
    build_agent_initial_state,
    build_coding_requested_state,
    build_routed_state,
    select_agent_next_node,
    select_coding_next_node,
)
from .support import (
    WorkspaceToolSnapshot,
    build_workspace_tool_response_kwargs,
)
from .failure import build_failure_descriptor
from ..agent_graph import run_agent
from ..trace.runtime import (
    build_runtime_event_summary,
    find_failure_trace,
    normalize_trace_items,
    trace_items_from_state,
)


def _coerce_intent(value: object) -> INTENT_TYPE:
    normalized = str(value or "").strip()
    if normalized in {"chat", "coding", "unknown"}:
        return normalized
    return "unknown"


def _build_planned_nodes(selected_route: str, coding_next_node: str | None = None) -> list[str]:
    planned_nodes = ["router", selected_route]
    if selected_route != "coding_node":
        planned_nodes.append("roleplay_node")
        return planned_nodes

    if coding_next_node:
        planned_nodes.append(coding_next_node)
        if coding_next_node == "workspace_tool_node":
            planned_nodes.append("run_tool_node")
    planned_nodes.append("roleplay_node")
    return planned_nodes


def _build_preview_notes(
    *,
    selected_route: str,
    coding_next_node: str | None,
    run_action: str | None,
) -> list[str]:
    if selected_route == "chat_node":
        return ["该输入会进入 chat_node，并调用当前 LLM client 生成回复。"]
    if selected_route == "unknown_node":
        return ["该输入当前会进入 unknown_node，并返回意图不明确提示。"]
    if coding_next_node == "workspace_tool_node":
        return [
            "该输入会进入 coding_node，先执行 workspace tool 规划，再创建新的 run。",
        ]
    if coding_next_node == "run_snapshot_node":
        return ["该输入会进入 coding_node，并读取已有 run 的状态或最终结果。"]
    if coding_next_node == "run_control_node":
        return [f"该输入会进入 coding_node，并对已有 run 执行 `{run_action}` 控制动作。"] if run_action else [
            "该输入会进入 coding_node，并对已有 run 执行控制动作。"
        ]
    return ["该输入会进入 coding_node，但当前未能解析出更细的后续分支。"]


def _phase_suggested_next_step(phase: str, *, blocked: bool) -> str:
    if blocked:
        return "继续使用 preview 观察路径，或改成 inspect / chat 分支进行安全运行期诊断。"

    return {
        "routing": "优先检查 intent 判断是否符合预期，再确认后续 route 是否正确。",
        "chat": "优先检查 LLM 配置、模型连通性和 chat_node 的 error/output。",
        "coding": "优先检查 run_action、target_run_id 和 coding 侧输入清洗是否符合预期。",
        "tools": "优先检查 workspace tool 规划结果、目标路径和工具执行错误信息。",
        "run_create": "优先检查 create_run 调用参数、run 快照读取结果和任务创建收口。",
        "run_read": "优先检查 run_id、snapshot 读取结果和终态/中间态分支判断。",
        "run_control": "优先检查 run_action、目标 run 当前状态和控制动作是否允许执行。",
        "roleplay": "优先检查 output、node_name 和 emit_chat_message 是否符合预期。",
        "diagnostics": "优先检查 diagnostics 预览路径是否与真实运行路径一致。",
    }.get(phase, "优先检查 failure_node 对应的 trace、ui_status 和输出内容。")


def _build_debug_summary(
    *,
    trace_items: list[dict[str, object]],
    error: str | None,
    ui_status: str | None,
    blocked: bool,
) -> AgentWorkflowDebugSummary:
    first_item = trace_items[0] if trace_items else {}
    last_item = trace_items[-1] if trace_items else {}
    failure_item = find_failure_trace(trace_items) or (last_item if blocked else {})
    failure_event = (
        str(failure_item.get("event"))
        if failure_item.get("event") is not None
        else None
    )
    failure_phase = (
        str(failure_item.get("phase"))
        if failure_item.get("phase") is not None
        else None
    )
    failure_details = failure_item.get("details")
    failure_descriptor = build_failure_descriptor(
        error_type="blocked" if blocked else "workflow_error",
        failure_event=failure_event,
        failure_phase=failure_phase or "unknown",
        failure_details=failure_details if isinstance(failure_details, dict) else None,
    ) if failure_event or blocked else None
    return AgentWorkflowDebugSummary(
        trace_count=len(trace_items),
        first_node=str(first_item.get("node")) if first_item.get("node") is not None else None,
        first_node_label=(
            str(first_item.get("node_label"))
            if first_item.get("node_label") is not None
            else None
        ),
        last_node=str(last_item.get("node")) if last_item.get("node") is not None else None,
        last_node_label=(
            str(last_item.get("node_label"))
            if last_item.get("node_label") is not None
            else None
        ),
        terminal_node=str(last_item.get("node")) if last_item.get("node") is not None else None,
        terminal_node_label=(
            str(last_item.get("node_label"))
            if last_item.get("node_label") is not None
            else None
        ),
        last_event=str(last_item.get("event")) if last_item.get("event") is not None else None,
        last_ui_status=(
            str(last_item.get("ui_status"))
            if last_item.get("ui_status") is not None
            else ui_status
        ),
        last_phase=str(last_item.get("phase")) if last_item.get("phase") is not None else None,
        failure_node=(
            str(failure_item.get("node"))
            if failure_item.get("node") is not None
            else None
        ),
        failure_node_label=(
            str(failure_item.get("node_label"))
            if failure_item.get("node_label") is not None
            else None
        ),
        failure_event=(
            failure_event
        ),
        failure_phase=(
            failure_phase
        ),
        failure_code=(
            failure_descriptor.get("error_code")
            if failure_descriptor is not None
            else None
        ),
        failure_domain=(
            failure_descriptor.get("failure_domain")
            if failure_descriptor is not None
            else None
        ),
        blocked=blocked,
        error_present=bool(error),
    )


def _build_error_context(
    *,
    error: str | None,
    blocked_reason: str | None,
    debug_summary: AgentWorkflowDebugSummary,
    trace_items: list[dict[str, object]],
) -> AgentWorkflowErrorContext | None:
    if not error and not blocked_reason:
        return None
    message = error or blocked_reason
    error_type = "blocked" if blocked_reason and not error else "workflow_error"
    failure_phase = debug_summary.failure_phase or debug_summary.last_phase or "unknown"
    failure_item = find_failure_trace(trace_items) or {}
    failure_details = failure_item.get("details")
    descriptor = build_failure_descriptor(
        error_type=error_type,
        failure_event=debug_summary.failure_event,
        failure_phase=failure_phase,
        failure_details=failure_details if isinstance(failure_details, dict) else None,
    )
    suggested_next_step = _phase_suggested_next_step(
        failure_phase,
        blocked=error_type == "blocked",
    )
    return AgentWorkflowErrorContext(
        message=message,
        error_type=error_type,
        summary=descriptor.get("summary"),
        error_code=descriptor.get("error_code"),
        failure_domain=descriptor.get("failure_domain"),
        failure_node=debug_summary.failure_node or debug_summary.last_node,
        failure_node_label=debug_summary.failure_node_label or debug_summary.last_node_label,
        failure_event=debug_summary.failure_event or debug_summary.last_event,
        failure_phase=failure_phase,
        last_ui_status=debug_summary.last_ui_status,
        suggested_next_step=suggested_next_step,
    )


def _is_runtime_executable(preview: AgentDiagnosticsResponse) -> tuple[bool, str | None]:
    if preview.selected_route in {"chat_node", "unknown_node"}:
        return True, None
    if preview.selected_route == "coding_node" and preview.run_action == "inspect":
        return True, None
    if preview.selected_route == "coding_node":
        return False, (
            "当前运行期 diagnostics 默认只允许执行 chat、unknown 和 inspect 分支；"
            "create / retry / rerun / cancel 请继续使用 preview 观察路径。"
        )
    return False, "当前输入未命中可执行的 diagnostics 分支。"


def preview_agent_workflow(
    *,
    prompt: str,
    context: str | None,
    intent: INTENT_TYPE | None,
) -> AgentDiagnosticsResponse:
    normalized_prompt = prompt.strip()
    normalized_context = (context or "").strip() or None
    initial_state = build_agent_initial_state(
        prompt=normalized_prompt,
        context=normalized_context,
        session_id=None,
        emit_chat_message=False,
        intent=intent,
    )

    resolved_intent = intent or detect_intent(normalized_prompt)
    routed_state = build_routed_state(initial_state, intent=resolved_intent)
    selected_route = select_agent_next_node(resolved_intent)
    final_state: dict[str, object] = dict(routed_state)
    coding_next_node: str | None = None

    if selected_route == "coding_node":
        final_state = build_coding_requested_state(routed_state)
        coding_next_node = select_coding_next_node(final_state)
        final_state = append_workflow_trace(
            final_state,
            node="diagnostics_preview",
            event="coding_path_selected",
            ui_status=str(final_state.get("ui_status") or "").strip() or None,
            details={
                "next_node": coding_next_node,
                "run_action": final_state.get("run_action"),
            },
        )
    else:
        final_state = append_workflow_trace(
            final_state,
            node="diagnostics_preview",
            event="route_selected",
            ui_status=str(final_state.get("ui_status") or "").strip() or None,
            details={"selected_route": selected_route},
        )

    trace_items = trace_items_from_state(final_state)
    debug_summary = _build_debug_summary(
        trace_items=trace_items,
        error=None,
        ui_status=str(final_state.get("ui_status")) if final_state.get("ui_status") is not None else None,
        blocked=False,
    )
    tool_snapshot = WorkspaceToolSnapshot.from_state(final_state)

    return AgentDiagnosticsResponse(
        ok=True,
        prompt=normalized_prompt,
        intent=_coerce_intent(final_state.get("intent")),
        selected_route=selected_route,
        run_action=str(final_state.get("run_action")) if final_state.get("run_action") is not None else None,
        target_run_id=(
            str(final_state.get("target_run_id"))
            if final_state.get("target_run_id") is not None
            else None
        ),
        **build_workspace_tool_response_kwargs(tool_snapshot),
        ui_status=str(final_state.get("ui_status")) if final_state.get("ui_status") is not None else None,
        planned_nodes=_build_planned_nodes(selected_route, coding_next_node),
        notes=_build_preview_notes(
            selected_route=selected_route,
            coding_next_node=coding_next_node,
            run_action=str(final_state.get("run_action")) if final_state.get("run_action") is not None else None,
        ),
        debug_summary=debug_summary,
        runtime_event_summary=build_runtime_event_summary(trace_items),
        error_context=None,
        workflow_trace=trace_items,
    )


async def run_agent_workflow_diagnostics(
    *,
    prompt: str,
    context: str | None,
    intent: INTENT_TYPE | None,
) -> AgentRunDiagnosticsResponse:
    normalized_context = (context or "").strip() or None
    preview = preview_agent_workflow(
        prompt=prompt,
        context=normalized_context,
        intent=intent,
    )
    preview_tool_snapshot = WorkspaceToolSnapshot(
        name=preview.workspace_tool_name,
        title=preview.workspace_tool.title if preview.workspace_tool is not None else None,
        reason=preview.workspace_tool_reason,
        category=preview.workspace_tool_category,
        output_kind=preview.workspace_tool_output_kind,
        error_code=preview.workspace_tool_error_code,
        descriptor=(
            preview.workspace_tool_descriptor.model_dump(mode="python")
            if preview.workspace_tool_descriptor is not None
            else None
        ),
        plan=dict(preview.workspace_tool_plan) if preview.workspace_tool_plan is not None else None,
    )
    executable, blocked_reason = _is_runtime_executable(preview)
    if not executable:
        preview_trace = normalize_trace_items([item.model_dump() for item in preview.workflow_trace])
        debug_summary = _build_debug_summary(
            trace_items=preview_trace,
            error=None,
            ui_status=preview.ui_status,
            blocked=True,
        )
        return AgentRunDiagnosticsResponse(
            ok=True,
            prompt=preview.prompt,
            intent=preview.intent,
            selected_route=preview.selected_route,
            run_action=preview.run_action,
            executable=False,
            executed=False,
            blocked_reason=blocked_reason,
            **build_workspace_tool_response_kwargs(preview_tool_snapshot),
            ui_status=preview.ui_status,
            planned_nodes=list(preview.planned_nodes),
            notes=list(preview.notes),
            debug_summary=debug_summary,
            runtime_event_summary=build_runtime_event_summary(preview_trace),
            error_context=_build_error_context(
                error=None,
                blocked_reason=blocked_reason,
                debug_summary=debug_summary,
                trace_items=preview_trace,
            ),
            workflow_trace=preview_trace,
        )

    result = await to_thread.run_sync(
        partial(
            run_agent,
            preview.prompt,
            normalized_context,
            session_id=None,
            intent=intent,
            emit_chat_message=False,
        )
    )
    runtime_trace = normalize_trace_items(result.workflow_trace)
    debug_summary = _build_debug_summary(
        trace_items=runtime_trace,
        error=result.error,
        ui_status=result.ui_status,
        blocked=False,
    )
    response_trace = runtime_trace or normalize_trace_items(
        [item.model_dump() for item in preview.workflow_trace]
    )
    runtime_tool_snapshot = WorkspaceToolSnapshot.from_state(result.state).merged_with(
        preview_tool_snapshot
    )
    return AgentRunDiagnosticsResponse(
        ok=result.ok,
        prompt=preview.prompt,
        intent=_coerce_intent(result.intent or preview.intent),
        selected_route=preview.selected_route,
        run_action=result.run_action or preview.run_action,
        executable=True,
        executed=True,
        blocked_reason=None,
        run_id=result.run_id,
        run_status=result.run_status,
        output=result.output or None,
        error=result.error,
        **build_workspace_tool_response_kwargs(runtime_tool_snapshot),
        ui_status=result.ui_status,
        planned_nodes=list(preview.planned_nodes),
        notes=list(preview.notes),
        debug_summary=debug_summary,
        runtime_event_summary=build_runtime_event_summary(response_trace),
        error_context=_build_error_context(
            error=result.error,
            blocked_reason=None,
            debug_summary=debug_summary,
            trace_items=response_trace,
        ),
        workflow_trace=response_trace,
    )
