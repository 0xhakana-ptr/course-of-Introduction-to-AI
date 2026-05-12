from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


try:
    from langgraph.types import Send
except Exception:  # pragma: no cover - import guard for older LangGraph versions.
    Send = None  # type: ignore[assignment]


FORBIDDEN_WORKER_PAYLOAD_KEYS = frozenset(
    {
        "action_result",
        "artifact_content",
        "code_diff",
        "current_code",
        "current_code_or_patch",
        "debug_trace",
        "full_code",
        "llm_prompt",
        "raw_error",
        "raw_error_ref",
        "stack_trace",
        "stderr",
        "stdout",
        "tool_internal_stack_trace",
        "workflow_trace",
    }
)
MAX_WORKER_TEXT_CHARS = 1200
SEND_API_AVAILABLE = Send is not None


@dataclass(frozen=True, slots=True)
class CodingWorkerPayload:
    target_node: str
    payload: dict[str, object] = field(default_factory=dict)
    allowed_keys: tuple[str, ...] = field(default_factory=tuple)
    redacted_keys: tuple[str, ...] = field(default_factory=tuple)
    send_api_available: bool = SEND_API_AVAILABLE

    def as_dict(self) -> dict[str, object]:
        return {
            "target_node": self.target_node,
            "payload": dict(self.payload),
            "allowed_keys": list(self.allowed_keys),
            "redacted_keys": list(self.redacted_keys),
            "send_api_available": self.send_api_available,
        }

    def to_send(self) -> object:
        if Send is None:
            raise RuntimeError("LangGraph Send API is not available in this environment.")
        return Send(self.target_node, dict(self.payload))


def _normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _compact_text(value: object, *, limit: int = MAX_WORKER_TEXT_CHARS) -> str:
    text = _normalize_text(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _safe_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, object] = {}
    for key, item in value.items():
        normalized_key = _normalize_text(key)
        if not normalized_key or normalized_key in FORBIDDEN_WORKER_PAYLOAD_KEYS:
            continue
        if isinstance(item, str):
            result[normalized_key] = _compact_text(item)
        elif isinstance(item, int | float | bool) or item is None:
            result[normalized_key] = item
        elif isinstance(item, Mapping):
            nested = _safe_mapping(item)
            if nested:
                result[normalized_key] = nested
    return result


def _redacted_keys(state: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(
        sorted(
            key
            for key in FORBIDDEN_WORKER_PAYLOAD_KEYS
            if key in state and state.get(key) is not None
        )
    )


def _build_payload(
    target_node: str,
    state: Mapping[str, object],
    allowed: Mapping[str, object],
) -> CodingWorkerPayload:
    payload = {
        key: value
        for key, value in allowed.items()
        if key not in FORBIDDEN_WORKER_PAYLOAD_KEYS and value is not None
    }
    return CodingWorkerPayload(
        target_node=target_node,
        payload=payload,
        allowed_keys=tuple(payload.keys()),
        redacted_keys=_redacted_keys(state),
    )


def build_pm_worker_payload(state: Mapping[str, object], *, target_node: str) -> CodingWorkerPayload:
    user_input = _compact_text(state.get("user_input"))
    return _build_payload(
        target_node,
        state,
        {
            "user_requirement": user_input,
        },
    )


def build_coder_worker_payload(
    state: Mapping[str, object],
    *,
    target_node: str,
) -> CodingWorkerPayload:
    current_task = _compact_text(state.get("current_task"))
    project_context_preview = _compact_text(state.get("context"))
    return _build_payload(
        target_node,
        state,
        {
            "current_task": current_task,
            "project_context_preview": project_context_preview or None,
            "workspace_action_name": _normalize_text(state.get("workspace_action_name")) or None,
            "workspace_action_input": _safe_mapping(state.get("workspace_action_input")),
            "run_action_name": _normalize_text(state.get("run_action_name")) or None,
            "run_action_input": _safe_mapping(state.get("run_action_input")),
        },
    )


def build_executor_worker_payload(
    state: Mapping[str, object],
    *,
    target_node: str,
) -> CodingWorkerPayload:
    return _build_payload(
        target_node,
        state,
        {
            "executor_action_name": _normalize_text(state.get("executor_action_name")) or None,
            "executor_action_input": _safe_mapping(state.get("executor_action_input")),
            "coder_plan": _safe_mapping(state.get("coder_plan")),
            "debugger_plan": _safe_mapping(state.get("debugger_plan")),
            "repair_count": state.get("repair_count"),
        },
    )


def build_qa_worker_payload(state: Mapping[str, object], *, target_node: str) -> CodingWorkerPayload:
    # QA is the only node allowed to dereference raw_error_ref. The payload marks
    # the ref separately instead of exposing any raw artifact content.
    allowed = {
        "raw_error_ref": _normalize_text(state.get("raw_error_ref")) or None,
        "current_task": _compact_text(state.get("current_task")),
        "executor_action_name": _normalize_text(state.get("executor_action_name")) or None,
    }
    payload = CodingWorkerPayload(
        target_node=target_node,
        payload={key: value for key, value in allowed.items() if value is not None},
        allowed_keys=tuple(key for key, value in allowed.items() if value is not None),
        redacted_keys=tuple(
            key for key in _redacted_keys(state) if key != "raw_error_ref"
        ),
    )
    return payload


def build_debugger_worker_payload(
    state: Mapping[str, object],
    *,
    target_node: str,
) -> CodingWorkerPayload:
    coder_plan = _safe_mapping(state.get("coder_plan"))
    return _build_payload(
        target_node,
        state,
        {
            "current_task": _compact_text(state.get("current_task")),
            "error_summary": _compact_text(state.get("error_summary") or state.get("error")),
            "coder_plan": coder_plan,
            "executor_action_name": _normalize_text(
                coder_plan.get("executor_action_name") or state.get("executor_action_name")
            )
            or None,
            "executor_action_input": (
                _safe_mapping(coder_plan.get("executor_action_input"))
                or _safe_mapping(state.get("executor_action_input"))
            ),
            "repair_count": state.get("repair_count"),
            "max_debug_steps": state.get("max_debug_steps"),
        },
    )
