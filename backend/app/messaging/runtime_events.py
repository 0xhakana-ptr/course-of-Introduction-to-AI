from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from ..schemas import MESSAGE_CHANNEL, MESSAGE_TYPE, MessageEnvelope
from .event_types import AGENT_EVENT_SOURCE, AGENT_EVENT_STAGE, AGENT_EVENT_TYPE


CHANNEL_BY_MESSAGE_TYPE: dict[MESSAGE_TYPE, MESSAGE_CHANNEL] = {
    "quip": "agent:quip",
    "expression": "agent:expression",
    "motion": "agent:motion",
    "chat": "agent:chat",
    "error": "agent:error",
    "status": "agent:status",
}


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


def normalize_frontend_message_payload(message: dict[str, Any]) -> dict[str, Any]:
    payload = dict(message)

    raw_type = payload.get("type")
    if isinstance(raw_type, str):
        inferred_channel = CHANNEL_BY_MESSAGE_TYPE.get(raw_type)  # type: ignore[arg-type]
        if inferred_channel is not None and payload.get("_channel") is None:
            payload["_channel"] = inferred_channel

    envelope = MessageEnvelope.model_validate(payload)
    return envelope.model_dump(by_alias=True, exclude_none=True)
