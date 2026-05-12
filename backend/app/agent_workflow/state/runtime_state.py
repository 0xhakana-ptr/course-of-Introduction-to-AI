from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .display_state import FrontendState, JsonValue, sanitize_frontend_payload
from .engineering_state import EngineeringState


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_non_negative_int(value: object, *, default: int = 0) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _coerce_mapping(value: object) -> dict[str, JsonValue]:
    if not isinstance(value, Mapping):
        return {}
    jsonable = sanitize_frontend_payload(value)
    return jsonable if isinstance(jsonable, dict) else {}


def _coerce_mapping_list(value: object) -> list[dict[str, JsonValue]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    items: list[dict[str, JsonValue]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        jsonable = sanitize_frontend_payload(item)
        if isinstance(jsonable, dict):
            items.append(jsonable)
    return items


def _compact_dict(payload: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != [] and value != {}
    }


@dataclass(frozen=True, slots=True)
class TurnState:
    turn_id: str | None = None
    session_id: str | None = None
    user_input: str | None = None
    intent: str | None = None
    terminal_status: str | None = None

    @classmethod
    def from_mapping(cls, state: Mapping[str, object]) -> "TurnState":
        return cls(
            turn_id=_normalize_optional_text(state.get("turn_id")),
            session_id=_normalize_optional_text(state.get("session_id")),
            user_input=_normalize_optional_text(state.get("user_input") or state.get("prompt")),
            intent=_normalize_optional_text(state.get("intent")),
            terminal_status=_normalize_optional_text(
                state.get("terminal_status") or state.get("stop_reason")
            ),
        )

    def as_dict(self) -> dict[str, JsonValue]:
        return _compact_dict(
            {
                "turn_id": self.turn_id,
                "session_id": self.session_id,
                "user_input": self.user_input,
                "intent": self.intent,
                "terminal_status": self.terminal_status,
            }
        )


@dataclass(frozen=True, slots=True)
class ConversationState:
    recent_messages: list[dict[str, JsonValue]] = field(default_factory=list)
    compressed_summary: str | None = None
    external_context_preview: str | None = None

    @classmethod
    def from_mapping(cls, state: Mapping[str, object]) -> "ConversationState":
        return cls(
            recent_messages=_coerce_mapping_list(state.get("recent_messages")),
            compressed_summary=_normalize_optional_text(state.get("compressed_summary")),
            external_context_preview=_normalize_optional_text(state.get("external_context_preview")),
        )

    def as_dict(self) -> dict[str, JsonValue]:
        return _compact_dict(
            {
                "recent_messages": list(self.recent_messages),
                "compressed_summary": self.compressed_summary,
                "external_context_preview": self.external_context_preview,
            }
        )


@dataclass(frozen=True, slots=True)
class RuntimeState:
    action_plan: dict[str, JsonValue] = field(default_factory=dict)
    workflow_trace: list[dict[str, JsonValue]] = field(default_factory=list)
    node_events: list[dict[str, JsonValue]] = field(default_factory=list)
    stop_reason: str | None = None
    max_steps: int = 0
    step_count: int = 0

    @classmethod
    def from_mapping(cls, state: Mapping[str, object]) -> "RuntimeState":
        return cls(
            action_plan=_coerce_mapping(state.get("action_plan")),
            workflow_trace=_coerce_mapping_list(state.get("workflow_trace")),
            node_events=_coerce_mapping_list(state.get("node_events")),
            stop_reason=_normalize_optional_text(state.get("stop_reason")),
            max_steps=_coerce_non_negative_int(state.get("max_steps")),
            step_count=_coerce_non_negative_int(state.get("step_count")),
        )

    def as_dict(self) -> dict[str, JsonValue]:
        return _compact_dict(
            {
                "action_plan": self.action_plan,
                "workflow_trace": list(self.workflow_trace),
                "node_events": list(self.node_events),
                "stop_reason": self.stop_reason,
                "max_steps": self.max_steps,
                "step_count": self.step_count,
            }
        )


@dataclass(frozen=True, slots=True)
class ToolState:
    tool_name: str | None = None
    tool_input: dict[str, JsonValue] = field(default_factory=dict)
    tool_result_ref: str | None = None
    tool_error_code: str | None = None
    requires_confirmation: bool = False

    @classmethod
    def from_mapping(cls, state: Mapping[str, object]) -> "ToolState":
        tool_input = _coerce_mapping(state.get("tool_input") or state.get("action_input"))
        sanitized_tool_input = sanitize_frontend_payload(tool_input)
        return cls(
            tool_name=_normalize_optional_text(state.get("tool_name") or state.get("workspace_tool_name")),
            tool_input=sanitized_tool_input if isinstance(sanitized_tool_input, dict) else {},
            tool_result_ref=_normalize_optional_text(
                state.get("tool_result_ref") or state.get("tool_result_artifact_ref")
            ),
            tool_error_code=_normalize_optional_text(
                state.get("tool_error_code") or state.get("workspace_tool_error_code")
            ),
            requires_confirmation=bool(state.get("requires_confirmation")),
        )

    def as_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_result_ref": self.tool_result_ref,
            "tool_error_code": self.tool_error_code,
        }
        if self.requires_confirmation:
            payload["requires_confirmation"] = True
        return _compact_dict(payload)


@dataclass(frozen=True, slots=True)
class CodingWorkflowState:
    turn: TurnState = field(default_factory=TurnState)
    frontend: FrontendState = field(default_factory=FrontendState)
    conversation: ConversationState = field(default_factory=ConversationState)
    runtime: RuntimeState = field(default_factory=RuntimeState)
    engineering: EngineeringState = field(default_factory=EngineeringState)
    tool: ToolState = field(default_factory=ToolState)

    @classmethod
    def from_mapping(cls, state: Mapping[str, object]) -> "CodingWorkflowState":
        return cls(
            turn=TurnState.from_mapping(state),
            frontend=FrontendState.from_mapping(state),
            conversation=ConversationState.from_mapping(state),
            runtime=RuntimeState.from_mapping(state),
            engineering=EngineeringState.from_mapping(state),
            tool=ToolState.from_mapping(state),
        )

    def as_dict(self) -> dict[str, JsonValue]:
        return {
            "turn": self.turn.as_dict(),
            "frontend": self.frontend.as_dict(),
            "conversation": self.conversation.as_dict(),
            "runtime": self.runtime.as_dict(),
            "engineering": self.engineering.as_dict(),
            "tool": self.tool.as_dict(),
        }
