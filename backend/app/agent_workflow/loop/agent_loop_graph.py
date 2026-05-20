"""Layer 3 work engine: streamlined LangGraph agent loop.

This module keeps the original file name but is now drastically simplified:
- perceive_node removed (Layer 1 handles intent detection)
- plan_node passes through Layer 1 routing directly (no re-planning)
- Simple workspace/file actions go directly to the action registry
- Only run.create enters the coding subgraph for heavy code generation
- No duplicate planning logic
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from ...schemas import INTENT_TYPE
from ..actions import default_action_registry
from ..actions.models import AgentActionResult
from ..contracts.workflow_results import WorkflowAgentResult, invoke_graph_with_result
from ..coding import RUN_ACTIONS_FOR_CODING_WORKFLOW, run_coding_workflow
from ..output.action_events import emit_workflow_action_event
from ..output.completion_events import emit_workflow_terminal_status
from ..output.node_events import emit_workflow_node_entered
from ..state.state_support import (
    append_workflow_trace,
    build_agent_initial_state,
    build_workflow_node_failure_state,
    merge_agent_state,
)
from ..runtime.graph_nodes import register_agent_graph_nodes
from ..utils.shared import coerce_bool, coerce_int, normalize_text
from .action_plan import make_action_plan


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
    file_context: dict[str, object]
    runtime_mode: str


# Only run.create enters the heavy coding subgraph; all other actions go direct.
_CODING_WORKFLOW_ACTIONS: frozenset[str] = RUN_ACTIONS_FOR_CODING_WORKFLOW


# ---------------------------------------------------------------------------
# Plan node — pass through Layer 1 routing
# ---------------------------------------------------------------------------

def _build_action_plan_from_routing(state: AgentLoopState) -> "tuple[str, dict[str, object], dict[str, object]]":
    action_name = normalize_text(state.get("action_name"))
    action_input = dict(state.get("action_input") or {})
    if not action_name:
        raise ValueError("_build_action_plan_from_routing called without action_name")
    intent = normalize_text(state.get("intent"), default="coding")
    plan = make_action_plan(
        action_name,
        action_input,
        reason=f"Action plan built from upstream routing: {action_name}",
        details={"intent": intent, "routed": True},
    )
    return plan.as_legacy_tuple()


def plan_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "plan_node")
    action_name, action_input, plan_details = _build_action_plan_from_routing(state)

    state_updates: dict[str, object] = {}
    if "next_action_queue" in plan_details:
        state_updates["action_queue"] = (
            [dict(item) for item in plan_details["next_action_queue"]]
            if isinstance(plan_details.get("next_action_queue"), list)
            else []
        )
    resolved_intent = normalize_text(plan_details.get("resolved_intent"))
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
        details={"action_name": action_name, "action_input": action_input, **plan_details},
    )


# ---------------------------------------------------------------------------
# Act node — dispatch to action registry or coding subgraph
# ---------------------------------------------------------------------------

def _execute_selected_action(state: AgentLoopState) -> AgentActionResult:
    action_name = normalize_text(state.get("action_name"))
    # Only run.create goes through the heavy coding subgraph
    if action_name in _CODING_WORKFLOW_ACTIONS:
        return _execute_action_via_coding_workflow(state)
    return default_action_registry.execute(action_name, state.get("action_input") or {})


def _execute_action_via_coding_workflow(state: AgentLoopState) -> AgentActionResult:
    action_name = normalize_text(state.get("action_name"))
    action_input = dict(state.get("action_input") or {})
    result = run_coding_workflow(
        normalize_text(state.get("user_input")),
        context=state.get("context"),
        session_id=state.get("session_id"),
        turn_id=state.get("turn_id"),
        run_action_name=action_name,
        run_action_input=action_input,
    )
    raw = result.action_result
    payload = dict(raw) if isinstance(raw, dict) else {}
    metadata = dict(payload.get("metadata")) if isinstance(payload.get("metadata"), dict) else {}
    metadata.update({"workflow_name": "coding", "coding_workflow_trace": list(result.workflow_trace)})
    return AgentActionResult(
        action_name=normalize_text(payload.get("action_name"), default=action_name),
        ok=bool(payload.get("ok")),
        summary=normalize_text(payload.get("summary"), default=result.output),
        data=payload.get("data"),
        error=str(payload.get("error")) if payload.get("error") is not None else result.error,
        metadata=metadata,
    )


def act_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "act_node")
    emit_workflow_action_event(state, action_status="started")
    result = _execute_selected_action(state)
    next_state = merge_agent_state(
        state,
        action_result=result.as_dict(),
        output=result.summary,
        error=None if result.ok else state.get("error"),
        ui_status="loop_action_done" if result.ok else "loop_action_failed",
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
        ui_status=normalize_text(next_state.get("ui_status")),
        details={"action_name": state.get("action_name"), "ok": result.ok, "error": result.error},
    )


# ---------------------------------------------------------------------------
# Observe, Decide, Finalize, Failure nodes
# ---------------------------------------------------------------------------

def observe_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "observe_node")
    action_result = state.get("action_result") or {}
    ar = dict(action_result) if isinstance(action_result, dict) else {}
    step_count = coerce_int(state.get("step_count")) + 1
    max_steps = coerce_int(state.get("max_steps"), default=15)
    action_ok = bool(ar.get("ok"))
    # Simplified loop: one action per turn, always stop after execution
    done = True
    stop_reason = "completed" if action_ok else "failed"

    observation = {
        "action_name": ar.get("action_name"),
        "ok": action_ok,
        "summary": ar.get("summary"),
        "error": ar.get("error"),
    }
    next_state = merge_agent_state(
        state,
        observation=observation,
        done=done,
        stop_reason=stop_reason,
        step_count=step_count,
        max_steps=max_steps,
        error=None if action_ok else (state.get("error") or ar.get("error") or ar.get("summary")),
        ui_status=normalize_text(state.get("ui_status"), default="loop_observed"),
    )
    return append_workflow_trace(
        next_state,
        node="observe_node",
        event="loop_observed",
        ui_status=normalize_text(next_state.get("ui_status")),
        details=observation,
    )


def decide_continue_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "decide_continue_node")
    done = coerce_bool(state.get("done"))
    step_count = coerce_int(state.get("step_count"))
    max_steps = coerce_int(state.get("max_steps"), default=15)
    updates: dict[str, object] = {"done": done, "ui_status": "loop_decided"}
    if not done and step_count >= max_steps:
        updates.update({"done": True, "error": "Agent Loop reached max_steps.", "stop_reason": "failed", "ui_status": "loop_max_steps"})
    next_state = merge_agent_state(state, **updates)
    return append_workflow_trace(
        next_state,
        node="decide_continue_node",
        event="loop_decided",
        ui_status=normalize_text(next_state.get("ui_status")),
        details={"done": bool(next_state.get("done")), "stop_reason": next_state.get("stop_reason") or "completed", "step_count": next_state.get("step_count")},
    )


def route_after_decision(state: AgentLoopState) -> str:
    if not coerce_bool(state.get("done")):
        return "plan_node"
    return "failure_node" if state.get("error") else "finalize_node"


def finalize_node(state: AgentLoopState) -> AgentLoopState:
    emit_workflow_node_entered(state, "finalize_node")
    next_state = merge_agent_state(state, error=None, ui_status="work_engine_finalized")
    next_state = append_workflow_trace(next_state, node="finalize_node", event="work_engine_finalized", ui_status="work_engine_finalized", details={"stop_reason": state.get("stop_reason") or "completed"})
    emit_workflow_terminal_status(next_state, node_name="finalize_node")
    return next_state


def failure_node(state: AgentLoopState) -> AgentLoopState:
    next_state = merge_agent_state(state, output=normalize_text(state.get("output"), default="Agent Loop failed"), ui_status="work_engine_failed")
    next_state = append_workflow_trace(next_state, node="failure_node", event="work_engine_failed", ui_status="work_engine_failed", details={"error": state.get("error")})
    emit_workflow_terminal_status(next_state, node_name="failure_node")
    return next_state


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def create_agent_loop_graph():
    workflow = StateGraph(AgentLoopState)
    register_agent_graph_nodes(
        workflow,
        node_handlers={
            "plan_node": plan_node,
            "act_node": act_node,
            "observe_node": observe_node,
            "decide_continue_node": decide_continue_node,
            "finalize_node": finalize_node,
            "failure_node": failure_node,
        },
        failure_builder=build_workflow_node_failure_state,
    )
    # perceive_node removed — Layer 1 handles intent. Entry is plan_node which
    # passes through Layer 1 routing directly.
    workflow.set_entry_point("plan_node")
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


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_agent_loop(
    prompt: str,
    context: str | None = None,
    *,
    session_id: str | None = None,
    intent: INTENT_TYPE | None = None,
    emit_chat_message: bool = True,
    emit_node_events: bool = True,
    action_name: str | None = None,
    action_input: dict[str, object] | None = None,
) -> WorkflowAgentResult:
    initial_state = build_agent_initial_state(
        prompt=prompt, context=context, session_id=session_id,
        emit_chat_message=emit_chat_message, emit_node_events=emit_node_events,
        intent=intent,
    )
    if action_name:
        initial_state["action_name"] = action_name
    if action_input:
        initial_state["action_input"] = action_input
    initial_state["runtime_mode"] = "loop"
    initial_state["step_count"] = 0
    initial_state["max_steps"] = 15
    initial_state["action_queue"] = []
    initial_state["recovery_attempted"] = False
    initial_state["recovery_reason"] = None
    initial_state["recovery_message"] = None
    initial_state["file_context"] = {}
    return invoke_graph_with_result(
        agent_loop_graph,
        initial_state=initial_state,
        on_success=lambda result: WorkflowAgentResult.from_state(result, default_intent=intent or "unknown"),
        on_error=lambda exc, state: WorkflowAgentResult.from_error(exc, state, default_intent=intent or "unknown"),
    )
