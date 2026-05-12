from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

from ..schemas import MESSAGE_CHANNEL, MESSAGE_TYPE, MessageEnvelope
from .event_types import (
    AGENT_EVENT_SOURCE,
    AGENT_EVENT_STAGE,
    AGENT_EVENT_TYPE,
    BRIDGE_EVENT_TYPE,
)


BRIDGE_EVENT_VERSION = "1.0"
AUTH_CONFIRMATION_ACTION = "ask_user_confirmation"

ROLEPLAY_MESSAGE_TYPES = {"chat", "quip", "expression", "motion"}
ROLEPLAY_EVENT_TYPES = {
    "chat.message",
    "character.quip",
    "character.expression",
    "character.motion",
    "roleplay.emitted",
}
SENSITIVE_BRIDGE_KEY_PARTS = (
    "api_key",
    "artifact_content",
    "code_diff",
    "current_code",
    "full_code",
    "llm_prompt",
    "password",
    "raw_error",
    "secret",
    "stack_trace",
    "stderr",
    "stdout",
    "token",
    "traceback",
)
MAX_BRIDGE_STRING_LENGTH = 800
MAX_BRIDGE_LIST_ITEMS = 20
MAX_BRIDGE_DEPTH = 4


CHANNEL_BY_MESSAGE_TYPE: dict[MESSAGE_TYPE, MESSAGE_CHANNEL] = {
    "quip": "agent:quip",
    "expression": "agent:expression",
    "motion": "agent:motion",
    "chat": "agent:chat",
    "error": "agent:error",
    "status": "agent:status",
}


def require_channel_for_message_type(message_type: MESSAGE_TYPE) -> MESSAGE_CHANNEL:
    return CHANNEL_BY_MESSAGE_TYPE[message_type]


class RuntimeEventInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: AGENT_EVENT_TYPE
    event_source: AGENT_EVENT_SOURCE
    event_stage: AGENT_EVENT_STAGE
    frontend_visible: bool = True


def build_runtime_event_fields(
    *,
    event_type: AGENT_EVENT_TYPE,
    event_source: AGENT_EVENT_SOURCE,
    event_stage: AGENT_EVENT_STAGE,
    frontend_visible: bool = True,
) -> dict[str, object]:
    info = RuntimeEventInfo(
        event_type=event_type,
        event_source=event_source,
        event_stage=event_stage,
        frontend_visible=frontend_visible,
    )
    return info.model_dump()


def _normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _is_sensitive_bridge_key(key: object) -> bool:
    normalized = str(key or "").strip().lower()
    return any(part in normalized for part in SENSITIVE_BRIDGE_KEY_PARTS)


def _sanitize_bridge_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= MAX_BRIDGE_DEPTH:
        return "[truncated]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_bridge_key(key):
                continue
            result[str(key)] = _sanitize_bridge_value(item, depth=depth + 1)
        return result
    if isinstance(value, list | tuple):
        return [
            _sanitize_bridge_value(item, depth=depth + 1)
            for item in list(value)[:MAX_BRIDGE_LIST_ITEMS]
        ]
    if isinstance(value, str):
        if len(value) > MAX_BRIDGE_STRING_LENGTH:
            return f"{value[:MAX_BRIDGE_STRING_LENGTH]}..."
        return value
    if isinstance(value, int | float | bool) or value is None:
        return value
    return _normalize_text(value)


def derive_bridge_event_type(message: Mapping[str, Any]) -> BRIDGE_EVENT_TYPE:
    metadata = _as_mapping(message.get("metadata"))
    message_type = _normalize_text(message.get("type"))
    event_type = _normalize_text(message.get("event_type"))
    action_name = _normalize_text(metadata.get("action_name"))

    if (
        event_type == "workflow.auth_required"
        or action_name == AUTH_CONFIRMATION_ACTION
        or bool(metadata.get("auth_required"))
    ):
        return "Auth_Request"
    if message_type in ROLEPLAY_MESSAGE_TYPES or event_type in ROLEPLAY_EVENT_TYPES:
        return "Roleplay_Dialogue"
    return "Status_Update"


def _bridge_common_payload(message: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _as_mapping(message.get("metadata"))
    payload: dict[str, Any] = {
        "type": message.get("type"),
        "event_type": message.get("event_type"),
        "event_source": message.get("event_source"),
        "event_stage": message.get("event_stage"),
        "node_name": message.get("node_name"),
        "timestamp": message.get("timestamp"),
        "phase": metadata.get("phase") or message.get("event_stage"),
        "runtime_event": metadata.get("runtime_event"),
    }
    sanitized_metadata = _sanitize_bridge_value(metadata)
    if sanitized_metadata:
        payload["metadata"] = sanitized_metadata
    return {key: value for key, value in payload.items() if value is not None}


def _build_status_bridge_payload(message: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _as_mapping(message.get("metadata"))
    payload = _bridge_common_payload(message)
    for key in (
        "status",
        "progress",
        "code",
        "message",
    ):
        value = message.get(key)
        if value is not None:
            payload[key] = _sanitize_bridge_value(value)

    for key in (
        "action_name",
        "action_label",
        "action_status",
        "action_category",
        "safety_level",
        "run_id",
        "run_status",
        "ui_status",
        "workflow_name",
    ):
        value = metadata.get(key)
        if value is not None:
            payload[key] = _sanitize_bridge_value(value)

    return payload


def _build_roleplay_bridge_payload(message: Mapping[str, Any]) -> dict[str, Any]:
    payload = _bridge_common_payload(message)
    for key in (
        "role",
        "content",
        "expression",
        "motion",
        "mode",
        "intensity",
    ):
        value = message.get(key)
        if value is not None:
            payload[key] = _sanitize_bridge_value(value)
    return payload


def _build_auth_bridge_payload(message: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _as_mapping(message.get("metadata"))
    payload = _bridge_common_payload(message)
    prompt = metadata.get("confirmation_prompt") or metadata.get("prompt") or message.get("content")
    if prompt is not None:
        payload["prompt"] = _sanitize_bridge_value(prompt)
    blocked_action_name = metadata.get("blocked_action_name")
    if blocked_action_name is not None:
        payload["blocked_action_name"] = _sanitize_bridge_value(blocked_action_name)
    blocked_action_input = metadata.get("blocked_action_input")
    if blocked_action_input is not None:
        payload["blocked_action_input"] = _sanitize_bridge_value(blocked_action_input)
    payload["auth_required"] = True
    payload["auth_status"] = metadata.get("auth_status") or "required"
    return payload


def build_bridge_payload(
    message: Mapping[str, Any],
    bridge_event_type: BRIDGE_EVENT_TYPE,
) -> dict[str, Any]:
    if bridge_event_type == "Auth_Request":
        return _build_auth_bridge_payload(message)
    if bridge_event_type == "Roleplay_Dialogue":
        return _build_roleplay_bridge_payload(message)
    return _build_status_bridge_payload(message)


def build_bridge_event_fields(message: Mapping[str, Any]) -> dict[str, object]:
    raw_bridge_event_type = _normalize_text(message.get("bridge_event_type"))
    bridge_event_type: BRIDGE_EVENT_TYPE
    if raw_bridge_event_type in {"Status_Update", "Roleplay_Dialogue", "Auth_Request"}:
        bridge_event_type = raw_bridge_event_type  # type: ignore[assignment]
    else:
        bridge_event_type = derive_bridge_event_type(message)

    existing_payload = message.get("bridge_payload")
    bridge_payload = (
        _sanitize_bridge_value(existing_payload)
        if isinstance(existing_payload, Mapping)
        else build_bridge_payload(message, bridge_event_type)
    )

    return {
        "bridge_event_type": bridge_event_type,
        "bridge_event_version": _normalize_text(
            message.get("bridge_event_version"),
            default=BRIDGE_EVENT_VERSION,
        ),
        "bridge_payload": bridge_payload,
    }


def normalize_frontend_message_payload(message: dict[str, Any]) -> dict[str, Any]:
    payload = dict(message)

    raw_type = payload.get("type")
    if isinstance(raw_type, str):
        inferred_channel = CHANNEL_BY_MESSAGE_TYPE.get(raw_type)  # type: ignore[arg-type]
        if inferred_channel is not None and payload.get("_channel") is None:
            payload["_channel"] = inferred_channel

    payload.update(build_bridge_event_fields(payload))
    envelope = MessageEnvelope.model_validate(payload)
    return envelope.model_dump(by_alias=True, exclude_none=True)
