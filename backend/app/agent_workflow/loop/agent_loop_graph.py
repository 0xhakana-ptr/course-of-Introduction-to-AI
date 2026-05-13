"""Top-level turn controller for one `/chat` request.

This module keeps the existing LangGraph file name for import stability, but
its architectural role is now narrower than a full coding/debugging agent
brain. It should coordinate one user turn, choose a stable action or subflow,
emit node/action/terminal events, and guarantee a completed or failed terminal
status.

Do not grow PM/Coder/QA/Debugger internals here. Those coding/debug loops
belong in dedicated subgraphs, starting with `agent_workflow/coding/`, so their
engineering state can stay isolated from roleplay and frontend state.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from ...llm.client import call_llm_sync
from ...schemas import INTENT_TYPE
from ...services.chat_action.intent import detect_intent, detect_run_action, extract_run_reference
from ...storage.file_context_store import file_context_store
from ...tools.workspace_tools import (
    WORKSPACE_TOOL_NAME_COPY,
    WORKSPACE_TOOL_NAME_DELETE,
    WORKSPACE_TOOL_NAME_LIST,
    WORKSPACE_TOOL_NAME_MOVE,
    WORKSPACE_TOOL_NAME_OVERVIEW,
    WORKSPACE_TOOL_NAME_READ,
    WORKSPACE_TOOL_NAME_SEARCH,
    WORKSPACE_TOOL_NAME_TEST,
    WORKSPACE_TOOL_NAME_WRITE,
    normalize_workspace_tool_plan,
    plan_workspace_tool,
)
from ..actions import default_action_registry
from ..actions.models import AgentActionResult
from ..contracts.workflow_results import WorkflowAgentResult, invoke_graph_with_result
from ..coding import RUN_ACTIONS_FOR_CODING_WORKFLOW, SIMPLE_WORKSPACE_ACTIONS, run_coding_workflow
from ..file import (
    file_state_from_action_result,
    merge_file_context,
    prompt_references_file_context,
    resolve_prompt_file_references,
)
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
from .action_plan import ActionPlan
from .file_followups import (
    copy_action_from_file_context,
    initial_search_prompt_from_multistep,
    workspace_dynamic_followup_queue,
    workspace_followup_queue,
)
from .planning import (
    apply_overwrite_confirmation_to_action,
    build_recovery_action_plan,
    coerce_bool,
    coerce_int,
    make_action_plan,
    should_replan_after_failure,
    with_confirmation_guard,
)


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
    action_queue: list[dict[str, object]]
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
    file_context: dict[str, object]
    runtime_mode: str


WORKSPACE_ACTION_BY_TOOL_NAME = {
    WORKSPACE_TOOL_NAME_OVERVIEW: "workspace.overview",
    WORKSPACE_TOOL_NAME_READ: "workspace.read",
    WORKSPACE_TOOL_NAME_WRITE: "workspace.write",
    WORKSPACE_TOOL_NAME_LIST: "workspace.list",
    WORKSPACE_TOOL_NAME_TEST: "workspace.test",
    WORKSPACE_TOOL_NAME_MOVE: "workspace.move",
    WORKSPACE_TOOL_NAME_COPY: "workspace.copy",
    WORKSPACE_TOOL_NAME_DELETE: "workspace.delete",
    WORKSPACE_TOOL_NAME_SEARCH: "workspace.search",
}

WORKSPACE_ACTIONS_DISPATCHED_TO_CODING_WORKFLOW = set(SIMPLE_WORKSPACE_ACTIONS)
RUN_ACTIONS_DISPATCHED_TO_CODING_WORKFLOW = set(RUN_ACTIONS_FOR_CODING_WORKFLOW)
AGENT_ACTIONS_DISPATCHED_TO_CODING_WORKFLOW = (
    WORKSPACE_ACTIONS_DISPATCHED_TO_CODING_WORKFLOW
    | RUN_ACTIONS_DISPATCHED_TO_CODING_WORKFLOW
)

RUN_ACTION_TO_AGENT_ACTION = {
    RUN_ACTION_CREATE: "run.create",
    "inspect": "run.inspect",
    RUN_ACTION_RETRY: "run.retry",
    RUN_ACTION_RERUN: "run.rerun",
    RUN_ACTION_CANCEL: "run.cancel",
}

def _normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _coerce_action_result(value: object) -> dict[str, object]:
    if isinstance(value, AgentActionResult):
        return value.as_dict()
    return dict(value) if isinstance(value, dict) else {}


def _coerce_action_queue(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []

    queue: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        action_name = _normalize_text(item.get("action_name"))
        action_input = item.get("action_input")
        if not action_name:
            continue
        queue.append(
            {
                "action_name": action_name,
                "action_input": dict(action_input) if isinstance(action_input, dict) else {},
            }
        )
    return queue


def _workspace_action_from_prompt(
    prompt: str,
    file_context: object | None = None,
) -> tuple[str, dict[str, object], dict[str, object] | None]:
    contextual_copy = copy_action_from_file_context(prompt, file_context)
    if contextual_copy is not None:
        return contextual_copy

    planning_prompt, file_context_reference = resolve_prompt_file_references(
        prompt,
        file_context,
    )
    initial_search_prompt = initial_search_prompt_from_multistep(planning_prompt)
    if initial_search_prompt:
        planning_prompt = initial_search_prompt
    plan_model = normalize_workspace_tool_plan(plan_workspace_tool(planning_prompt))
    if plan_model is None:
        return "run.create", {"prompt": prompt}, None

    tool_name = _normalize_text(plan_model.tool_name, default=WORKSPACE_TOOL_NAME_OVERVIEW)
    tool_input = dict(plan_model.tool_input)
    workspace_plan = plan_model.as_dict()
    if file_context_reference:
        workspace_plan.update(
            {
                "file_context_reference": file_context_reference,
                "contextual_prompt": planning_prompt,
            }
        )
    if (
        tool_name == WORKSPACE_TOOL_NAME_WRITE
        and _normalize_text(tool_input.get("target_location")).lower() == "desktop"
    ):
        return "workspace.export_desktop", tool_input, workspace_plan

    action_name = WORKSPACE_ACTION_BY_TOOL_NAME.get(tool_name, "run.create")
    if bool(plan_model.terminal) or tool_name == WORKSPACE_TOOL_NAME_WRITE:
        return action_name, tool_input, workspace_plan

    return "run.create", {"prompt": prompt}, workspace_plan


def _contextual_workspace_action_from_prompt(
    prompt: str,
    file_context: object,
) -> tuple[str, dict[str, object], dict[str, object] | None] | None:
    if not prompt_references_file_context(prompt):
        return None
    action_name, action_input, workspace_plan = _workspace_action_from_prompt(
        prompt,
        file_context,
    )
    if action_name == "run.create":
        return None
    return action_name, action_input, workspace_plan


def _build_action_plan(state: AgentLoopState) -> ActionPlan:
    if coerce_bool(state.get("recovery_attempted")) and _normalize_text(state.get("recovery_reason")):
        return build_recovery_action_plan(state)

    prompt = _normalize_text(state.get("user_input"))
    intent = _normalize_text(state.get("intent"), default=detect_intent(prompt))
    file_context = state.get("file_context") or {}
    action_queue = _coerce_action_queue(state.get("action_queue"))
    if action_queue:
        next_action = action_queue[0]
        remaining_queue = action_queue[1:]
        action_name = _normalize_text(next_action.get("action_name"))
        action_input = dict(next_action.get("action_input") or {})
        action_input, _ = apply_overwrite_confirmation_to_action(
            prompt=prompt,
            action_name=action_name,
            action_input=action_input,
        )
        return with_confirmation_guard(
            prompt=prompt,
            plan=make_action_plan(
                action_name,
                action_input,
                reason="Agent Loop continues with the next queued action.",
                planner_source="queue",
                next_action_queue=remaining_queue,
                details={
                    "intent": intent,
                    "queued_action": True,
                },
            ),
        )

    contextual_workspace_action = _contextual_workspace_action_from_prompt(prompt, file_context)
    if contextual_workspace_action is not None:
        action_name, action_input, workspace_plan = contextual_workspace_action
        action_input, workspace_plan = apply_overwrite_confirmation_to_action(
            prompt=prompt,
            action_name=action_name,
            action_input=action_input,
            workspace_plan=workspace_plan,
        )
        followup_queue = workspace_followup_queue(
            prompt=prompt,
            action_name=action_name,
            action_input=action_input,
        )
        return with_confirmation_guard(
            prompt=prompt,
            plan=make_action_plan(
                action_name,
                action_input,
                reason="Prompt references recent file context and selected a workspace action.",
                next_action_queue=followup_queue,
                details={
                    "intent": "coding",
                    "resolved_intent": "coding",
                    "workspace_tool_plan": workspace_plan,
                    "file_context_used": True,
                },
            ),
        )

    if intent == "chat":
        return make_action_plan(
            "chat.reply",
            {"prompt": prompt, "context": state.get("context")},
            reason="Chat intent uses direct LLM reply action.",
            details={"intent": intent},
        )

    if intent == "coding":
        run_action = detect_run_action(prompt)
        target_run_id = extract_run_reference(prompt) if run_action != RUN_ACTION_CREATE else None
        if run_action != RUN_ACTION_CREATE:
            action_name = RUN_ACTION_TO_AGENT_ACTION.get(run_action, "run.inspect")
            return with_confirmation_guard(
                prompt=prompt,
                plan=make_action_plan(
                    action_name,
                    {"run_id": target_run_id},
                    reason=f"Coding prompt selected run control action `{run_action}`.",
                    details={
                        "intent": intent,
                        "run_action": run_action,
                        "target_run_id": target_run_id,
                    },
                ),
            )

        action_name, action_input, workspace_plan = _workspace_action_from_prompt(
            prompt,
            file_context,
        )
        action_input, workspace_plan = apply_overwrite_confirmation_to_action(
            prompt=prompt,
            action_name=action_name,
            action_input=action_input,
            workspace_plan=workspace_plan,
        )
        if action_name == "run.create":
            action_input = {
                "prompt": prompt,
                "context": state.get("context"),
            }
        followup_queue = workspace_followup_queue(
            prompt=prompt,
            action_name=action_name,
            action_input=action_input,
        )
        return with_confirmation_guard(
            prompt=prompt,
            plan=make_action_plan(
                action_name,
                action_input,
                reason=(
                    "Coding prompt selected a workspace action."
                    if workspace_plan is not None and action_name != "run.create"
                    else "Coding prompt selected run creation."
                ),
                next_action_queue=followup_queue,
                details={
                    "intent": intent,
                    "run_action": run_action,
                    "workspace_tool_plan": workspace_plan,
                },
            ),
        )

    return make_action_plan(
        "final.answer",
        {
            "content": (
                "我这次没有完全听懂你的意思。"
                "\n\n如果你只是想聊天，可以直接继续说；"
                "如果你想让我处理代码任务，可以补充目标、文件、报错或 run_id。"
            )
        },
        reason="Unknown intent falls back to final answer.",
        details={"intent": intent},
    )


def _build_plan(state: AgentLoopState) -> tuple[str, dict[str, object], dict[str, object]]:
    return _build_action_plan(state).as_legacy_tuple()


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
    state_updates: dict[str, object] = {}
    if "next_action_queue" in plan_details:
        state_updates["action_queue"] = _coerce_action_queue(
            plan_details.get("next_action_queue")
        )
    resolved_intent = _normalize_text(plan_details.get("resolved_intent"))
    if resolved_intent in {"chat", "coding", "unknown"}:
        state_updates["intent"] = resolved_intent
    next_state = merge_agent_state(
        state,
        action_name=action_name,
        action_input=action_input,
        target_run_id=action_input.get("run_id"),
        ui_status="loop_planned",
        **state_updates,
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


def _agent_action_result_from_mapping(
    value: object,
    *,
    fallback_action_name: str,
    fallback_summary: str,
    fallback_error: str | None,
    coding_workflow_trace: list[dict[str, object]],
) -> AgentActionResult:
    payload = dict(value) if isinstance(value, dict) else {}
    metadata = dict(payload.get("metadata")) if isinstance(payload.get("metadata"), dict) else {}
    metadata.update(
        {
            "workflow_name": "coding",
            "coding_workflow_trace": [dict(item) for item in coding_workflow_trace],
            "coding_workflow_node_names": [
                str(item.get("node") or "")
                for item in coding_workflow_trace
                if str(item.get("node") or "").strip()
            ],
        }
    )
    return AgentActionResult(
        action_name=_normalize_text(payload.get("action_name"), default=fallback_action_name),
        ok=bool(payload.get("ok")),
        summary=_normalize_text(payload.get("summary"), default=fallback_summary),
        data=payload.get("data"),
        error=(
            str(payload.get("error"))
            if payload.get("error") is not None
            else fallback_error
        ),
        metadata=metadata,
    )


def _execute_action_via_coding_workflow(state: AgentLoopState) -> AgentActionResult:
    action_name = _normalize_text(state.get("action_name"))
    action_input = dict(state.get("action_input") or {})
    workflow_kwargs: dict[str, object] = {}
    if action_name in WORKSPACE_ACTIONS_DISPATCHED_TO_CODING_WORKFLOW:
        workflow_kwargs.update(
            {
                "workspace_action_name": action_name,
                "workspace_action_input": action_input,
            }
        )
    elif action_name in RUN_ACTIONS_DISPATCHED_TO_CODING_WORKFLOW:
        workflow_kwargs.update(
            {
                "run_action_name": action_name,
                "run_action_input": action_input,
            }
        )
    result = run_coding_workflow(
        _normalize_text(state.get("user_input")),
        context=state.get("context"),
        session_id=state.get("session_id"),
        turn_id=state.get("turn_id"),
        **workflow_kwargs,
    )
    return _agent_action_result_from_mapping(
        result.action_result,
        fallback_action_name=action_name,
        fallback_summary=result.output,
        fallback_error=result.error,
        coding_workflow_trace=result.workflow_trace,
    )


def _execute_selected_action(state: AgentLoopState) -> AgentActionResult:
    action_name = _normalize_text(state.get("action_name"))
    if action_name == "chat.reply":
        return _execute_chat_reply(state)
    if action_name in AGENT_ACTIONS_DISPATCHED_TO_CODING_WORKFLOW:
        return _execute_action_via_coding_workflow(state)
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
    action_result_payload = result.as_dict()
    updates: dict[str, object] = {
        "action_result": action_result_payload,
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
        if result.ok:
            file_state_update = file_state_from_action_result(
                action_name,
                dict(state.get("action_input") or {}),
                action_result_payload,
            )
            if file_state_update:
                if _normalize_text(state.get("session_id")):
                    file_context = file_context_store.update_context(
                        state.get("session_id"),
                        file_state_update,
                    )
                else:
                    file_context = merge_file_context(
                        state.get("file_context"),
                        file_state_update,
                    )
                updates["file_context"] = file_context
                action_result_metadata = dict(action_result_payload.get("metadata") or {})
                action_result_metadata.update(
                    {
                        "file_state": file_state_update,
                        "file_context": file_context,
                    }
                )
                action_result_payload["metadata"] = action_result_metadata
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
    step_count = coerce_int(state.get("step_count"), default=0) + 1
    max_steps = coerce_int(state.get("max_steps"), default=3)
    should_replan, recovery_reason, recovery_message = should_replan_after_failure(
        state,
        action_result,
    )
    action_ok = bool(action_result.get("ok"))
    action_queue = _coerce_action_queue(state.get("action_queue"))
    if action_ok and not should_replan:
        action_queue.extend(
            workspace_dynamic_followup_queue(
                prompt=_normalize_text(state.get("user_input")),
                action_result=action_result,
            )
        )
    should_continue_queue = action_ok and not should_replan and bool(action_queue)
    done = not should_replan and not should_continue_queue
    if should_continue_queue:
        stop_reason = "queued_action"
    else:
        stop_reason = "recoverable_error" if should_replan else ("completed" if action_ok else "failed")
    observation = {
        "action_name": action_result.get("action_name"),
        "ok": action_ok,
        "summary": action_result.get("summary"),
        "error": action_result.get("error"),
        "recoverable": should_replan,
        "recovery_reason": recovery_reason,
        "queued_actions_remaining": len(action_queue),
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
        recovery_attempted=coerce_bool(state.get("recovery_attempted")) or should_replan,
        recovery_reason=recovery_reason or state.get("recovery_reason"),
        recovery_message=recovery_message or state.get("recovery_message"),
        action_queue=action_queue if should_continue_queue or should_replan else [],
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
    done = coerce_bool(state.get("done"))
    step_count = coerce_int(state.get("step_count"), default=0)
    max_steps = coerce_int(state.get("max_steps"), default=3)
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
    if not coerce_bool(state.get("done")):
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
    initial_state["action_queue"] = []
    initial_state["recovery_attempted"] = False
    initial_state["recovery_reason"] = None
    initial_state["recovery_message"] = None
    initial_state["file_context"] = file_context_store.get_context(session_id)
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
