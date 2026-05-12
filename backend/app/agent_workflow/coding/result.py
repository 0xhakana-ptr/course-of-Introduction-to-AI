from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ..state import CodingWorkflowState

RAW_PAYLOAD_KEYS = frozenset(
    {
        "code_diff",
        "current_code",
        "current_code_or_patch",
        "debug_trace",
        "full_code",
        "raw_error",
        "stack_trace",
        "stderr",
        "stdout",
        "tool_internal_stack_trace",
    }
)


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_text(value: object, *, default: str = "") -> str:
    text = _normalize_optional_text(value)
    return text if text is not None else default


def _coerce_mapping_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _coerce_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _sanitize_result_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_result_value(item)
            for key, item in value.items()
            if str(key).strip().lower() not in RAW_PAYLOAD_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_result_value(item) for item in value]
    return value


def _sanitize_result_state(state: Mapping[str, object]) -> dict[str, object]:
    sanitized = _sanitize_result_value(dict(state))
    return sanitized if isinstance(sanitized, dict) else {}


def _sanitize_action_result(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    sanitized = _sanitize_result_value(dict(value))
    return sanitized if isinstance(sanitized, dict) else None


@dataclass(slots=True)
class CodingWorkflowResult:
    ok: bool = True
    output: str = ""
    error: str | None = None
    ui_status: str | None = None
    stop_reason: str | None = None
    tasks_list: list[str] = field(default_factory=list)
    current_task: str | None = None
    action_result: dict[str, object] | None = None
    workflow_trace: list[dict[str, object]] = field(default_factory=list)
    coding_state: dict[str, object] = field(default_factory=dict)
    state: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "CodingWorkflowResult":
        error = _normalize_optional_text(state.get("error"))
        coding_state = state.get("coding_state")
        if not isinstance(coding_state, Mapping):
            coding_state = CodingWorkflowState.from_mapping(state).as_dict()
        return cls(
            ok=error is None,
            output=_normalize_text(state.get("output")),
            error=error,
            ui_status=_normalize_optional_text(state.get("ui_status")),
            stop_reason=_normalize_optional_text(state.get("stop_reason")),
            tasks_list=_coerce_text_list(state.get("tasks_list")),
            current_task=_normalize_optional_text(state.get("current_task")),
            action_result=_sanitize_action_result(state.get("action_result")),
            workflow_trace=_coerce_mapping_list(state.get("workflow_trace")),
            coding_state=dict(coding_state),
            state=_sanitize_result_state(state),
        )

    @classmethod
    def from_error(
        cls,
        exc: Exception,
        state: Mapping[str, object],
    ) -> "CodingWorkflowResult":
        error = str(exc).strip() or exc.__class__.__name__
        return cls(
            ok=False,
            output=f"Coding workflow 执行失败：{error}",
            error=error,
            ui_status="coding_workflow_failed",
            stop_reason="failed",
            tasks_list=_coerce_text_list(state.get("tasks_list")),
            current_task=_normalize_optional_text(state.get("current_task")),
            action_result=_sanitize_action_result(state.get("action_result")),
            workflow_trace=_coerce_mapping_list(state.get("workflow_trace")),
            coding_state=CodingWorkflowState.from_mapping(state).as_dict(),
            state=_sanitize_result_state(state),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "output": self.output,
            "error": self.error,
            "ui_status": self.ui_status,
            "stop_reason": self.stop_reason,
            "tasks_list": list(self.tasks_list),
            "current_task": self.current_task,
            "action_result": dict(self.action_result) if self.action_result else None,
            "workflow_trace": [dict(item) for item in self.workflow_trace],
            "coding_state": dict(self.coding_state),
            "state": dict(self.state),
        }
