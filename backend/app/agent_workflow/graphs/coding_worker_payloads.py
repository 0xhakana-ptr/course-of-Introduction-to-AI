from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..state.utils_shared import compact_text, normalize_text, safe_mapping, FORBIDDEN_WORKER_PAYLOAD_KEYS, MAX_WORKER_TEXT_CHARS


try:
    from langgraph.types import Send
except Exception:  # pragma: no cover - import guard for older LangGraph versions.
    Send = None  # type: ignore[assignment]


# FORBIDDEN_WORKER_PAYLOAD_KEYS and MAX_WORKER_TEXT_CHARS imported from ..utils.shared
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


# _normalize_text, _compact_text, _safe_mapping now from ..utils.shared


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
    user_input = compact_text(state.get("user_input"))
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
    current_task = compact_text(state.get("current_task"))
    project_context_preview = compact_text(state.get("context"))
    return _build_payload(
        target_node,
        state,
        {
            "current_task": current_task,
            "project_context_preview": project_context_preview or None,
            "workspace_action_name": normalize_text(state.get("workspace_action_name")) or None,
            "workspace_action_input": safe_mapping(state.get("workspace_action_input")),
            "run_action_name": normalize_text(state.get("run_action_name")) or None,
            "run_action_input": safe_mapping(state.get("run_action_input")),
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
            "executor_action_name": normalize_text(state.get("executor_action_name")) or None,
            "executor_action_input": safe_mapping(state.get("executor_action_input")),
            "coder_plan": safe_mapping(state.get("coder_plan")),
            "debugger_plan": safe_mapping(state.get("debugger_plan")),
            "repair_count": state.get("repair_count"),
        },
    )


def build_qa_worker_payload(state: Mapping[str, object], *, target_node: str) -> CodingWorkerPayload:
    # QA is the only node allowed to dereference raw_error_ref. The payload marks
    # the ref separately instead of exposing any raw artifact content.
    allowed = {
        "raw_error_ref": normalize_text(state.get("raw_error_ref")) or None,
        "current_task": compact_text(state.get("current_task")),
        "executor_action_name": normalize_text(state.get("executor_action_name")) or None,
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
    coder_plan = safe_mapping(state.get("coder_plan"))
    return _build_payload(
        target_node,
        state,
        {
            "current_task": compact_text(state.get("current_task")),
            "error_summary": compact_text(state.get("error_summary") or state.get("error")),
            "coder_plan": coder_plan,
            "executor_action_name": normalize_text(
                coder_plan.get("executor_action_name") or state.get("executor_action_name")
            )
            or None,
            "executor_action_input": (
                safe_mapping(coder_plan.get("executor_action_input"))
                or safe_mapping(state.get("executor_action_input"))
            ),
            "repair_count": state.get("repair_count"),
            "max_debug_steps": state.get("max_debug_steps"),
        },
    )
