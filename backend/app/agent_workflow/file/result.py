from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


RAW_FILE_PAYLOAD_KEYS = frozenset(
    {
        "raw_error",
        "stack_trace",
        "stderr",
        "stdout",
        "traceback",
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


def _sanitize_result_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_result_value(item)
            for key, item in value.items()
            if str(key).strip().lower() not in RAW_FILE_PAYLOAD_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_result_value(item) for item in value]
    return value


def _sanitize_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    sanitized = _sanitize_result_value(dict(value))
    return sanitized if isinstance(sanitized, dict) else {}


@dataclass(slots=True)
class FileWorkflowResult:
    ok: bool = True
    output: str = ""
    error: str | None = None
    ui_status: str | None = None
    stop_reason: str | None = None
    action_result: dict[str, object] | None = None
    workflow_trace: list[dict[str, object]] = field(default_factory=list)
    file_state: dict[str, object] = field(default_factory=dict)
    state: dict[str, object] = field(default_factory=dict)

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "FileWorkflowResult":
        error = _normalize_optional_text(state.get("error"))
        return cls(
            ok=error is None,
            output=_normalize_text(state.get("output")),
            error=error,
            ui_status=_normalize_optional_text(state.get("ui_status")),
            stop_reason=_normalize_optional_text(state.get("stop_reason")),
            action_result=_sanitize_mapping(state.get("action_result")) or None,
            workflow_trace=_coerce_mapping_list(state.get("workflow_trace")),
            file_state=_sanitize_mapping(state.get("file_state")),
            state=_sanitize_mapping(state),
        )

    @classmethod
    def from_error(
        cls,
        exc: Exception,
        state: Mapping[str, object],
    ) -> "FileWorkflowResult":
        error = str(exc).strip() or exc.__class__.__name__
        return cls(
            ok=False,
            output=f"File workflow 执行失败：{error}",
            error=error,
            ui_status="file_workflow_failed",
            stop_reason="failed",
            action_result=_sanitize_mapping(state.get("action_result")) or None,
            workflow_trace=_coerce_mapping_list(state.get("workflow_trace")),
            file_state=_sanitize_mapping(state.get("file_state")),
            state=_sanitize_mapping(state),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "output": self.output,
            "error": self.error,
            "ui_status": self.ui_status,
            "stop_reason": self.stop_reason,
            "action_result": dict(self.action_result) if self.action_result else None,
            "workflow_trace": [dict(item) for item in self.workflow_trace],
            "file_state": dict(self.file_state),
            "state": dict(self.state),
        }
