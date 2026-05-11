from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from ...llm.client import call_llm_sync
from ...schemas import INTENT_TYPE
from ...services.chat_action.intent import detect_intent, detect_run_action, extract_run_reference
from ...tools.workspace_tools import (
    WORKSPACE_TOOL_ERROR_EXECUTION_FAILED,
    WORKSPACE_TOOL_ERROR_TARGET_DISABLED,
    WORKSPACE_TOOL_ERROR_TARGET_UNSUPPORTED,
    WORKSPACE_TOOL_NAME_LIST,
    WORKSPACE_TOOL_NAME_OVERVIEW,
    WORKSPACE_TOOL_NAME_READ,
    WORKSPACE_TOOL_NAME_TEST,
    WORKSPACE_TOOL_NAME_WRITE,
    normalize_workspace_tool_plan,
    plan_workspace_tool,
)
from ..actions import default_action_registry
from ..actions.models import AgentActionResult
from ..contracts.workflow_results import WorkflowAgentResult, invoke_graph_with_result
from ..output.action_events import emit_workflow_action_event
from ..output.completion_events import emit_workflow_terminal_status
from ..output.node_events import emit_workflow_node_entered
from ..output.text import (
    build_run_control_output,
    build_run_creation_output_with_snapshot,
    build_run_snapshot_progress_output,
    build_run_terminal_output,
)
from ..state.constants import RUN_ACTION_CANCEL, RUN_ACTION_CREATE, RUN_ACTION_RERUN, RUN_ACTION_RETRY
from ..state.run_support import build_run_control_fallback_next_action
from ..state.state_support import (
    append_workflow_trace,
    build_agent_initial_state,
    build_workflow_node_failure_state,
    merge_agent_state,
)
from ..runtime.graph_nodes import register_agent_graph_nodes


class AgentLoopState(TypedDict, total=False):
    turn_id: str
    user_input: str
    context: str | None
    session_id: str | None
    intent: INTENT_TYPE
    emit_chat_message: bool
    emit_node_events: bool
    output: str
    error: str | None
    ui_status: str | None
    workflow_trace: list[dict[str, object]]
    action_name: str | None
    action_input: dict[str, object]
    action_result: dict[str, object] | None
    observation: dict[str, object] | None
    done: bool
    stop_reason: str | None
    step_count: int
    max_steps: int
    recovery_attempted: bool
    recovery_reason: str | None
    recovery_message: str | None
    run_id: str | None
    run_status: str | None
    run_action: str | None
    target_run_id: str | None
    workspace_tool_name: str | None
    workspace_tool_error: str | None
    workspace_tool_error_code: str | None
    runtime_mode: str


WORKSPACE_ACTION_BY_TOOL_NAME = {
    WORKSPACE_TOOL_NAME_OVERVIEW: "workspace.overview",
    WORKSPACE_TOOL_NAME_READ: "workspace.read",
    WORKSPACE_TOOL_NAME_WRITE: "workspace.write",
    WORKSPACE_TOOL_NAME_LIST: "workspace.list",
    WORKSPACE_TOOL_NAME_TEST: "workspace.test",
}

RUN_ACTION_TO_AGENT_ACTION = {
    RUN_ACTION_CREATE: "run.create",
    "inspect": "run.inspect",
    RUN_ACTION_RETRY: "run.retry",
    RUN_ACTION_RERUN: "run.rerun",
    RUN_ACTION_CANCEL: "run.cancel",
}

RUN_ACTIONS_REQUIRING_ID = {
    "run.inspect",
    "run.retry",
    "run.rerun",
    "run.cancel",
}

RECOVERY_REASON_DESKTOP_EXPORT_DISABLED = "desktop_export_disabled"
RECOVERY_REASON_FILE_EXISTS = "file_exists"
RECOVERY_REASON_MISSING_RUN_ID = "missing_run_id"
RECOVERY_REASON_UNSUPPORTED_WRITE_TARGET = "unsupported_write_target"


def _normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _coerce_action_result(value: object) -> dict[str, object]:
    if isinstance(value, AgentActionResult):
        return value.as_dict()
    return dict(value) if isinstance(value, dict) else {}


def _workspace_action_from_prompt(prompt: str) -> tuple[str, dict[str, object], dict[str, object] | None]:
    plan_model = normalize_workspace_tool_plan(plan_workspace_tool(prompt))
    if plan_model is None:
        return "run.create", {"prompt": prompt}, None

    tool_name = _normalize_text(plan_model.tool_name, default=WORKSPACE_TOOL_NAME_OVERVIEW)
    tool_input = dict(plan_model.tool_input)
    if (
        tool_name == WORKSPACE_TOOL_NAME_WRITE
        and _normalize_text(tool_input.get("target_location")).lower() == "desktop"
    ):
        return "workspace.export_desktop", tool_input, plan_model.as_dict()

    action_name = WORKSPACE_ACTION_BY_TOOL_NAME.get(tool_name, "run.create")
    if bool(plan_model.terminal) or tool_name == WORKSPACE_TOOL_NAME_WRITE:
        return action_name, tool_input, plan_model.as_dict()

    return "run.create", {"prompt": prompt}, plan_model.as_dict()


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce_int(value: object, *, default: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _is_file_exists_error(action_result: dict[str, object]) -> bool:
    error = _normalize_text(action_result.get("error")).lower()
    summary = _normalize_text(action_result.get("summary")).lower()
    return "file already exists" in error or "file already exists" in summary


def _build_recovery_message(
    *,
    reason: str,
    state: AgentLoopState,
    action_result: dict[str, object],
) -> str:
    action_input = state.get("action_input") or {}
    action_name = _normalize_text(state.get("action_name"))
    if reason == RECOVERY_REASON_DESKTOP_EXPORT_DISABLED:
        return (
            "我还不能直接导出到桌面，因为桌面导出没有启用或没有配置 "
            "`DESKTOP_EXPORT_DIR`。\n\n"
            "如果要继续，请先配置 `DESKTOP_EXPORT_ENABLED=true` 和 "
            "`DESKTOP_EXPORT_DIR`，或者让我改为创建到项目 workspace 里。"
        )
    if reason == RECOVERY_REASON_FILE_EXISTS:
        rel_path = _normalize_text(action_input.get("rel_path"), default="目标文件")
        target_location = _normalize_text(action_input.get("target_location"), default="workspace")
        target_label = "桌面导出目录" if target_location == "desktop" else "workspace"
        return (
            f"`{rel_path}` 在 {target_label} 中已经存在，我不会直接覆盖。\n\n"
            "如果你确认要覆盖，请明确告诉我“覆盖这个文件”；"
            "如果不想覆盖，请给我一个新的文件名。"
        )
    if reason == RECOVERY_REASON_MISSING_RUN_ID:
        action_label = action_name.split(".", 1)[1] if "." in action_name else action_name
        return (
            f"我需要一个明确的 `run_id` 才能继续执行 `{action_label}`。\n\n"
            "请把要处理的 `run_id` 发给我，我再继续查看、重试、重跑或取消。"
        )
    if reason == RECOVERY_REASON_UNSUPPORTED_WRITE_TARGET:
        return (
            "当前只支持写入项目 workspace，或显式配置过的桌面导出目录。\n\n"
            "请改为 workspace 路径，或先配置桌面导出目录。"
        )

    summary = _normalize_text(action_result.get("summary"), default="工具执行失败。")
    return f"这一步没有完成：{summary}"


def _recovery_reason_for_action_result(
    state: AgentLoopState,
    action_result: dict[str, object],
) -> str | None:
    if bool(action_result.get("ok")):
        return None

    action_name = _normalize_text(state.get("action_name"))
    action_input = state.get("action_input") or {}
    metadata = action_result.get("metadata")
    metadata_dict = dict(metadata) if isinstance(metadata, dict) else {}
    tool_error_code = _normalize_text(metadata_dict.get("tool_error_code"))

    if action_name == "workspace.export_desktop" and tool_error_code == WORKSPACE_TOOL_ERROR_TARGET_DISABLED:
        return RECOVERY_REASON_DESKTOP_EXPORT_DISABLED
    if action_name.startswith("workspace.") and tool_error_code == WORKSPACE_TOOL_ERROR_TARGET_UNSUPPORTED:
        return RECOVERY_REASON_UNSUPPORTED_WRITE_TARGET
    if (
        action_name.startswith("workspace.")
        and tool_error_code == WORKSPACE_TOOL_ERROR_EXECUTION_FAILED
        and _is_file_exists_error(action_result)
    ):
        return RECOVERY_REASON_FILE_EXISTS
    if action_name in RUN_ACTIONS_REQUIRING_ID and not _normalize_text(action_input.get("run_id")):
        return RECOVERY_REASON_MISSING_RUN_ID
    return None


def _should_replan_after_failure(
    state: AgentLoopState,
    action_result: dict[str, object],
) -> tuple[bool, str | None, str | None]:
    if _coerce_bool(state.get("recovery_attempted")):
        return False, None, None

    reason = _recovery_reason_for_action_result(state, action_result)
    if reason is None:
        return False, None, None

    message = _build_recovery_message(
        reason=reason,
        state=state,
        action_result=action_result,
    )
    return True, reason, message


def _build_recovery_plan(state: AgentLoopState) -> tuple[str, dict[str, object], dict[str, object]]:
    reason = _normalize_text(state.get("recovery_reason"))
    message = _normalize_text(state.get("recovery_message"), default="这一步需要你补充确认后才能继续。")

    if reason == RECOVERY_REASON_FILE_EXISTS:
        return "ask_user_confirmation", {"prompt": message}, {
            "reason": "Recoverable tool failure asks the user before overwrite.",
            "recovery_reason": reason,
        }

    return "final.answer", {"content": message}, {
        "reason": "Recoverable tool failure is converted to a clear final answer.",
        "recovery_reason": reason,
    }


def _build_plan(state: AgentLoopState) -> tuple[str, dict[str, object], dict[str, object]]:
    if _coerce_bool(state.get("recovery_attempted")) and _normalize_text(state.get("recovery_reason")):
        return _build_recovery_plan(state)

    prompt = _normalize_text(state.get("user_input"))
    intent = _normalize_text(state.get("intent"), default=detect_intent(prompt))

    if intent == "chat":
        return "chat.reply", {"prompt": prompt, "context": state.get("context")}, {
            "intent": intent,
            "reason": "Chat intent uses direct LLM reply action.",
        }

    if intent == "coding":
        run_action = detect_run_action(prompt)
        target_run_id = extract_run_reference(prompt) if run_action != RUN_ACTION_CREATE else None
        if run_action != RUN_ACTION_CREATE:
            action_name = RUN_ACTION_TO_AGENT_ACTION.get(run_action, "run.inspect")
            return action_name, {"run_id": target_run_id}, {
                "intent": intent,
                "run_action": run_action,
                "target_run_id": target_run_id,
            }

        action_name, action_input, workspace_plan = _workspace_action_from_prompt(prompt)
        if action_name == "run.create":
            action_input = {
                "prompt": prompt,
                "context": state.get("context"),
            }
        return action_name, action_input, {
            "intent": intent,
            "run_action": run_action,
            "workspace_tool_plan": workspace_plan,
        }

    return "final.answer", {
        "content": (
            "我这次没有完全听懂你的意思。"
            "\n\n如果你只是想聊天，可以直接继续说；"
            "如果你想让我处理代码任务，可以补充目标、文件、报错或 run_id。"
        )
    }, {"intent": intent, "reason": "Unknown intent falls back to final answer."}


def perceive_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "perceive_node")
    prompt = _normalize_text(state.get("user_input"))
    intent = _normalize_text(state.get("intent"), default=detect_intent(prompt))
    next_state = merge_agent_state(
        state,
        intent=intent,
        ui_status="loop_perceived",
    )
    return append_workflow_trace(
        next_state,
        node="perceive_node",
        event="loop_perceived",
        ui_status="loop_perceived",
        details={"intent": intent},
    )


def plan_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "plan_node")
    action_name, action_input, plan_details = _build_plan(state)
    next_state = merge_agent_state(
        state,
        action_name=action_name,
        action_input=action_input,
        target_run_id=action_input.get("run_id"),
        ui_status="loop_planned",
    )
    return append_workflow_trace(
        next_state,
        node="plan_node",
        event="loop_planned",
        ui_status="loop_planned",
        details={
            "action_name": action_name,
            "action_input": action_input,
            **plan_details,
        },
    )


def _execute_chat_reply(state: AgentLoopState) -> AgentActionResult:
    result = call_llm_sync(
        _normalize_text(state.get("user_input")),
        state.get("context"),
    )
    return AgentActionResult(
        action_name="chat.reply",
        ok=result.ok,
        summary=result.output,
        data={"content": result.output},
        error=result.error if not result.ok else None,
    )


def _execute_selected_action(state: AgentLoopState) -> AgentActionResult:
    action_name = _normalize_text(state.get("action_name"))
    if action_name == "chat.reply":
        return _execute_chat_reply(state)
    return default_action_registry.execute(
        action_name,
        state.get("action_input") or {},
    )


def _build_user_visible_run_action_output(
    *,
    action_name: str,
    result: AgentActionResult,
    data: dict[str, object],
    metadata: dict[str, object],
) -> str:
    action = action_name.split(".", 1)[1] if "." in action_name else action_name
    run_id = _normalize_text(metadata.get("run_id") or data.get("run_id"))
    status = _normalize_text(metadata.get("status") or data.get("status"), default="unknown")
    summary = _normalize_text(data.get("summary") or data.get("output"), default=result.summary)
    next_action = _normalize_text(data.get("next_action"))

    if not run_id:
        return result.summary

    if action == "create":
        return build_run_creation_output_with_snapshot(
            run_id=run_id,
            status=status,
            snapshot_summary=summary,
            next_action=next_action or "等待后台开始执行，然后继续查询任务状态。",
        )

    if action == "inspect":
        next_action = next_action or "需要时继续查询任务状态。"
        if bool(data.get("terminal")):
            return build_run_terminal_output(
                run_id=run_id,
                status=status,
                summary_text=summary,
                next_action=next_action,
            )
        return build_run_snapshot_progress_output(
            run_id=run_id,
            status=status,
            snapshot_summary=summary,
            next_action=next_action,
            latest_attempt_summary=_normalize_text(data.get("latest_attempt_summary")) or None,
            cancel_requested=bool(data.get("cancel_requested")),
        )

    if action in {RUN_ACTION_RETRY, RUN_ACTION_RERUN, RUN_ACTION_CANCEL}:
        source_run_id = _normalize_text(data.get("source_run_id")) or None
        return build_run_control_output(
            action=action,
            run_id=run_id,
            status=status,
            snapshot_summary=summary,
            next_action=next_action or build_run_control_fallback_next_action(action),
            source_run_id=source_run_id if source_run_id != run_id else None,
        )

    return result.summary


def _state_updates_from_action_result(
    state: AgentLoopState,
    result: AgentActionResult,
) -> dict[str, object]:
    action_name = _normalize_text(state.get("action_name"))
    data = result.data if isinstance(result.data, dict) else {}
    metadata = dict(result.metadata)
    updates: dict[str, object] = {
        "action_result": result.as_dict(),
        "output": result.summary,
        "error": None if result.ok else state.get("error"),
        "ui_status": "loop_action_done" if result.ok else "loop_action_failed",
    }

    if action_name.startswith("workspace."):
        updates.update(
            {
                "workspace_tool_name": metadata.get("tool_name"),
                "workspace_tool_error": result.error,
                "workspace_tool_error_code": metadata.get("tool_error_code"),
            }
        )
        if not result.ok:
            updates["ui_status"] = "workspace_tool_failed"
        return updates

    if action_name.startswith("run."):
        run_output = _build_user_visible_run_action_output(
            action_name=action_name,
            result=result,
            data=data,
            metadata=metadata,
        )
        updates.update(
            {
                "run_id": metadata.get("run_id") or data.get("run_id"),
                "run_status": metadata.get("status") or data.get("status"),
                "run_action": action_name.split(".", 1)[1],
                "output": run_output,
            }
        )
        if not result.ok:
            updates["error"] = result.error
            updates["ui_status"] = "run_action_failed"
        return updates

    if action_name == "chat.reply" and not result.ok:
        updates["error"] = result.error
        updates["ui_status"] = "chat_failed"

    return updates


def act_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "act_node")
    emit_workflow_action_event(state, action_status="started")
    result = _execute_selected_action(state)
    next_state = merge_agent_state(
        state,
        **_state_updates_from_action_result(state, result),
    )
    emit_workflow_action_event(
        next_state,
        action_status="completed" if result.ok else "failed",
        result=result.as_dict(),
    )
    return append_workflow_trace(
        next_state,
        node="act_node",
        event="loop_action_executed" if result.ok else "loop_action_failed",
        ui_status=_normalize_text(next_state.get("ui_status")),
        details={
            "action_name": state.get("action_name"),
            "ok": result.ok,
            "error": result.error,
            "metadata": dict(result.metadata),
        },
    )


def observe_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "observe_node")
    action_result = _coerce_action_result(state.get("action_result"))
    step_count = _coerce_int(state.get("step_count"), default=0) + 1
    max_steps = _coerce_int(state.get("max_steps"), default=3)
    should_replan, recovery_reason, recovery_message = _should_replan_after_failure(
        state,
        action_result,
    )
    action_ok = bool(action_result.get("ok"))
    done = not should_replan
    stop_reason = "recoverable_error" if should_replan else ("completed" if action_ok else "failed")
    observation = {
        "action_name": action_result.get("action_name"),
        "ok": action_ok,
        "summary": action_result.get("summary"),
        "error": action_result.get("error"),
        "recoverable": should_replan,
        "recovery_reason": recovery_reason,
    }
    state_error = state.get("error")
    if should_replan:
        state_error = None
    elif not action_ok:
        state_error = state_error or action_result.get("error") or action_result.get("summary")
    next_state = merge_agent_state(
        state,
        observation=observation,
        done=done,
        stop_reason=stop_reason,
        step_count=step_count,
        max_steps=max_steps,
        recovery_attempted=_coerce_bool(state.get("recovery_attempted")) or should_replan,
        recovery_reason=recovery_reason or state.get("recovery_reason"),
        recovery_message=recovery_message or state.get("recovery_message"),
        error=state_error,
        ui_status=_normalize_text(state.get("ui_status"), default="loop_observed"),
    )
    return append_workflow_trace(
        next_state,
        node="observe_node",
        event="loop_observed",
        ui_status=_normalize_text(next_state.get("ui_status")),
        details=observation,
    )


def decide_continue_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "decide_continue_node")
    done = _coerce_bool(state.get("done"))
    step_count = _coerce_int(state.get("step_count"), default=0)
    max_steps = _coerce_int(state.get("max_steps"), default=3)
    updates: dict[str, object] = {
        "done": done,
        "ui_status": _normalize_text(state.get("ui_status"), default="loop_decided"),
    }
    if not done and step_count >= max_steps:
        updates.update(
            {
                "done": True,
                "error": "Agent Loop reached max_steps before completing the task.",
                "stop_reason": "failed",
                "ui_status": "loop_max_steps",
            }
        )
    elif not done:
        updates.update(
            {
                "stop_reason": "replanning",
                "ui_status": "loop_replanning",
            }
        )
    next_state = merge_agent_state(
        state,
        **updates,
    )
    return append_workflow_trace(
        next_state,
        node="decide_continue_node",
        event="loop_decided",
        ui_status=_normalize_text(next_state.get("ui_status")),
        details={
            "done": bool(next_state.get("done")),
            "stop_reason": next_state.get("stop_reason") or "completed",
            "step_count": next_state.get("step_count"),
            "max_steps": next_state.get("max_steps"),
            "will_replan": not bool(next_state.get("done")) and not bool(next_state.get("error")),
        },
    )


def route_after_decision(state: AgentLoopState) -> str:
    if not _coerce_bool(state.get("done")):
        return "plan_node"
    if state.get("error"):
        return "failure_node"
    return "finalize_node"


def finalize_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "finalize_node")
    next_state = append_workflow_trace(
        state,
        node="finalize_node",
        event="loop_finalized",
        ui_status=_normalize_text(state.get("ui_status"), default="loop_finalized"),
        details={"stop_reason": state.get("stop_reason") or "completed"},
    )
    next_state = merge_agent_state(
        next_state,
        error=None,
        ui_status=_normalize_text(state.get("ui_status"), default="loop_finalized"),
    )
    next_state = append_workflow_trace(
        next_state,
        node="roleplay_node",
        event="roleplay_emit",
        ui_status=_normalize_text(next_state.get("ui_status")),
        details={"node_name": "agent_loop_roleplay"},
    )
    from ..output.roleplay import emit_roleplay_state

    emitted_state = emit_roleplay_state(
        next_state,
        default_node_name="agent_loop_roleplay",
    )
    emit_workflow_terminal_status(emitted_state, node_name="finalize_node")
    return emitted_state


def failure_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "failure_node")
    next_state = merge_agent_state(
        state,
        output=_normalize_text(state.get("output"), default="Agent Loop 执行失败。"),
        ui_status=_normalize_text(state.get("ui_status"), default="loop_failed"),
    )
    next_state = append_workflow_trace(
        next_state,
        node="failure_node",
        event="loop_failed",
        ui_status=_normalize_text(next_state.get("ui_status")),
        details={"error": state.get("error")},
    )
    emit_workflow_terminal_status(next_state, node_name="failure_node")
    return next_state


def create_agent_loop_graph():
    workflow = StateGraph(AgentLoopState)
    register_agent_graph_nodes(
        workflow,
        node_handlers={
            "perceive_node": perceive_node,
            "plan_node": plan_node,
            "act_node": act_node,
            "observe_node": observe_node,
            "decide_continue_node": decide_continue_node,
            "finalize_node": finalize_node,
            "failure_node": failure_node,
        },
        failure_builder=build_workflow_node_failure_state,
    )
    workflow.set_entry_point("perceive_node")
    workflow.add_edge("perceive_node", "plan_node")
    workflow.add_edge("plan_node", "act_node")
    workflow.add_edge("act_node", "observe_node")
    workflow.add_edge("observe_node", "decide_continue_node")
    workflow.add_conditional_edges(
        "decide_continue_node",
        route_after_decision,
        {
            "plan_node": "plan_node",
            "finalize_node": "finalize_node",
            "failure_node": "failure_node",
        },
    )
    workflow.add_edge("finalize_node", END)
    workflow.add_edge("failure_node", END)
    return workflow.compile()


agent_loop_graph = create_agent_loop_graph()


def run_agent_loop(
    prompt: str,
    context: str | None = None,
    *,
    session_id: str | None = None,
    intent: INTENT_TYPE | None = None,
    emit_chat_message: bool = True,
    emit_node_events: bool = True,
) -> WorkflowAgentResult:
    initial_state = build_agent_initial_state(
        prompt=prompt,
        context=context,
        session_id=session_id,
        emit_chat_message=emit_chat_message,
        emit_node_events=emit_node_events,
        intent=intent,
    )
    initial_state["runtime_mode"] = "loop"
    initial_state["step_count"] = 0
    initial_state["max_steps"] = 3
    initial_state["recovery_attempted"] = False
    initial_state["recovery_reason"] = None
    initial_state["recovery_message"] = None
    return invoke_graph_with_result(
        agent_loop_graph,
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
