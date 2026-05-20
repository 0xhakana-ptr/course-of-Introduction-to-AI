from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from ..contracts.workflow_nodes import get_workflow_node_metadata


AgentRuntimeStopReason = Literal["completed", "failed", "cancelled", "unknown"]


ACTION_BY_EVENT: dict[str, str] = {
    "intent_routed": "workflow.route_intent",
    "llm_response_ready": "chat.reply",
    "llm_response_failed": "chat.reply",
    "coding_request_prepared": "workflow.prepare_coding",
    "workspace_tool_applied": "workspace.tool",
    "workspace_tool_failed": "workspace.tool",
    "workspace_tool_skipped": "workspace.tool",
    "run_created": "run.create",
    "run_create_failed": "run.create",
    "run_snapshot_ready": "run.inspect",
    "run_snapshot_in_progress": "run.inspect",
    "run_snapshot_terminal": "run.inspect",
    "run_snapshot_failed": "run.inspect",
    "run_control_done": "run.control",
    "run_control_failed": "run.control",
    "unknown_intent_done": "workflow.fallback",
    "roleplay_emit": "final.answer",
    "node_exception": "workflow.node",
    "loop_perceived": "workflow.perceive",
    "loop_planned": "workflow.plan",
    "loop_action_executed": "workflow.act",
    "loop_action_failed": "workflow.act",
    "loop_observed": "workflow.observe",
    "loop_decided": "workflow.decide",
    "loop_finalized": "final.answer",
    "loop_failed": "workflow.failure",
}


@dataclass(frozen=True, slots=True)
class AgentRuntimeAction:
    name: str
    node: str
    input: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "node": self.node,
            "input": dict(self.input),
        }


@dataclass(frozen=True, slots=True)
class AgentRuntimeObservation:
    status: Literal["ok", "error", "unknown"]
    summary: str
    details: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class AgentRuntimeStep:
    index: int
    node: str
    phase: str
    event: str
    ui_status: str | None
    action: AgentRuntimeAction
    observation: AgentRuntimeObservation

    def as_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "node": self.node,
            "phase": self.phase,
            "event": self.event,
            "ui_status": self.ui_status,
            "action": self.action.as_dict(),
            "observation": self.observation.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class AgentRuntimeTurn:
    turn_id: str | None
    session_id: str | None
    goal: str
    done: bool
    stop_reason: AgentRuntimeStopReason
    final_output: str
    steps: list[AgentRuntimeStep] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "done": self.done,
            "stop_reason": self.stop_reason,
            "final_output": self.final_output,
            "steps": [step.as_dict() for step in self.steps],
            "step_count": len(self.steps),
        }


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_text(value: object, *, default: str = "") -> str:
    return _normalize_optional_text(value) or default


def _coerce_mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _runtime_action_name(trace_entry: Mapping[str, object]) -> str:
    event = _normalize_text(trace_entry.get("event"), default="unknown")
    if event in {"loop_action_executed", "loop_action_failed"}:
        details = _coerce_mapping(trace_entry.get("details"))
        action_name = _normalize_optional_text(details.get("action_name"))
        if action_name:
            return action_name
    if event in {"workspace_tool_applied", "workspace_tool_failed"}:
        details = _coerce_mapping(trace_entry.get("details"))
        tool_name = _normalize_optional_text(details.get("tool_name"))
        return f"workspace.{tool_name}" if tool_name else ACTION_BY_EVENT[event]
    if event in {"run_control_done", "run_control_failed"}:
        details = _coerce_mapping(trace_entry.get("details"))
        action = _normalize_optional_text(details.get("action"))
        return f"run.{action}" if action else ACTION_BY_EVENT[event]
    return ACTION_BY_EVENT.get(event, "workflow.trace")


def _runtime_action_input(trace_entry: Mapping[str, object]) -> dict[str, object]:
    details = _coerce_mapping(trace_entry.get("details"))
    event = _normalize_text(trace_entry.get("event"), default="unknown")

    if event == "intent_routed":
        return {"intent": details.get("intent")}
    if event == "coding_request_prepared":
        return {
            "run_action": details.get("run_action"),
            "target_run_id": details.get("target_run_id"),
            "workspace_tool_name": details.get("workspace_tool_name"),
            "workspace_tool_terminal": details.get("workspace_tool_terminal"),
        }
    if event.startswith("workspace_tool_"):
        return {
            "tool_name": details.get("tool_name"),
            "tool_input": details.get("tool_input"),
            "terminal": details.get("terminal"),
        }
    if event.startswith("run_"):
        return {
            "run_id": details.get("run_id"),
            "status": details.get("status"),
            "action": details.get("action"),
        }
    if event == "loop_planned":
        return {
            "action_name": details.get("action_name"),
            "action_input": details.get("action_input"),
        }
    if event in {"loop_action_executed", "loop_action_failed"}:
        return {
            "action_name": details.get("action_name"),
        }
    if event == "node_exception":
        return {"error_type": details.get("error_type")}
    return {}


def _runtime_observation_status(
    trace_entry: Mapping[str, object],
) -> Literal["ok", "error", "unknown"]:
    event = _normalize_text(trace_entry.get("event"), default="unknown").lower()
    details = _coerce_mapping(trace_entry.get("details"))
    if "failed" in event or "exception" in event or bool(details.get("has_error")):
        return "error"
    if event == "unknown":
        return "unknown"
    return "ok"


def _runtime_observation_summary(trace_entry: Mapping[str, object]) -> str:
    message = _normalize_optional_text(trace_entry.get("message"))
    if message:
        return message

    event = _normalize_text(trace_entry.get("event"), default="workflow.trace")
    node = _normalize_text(trace_entry.get("node"), default="unknown")
    ui_status = _normalize_optional_text(trace_entry.get("ui_status"))
    if ui_status:
        return f"{node} finished {event} with ui_status={ui_status}."
    return f"{node} finished {event}."


def _resolve_phase(trace_entry: Mapping[str, object]) -> str:
    phase = _normalize_optional_text(trace_entry.get("phase"))
    if phase:
        return phase
    node = _normalize_text(trace_entry.get("node"), default="")
    return get_workflow_node_metadata(node).get("phase") or "unknown"


def build_runtime_step_from_trace_entry(trace_entry: Mapping[str, object]) -> AgentRuntimeStep:
    index = int(trace_entry.get("step") or trace_entry.get("index") or 0)
    node = _normalize_text(trace_entry.get("node"), default="unknown")
    event = _normalize_text(trace_entry.get("event"), default="workflow.trace")
    details = _coerce_mapping(trace_entry.get("details"))
    return AgentRuntimeStep(
        index=index,
        node=node,
        phase=_resolve_phase(trace_entry),
        event=event,
        ui_status=_normalize_optional_text(trace_entry.get("ui_status")),
        action=AgentRuntimeAction(
            name=_runtime_action_name(trace_entry),
            node=node,
            input=_runtime_action_input(trace_entry),
        ),
        observation=AgentRuntimeObservation(
            status=_runtime_observation_status(trace_entry),
            summary=_runtime_observation_summary(trace_entry),
            details=details,
        ),
    )


def build_runtime_steps_from_trace(trace_items: object) -> list[AgentRuntimeStep]:
    if not isinstance(trace_items, list):
        return []
    return [
        build_runtime_step_from_trace_entry(item)
        for item in trace_items
        if isinstance(item, Mapping)
    ]


def coerce_runtime_steps(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    steps: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, AgentRuntimeStep):
            steps.append(item.as_dict())
        elif isinstance(item, Mapping):
            steps.append(dict(item))
    return steps


def _resolve_stop_reason(state: Mapping[str, object], *, ok: bool) -> AgentRuntimeStopReason:
    if not ok:
        return "failed"
    ui_status = (_normalize_optional_text(state.get("ui_status")) or "").lower()
    if ui_status.endswith("failed") or ui_status.endswith("error"):
        return "failed"
    run_status = (_normalize_optional_text(state.get("run_status")) or "").lower()
    if run_status == "cancelled":
        return "cancelled"
    return "completed"


def build_runtime_turn_from_state(
    state: Mapping[str, object],
    *,
    ok: bool,
    workflow_trace: list[dict[str, object]] | None = None,
) -> AgentRuntimeTurn:
    trace_items = workflow_trace if workflow_trace is not None else []
    steps = build_runtime_steps_from_trace(trace_items)
    return AgentRuntimeTurn(
        turn_id=_normalize_optional_text(state.get("turn_id")),
        session_id=_normalize_optional_text(state.get("session_id")),
        goal=_normalize_text(state.get("user_input")),
        done=True,
        stop_reason=_resolve_stop_reason(state, ok=ok),
        final_output=_normalize_text(state.get("output")),
        steps=steps,
    )
