from collections.abc import Mapping

from .agent_constants import (
    RUN_ACTION_CREATE,
    RUN_ACTION_INSPECT,
)
from .agent_state_support import (
    append_workflow_trace,
    merge_agent_state,
    merge_context_sections,
    normalize_optional_text,
)
from .agent_text_support import (
    build_run_control_failure_output,
    build_run_control_output,
    build_run_creation_output_with_snapshot,
    build_run_snapshot_output,
    build_run_snapshot_progress_output,
    build_run_terminal_output,
    build_unknown_intent_output,
)
from ..services.chat_action.intent import detect_run_action, extract_run_reference
from ..tools.workspace_tools import (
    build_workspace_tool_context,
    execute_workspace_tool_plan,
    plan_workspace_tool,
)


def build_coding_requested_state(state: Mapping[str, object]) -> dict[str, object]:
    prompt = str(state.get("user_input") or "")
    run_action = detect_run_action(prompt)
    target_run_id = extract_run_reference(prompt) if run_action != RUN_ACTION_CREATE else None
    tool_plan = plan_workspace_tool(prompt) if run_action == RUN_ACTION_CREATE else None
    workspace_tool_name = None
    workspace_tool_reason = None
    if isinstance(tool_plan, Mapping):
        workspace_tool_name = normalize_optional_text(tool_plan.get("tool_name"))
        workspace_tool_reason = normalize_optional_text(tool_plan.get("reason"))

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
    tool_name = normalize_optional_text(tool_result.get("tool_name"))
    tool_reason = normalize_optional_text(tool_result.get("reason"))
    tool_error = normalize_optional_text(tool_result.get("error"))
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
