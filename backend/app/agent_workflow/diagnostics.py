from collections.abc import Mapping

from ..schemas import AgentDiagnosticsResponse, INTENT_TYPE
from ..services.chat_action.intent import detect_intent
from .agent_support import (
    append_workflow_trace,
    build_agent_initial_state,
    build_coding_requested_state,
    build_routed_state,
    select_agent_next_node,
    select_coding_next_node,
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

    workflow_trace = final_state.get("workflow_trace")
    trace_items = [
        dict(item)
        for item in workflow_trace
        if isinstance(workflow_trace, list) and isinstance(item, Mapping)
    ] if isinstance(workflow_trace, list) else []

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
        workspace_tool_name=(
            str(final_state.get("workspace_tool_name"))
            if final_state.get("workspace_tool_name") is not None
            else None
        ),
        workspace_tool_reason=(
            str(final_state.get("workspace_tool_reason"))
            if final_state.get("workspace_tool_reason") is not None
            else None
        ),
        workspace_tool_plan=(
            dict(final_state.get("workspace_tool_plan"))
            if isinstance(final_state.get("workspace_tool_plan"), Mapping)
            else None
        ),
        ui_status=str(final_state.get("ui_status")) if final_state.get("ui_status") is not None else None,
        planned_nodes=_build_planned_nodes(selected_route, coding_next_node),
        notes=_build_preview_notes(
            selected_route=selected_route,
            coding_next_node=coding_next_node,
            run_action=str(final_state.get("run_action")) if final_state.get("run_action") is not None else None,
        ),
        workflow_trace=trace_items,
    )
