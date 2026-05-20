from functools import partial

from anyio import to_thread

from ...schemas import (
    AgentDiagnosticsResponse,
    AgentRunDiagnosticsResponse,
    AgentWorkflowDebugSummary,
    AgentWorkflowErrorContext,
    INTENT_TYPE,
)
from ..actions import default_action_registry
from ..actions.workspace import WORKSPACE_ACTION_TOOL_MAP
from ..state.state_support import build_agent_initial_state
from ..graphs.loop_agent_loop_graph import plan_node, run_agent_loop
from .support import (
    WorkspaceToolSnapshot,
    build_workspace_tool_response_kwargs,
)
from .failure import build_failure_descriptor
from ..state.trace_runtime import (
    build_runtime_event_summary,
    find_failure_trace,
    normalize_trace_items,
    trace_items_from_state,
)


LOOP_DIAGNOSTICS_NOTE = (
    "该 diagnostics 使用 Agent Loop 主路径，与默认 /chat 运行路径对齐。"
)
LOOP_DIAGNOSTICS_EXECUTABLE_ACTIONS = {
    "chat.reply",
    "final.answer",
    "ask_user_confirmation",
    "run.inspect",
    "workspace.overview",
    "workspace.read",
    "workspace.list",
}
RUN_ACTION_BY_AGENT_ACTION = {
    "run.create": "create",
    "run.inspect": "inspect",
    "run.retry": "retry",
    "run.rerun": "rerun",
    "run.cancel": "cancel",
}


def _coerce_intent(value: object) -> INTENT_TYPE:
    normalized = str(value or "").strip()
    if normalized in {"chat", "coding", "unknown"}:
        return normalized
    return "unknown"


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _action_descriptor_kwargs(action_name: str | None) -> dict[str, object]:
    definition = default_action_registry.get(action_name or "")
    if definition is None:
        return {
            "action_name": action_name,
            "action_category": None,
            "action_safety_level": None,
            "requires_confirmation": None,
        }

    descriptor = definition.descriptor
    return {
        "action_name": descriptor.name,
        "action_category": descriptor.category,
        "action_safety_level": descriptor.safety_level,
        "requires_confirmation": descriptor.requires_confirmation,
    }


def _run_action_from_agent_action(action_name: str | None) -> str | None:
    return RUN_ACTION_BY_AGENT_ACTION.get(str(action_name or "").strip())


def _target_run_id_from_action_input(action_input: object) -> str | None:
    if not isinstance(action_input, dict):
        return None
    return _normalize_optional_text(action_input.get("run_id"))


def _workspace_tool_snapshot_from_loop_plan(
    *,
    action_name: str | None,
    action_input: object,
) -> WorkspaceToolSnapshot:
    tool_name = WORKSPACE_ACTION_TOOL_MAP.get(str(action_name or "").strip())
    if tool_name is None:
        return WorkspaceToolSnapshot()

    tool_input = dict(action_input) if isinstance(action_input, dict) else {}
    return WorkspaceToolSnapshot.from_state(
        {
            "workspace_tool_name": tool_name,
            "workspace_tool_reason": f"Agent Loop planned action `{action_name}`.",
            "workspace_tool_plan": {
                "tool_name": tool_name,
                "tool_input": tool_input,
                "reason": f"Agent Loop planned action `{action_name}`.",
                "terminal": True,
            },
        }
    )


def _loop_initial_state(
    *,
    prompt: str,
    context: str | None,
    intent: INTENT_TYPE | None,
) -> dict[str, object]:
    state = build_agent_initial_state(
        prompt=prompt,
        context=context,
        session_id=None,
        emit_chat_message=False,
        emit_node_events=False,
        intent=intent,
    )
    state["runtime_mode"] = "loop"
    state["step_count"] = 0
    state["max_steps"] = 3
    state["recovery_attempted"] = False
    state["recovery_reason"] = None
    state["recovery_message"] = None
    return state


def _preview_loop_state(
    *,
    prompt: str,
    context: str | None,
    intent: INTENT_TYPE | None,
) -> dict[str, object]:
    state = _loop_initial_state(prompt=prompt, context=context, intent=intent)
    return plan_node(state)


def _loop_planned_nodes(action_name: str | None) -> list[str]:
    terminal_node = "failure_node" if not action_name else "finalize_node"
    return [
        "plan_node",
        "act_node",
        "observe_node",
        "decide_continue_node",
        terminal_node,
    ]


def _loop_preview_notes(
    *,
    action_name: str | None,
    executable: bool,
    blocked_reason: str | None = None,
) -> list[str]:
    action_text = action_name or "unknown"
    notes = [
        LOOP_DIAGNOSTICS_NOTE,
        f"Agent Loop 当前计划执行 `{action_text}`。",
    ]
    if executable:
        notes.append("该动作可在 run diagnostics 中受控执行。")
    elif blocked_reason:
        notes.append(blocked_reason)
    return notes


def _phase_suggested_next_step(phase: str, *, blocked: bool) -> str:
    if blocked:
        return "继续使用 preview 观察路径，或改成 inspect / chat 分支进行安全运行期诊断。"

    return {
        "routing": "优先检查 perceive/plan 的 intent、action_name 和 action_input 是否符合预期。",
        "chat": "优先检查 LLM 配置、模型连通性和 chat.reply 的 error/output。",
        "coding": "优先检查 plan_node 生成的 action、run_id 和 workspace 输入清洗是否符合预期。",
        "tools": "优先检查 act/observe 的工具执行结果、目标路径和错误信息。",
        "run_create": "优先检查 run.create 调用参数、run 快照读取结果和任务创建收口。",
        "run_read": "优先检查 run_id、run.inspect 读取结果和终态/中间态分支判断。",
        "run_control": "优先检查 run action、目标 run 当前状态和控制动作是否允许执行。",
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


def _is_loop_runtime_executable(preview: AgentDiagnosticsResponse) -> tuple[bool, str | None]:
    action_name = str(preview.action_name or "").strip()
    if action_name in LOOP_DIAGNOSTICS_EXECUTABLE_ACTIONS:
        return True, None
    if not action_name:
        return False, "Agent Loop 未能规划出可执行动作，请先使用 preview 查看状态。"
    return False, (
        f"Loop diagnostics 已拦截 `{action_name}`：该动作可能产生副作用，"
        "请先使用 preview 观察计划，或通过正式 /chat 流程执行。"
    )


def preview_agent_workflow(
    *,
    prompt: str,
    context: str | None,
    intent: INTENT_TYPE | None,
) -> AgentDiagnosticsResponse:
    normalized_prompt = prompt.strip()
    normalized_context = (context or "").strip() or None
    final_state = _preview_loop_state(
        prompt=normalized_prompt,
        context=normalized_context,
        intent=intent,
    )
    action_name = _normalize_optional_text(final_state.get("action_name"))
    action_input = final_state.get("action_input")
    executable, blocked_reason = _is_loop_runtime_executable(
        AgentDiagnosticsResponse(
            ok=True,
            prompt=normalized_prompt,
            intent=_coerce_intent(final_state.get("intent")),
            selected_route="agent_loop",
            **_action_descriptor_kwargs(action_name),
        )
    )
    trace_items = trace_items_from_state(final_state)
    debug_summary = _build_debug_summary(
        trace_items=trace_items,
        error=None,
        ui_status=str(final_state.get("ui_status")) if final_state.get("ui_status") is not None else None,
        blocked=False,
    )
    tool_snapshot = _workspace_tool_snapshot_from_loop_plan(
        action_name=action_name,
        action_input=action_input,
    )

    return AgentDiagnosticsResponse(
        ok=True,
        prompt=normalized_prompt,
        intent=_coerce_intent(final_state.get("intent")),
        diagnostics_mode="loop",
        route_scope="primary_loop",
        selected_route="agent_loop",
        **_action_descriptor_kwargs(action_name),
        run_action=_run_action_from_agent_action(action_name),
        target_run_id=_target_run_id_from_action_input(action_input),
        **build_workspace_tool_response_kwargs(tool_snapshot),
        ui_status=str(final_state.get("ui_status")) if final_state.get("ui_status") is not None else None,
        planned_nodes=_loop_planned_nodes(action_name),
        notes=_loop_preview_notes(
            action_name=action_name,
            executable=executable,
            blocked_reason=blocked_reason,
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
    executable, blocked_reason = _is_loop_runtime_executable(preview)
    preview_trace = normalize_trace_items([item.model_dump() for item in preview.workflow_trace])
    if not executable:
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
            diagnostics_mode="loop",
            route_scope="primary_loop",
            selected_route=preview.selected_route,
            action_name=preview.action_name,
            action_category=preview.action_category,
            action_safety_level=preview.action_safety_level,
            requires_confirmation=preview.requires_confirmation,
            run_action=preview.run_action,
            executable=False,
            executed=False,
            blocked_reason=blocked_reason,
            **build_workspace_tool_response_kwargs(
                WorkspaceToolSnapshot(
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
            ),
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
            run_agent_loop,
            preview.prompt,
            normalized_context,
            session_id=None,
            intent=intent,
            emit_chat_message=False,
            emit_node_events=False,
        )
    )
    runtime_trace = normalize_trace_items(result.workflow_trace)
    debug_summary = _build_debug_summary(
        trace_items=runtime_trace,
        error=result.error,
        ui_status=result.ui_status,
        blocked=False,
    )
    response_trace = runtime_trace or preview_trace
    action_name = _normalize_optional_text(result.state.get("action_name")) or preview.action_name
    runtime_tool_snapshot = WorkspaceToolSnapshot.from_state(result.state).merged_with(
        WorkspaceToolSnapshot(
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
    )
    return AgentRunDiagnosticsResponse(
        ok=result.ok,
        prompt=preview.prompt,
        intent=_coerce_intent(result.intent or preview.intent),
        diagnostics_mode="loop",
        route_scope="primary_loop",
        selected_route=preview.selected_route,
        **_action_descriptor_kwargs(action_name),
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
