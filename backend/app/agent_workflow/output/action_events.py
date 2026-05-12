import logging
from collections.abc import Mapping

from ...messaging.event_types import AGENT_EVENT_STAGE, AGENT_EVENT_TYPE
from ...messaging.message_sender import message_sender
from ..actions import default_action_registry


logger = logging.getLogger(__name__)


ACTION_EVENT_PROGRESS = {
    "started": 42,
    "completed": 68,
    "failed": 68,
}


def _normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _action_descriptor(action_name: str) -> dict[str, object]:
    definition = default_action_registry.get(action_name)
    if definition is None:
        return {
            "name": action_name,
            "category": "unknown",
            "safety_level": "unknown",
            "requires_confirmation": False,
            "user_visible_label": action_name or "未知动作",
        }
    return definition.descriptor.as_dict()


def _action_event_stage(descriptor: Mapping[str, object]) -> AGENT_EVENT_STAGE:
    action_name = _normalize_text(descriptor.get("name"))
    category = _normalize_text(descriptor.get("category"))

    if category == "chat":
        return "chat"
    if category == "workspace":
        return "tools"
    if action_name == "run.create":
        return "run_create"
    if action_name == "run.inspect":
        return "run_read"
    if category == "run":
        return "run_control"
    if category in {"character", "final"}:
        return "roleplay"
    if category == "confirmation":
        return "fallback"
    return "unknown"


def _action_event_type(action_status: str) -> AGENT_EVENT_TYPE:
    if action_status == "completed":
        return "workflow.action_completed"
    if action_status == "failed":
        return "workflow.action_failed"
    return "workflow.action_started"


def _confirmation_metadata(
    action_status: str,
    *,
    action_input: Mapping[str, object] | None = None,
    result: Mapping[str, object] | None = None,
) -> dict[str, object]:
    result_data = result.get("data") if isinstance(result, Mapping) else None
    result_metadata = result.get("metadata") if isinstance(result, Mapping) else None
    input_map = action_input if isinstance(action_input, Mapping) else {}
    data_map = result_data if isinstance(result_data, Mapping) else {}
    metadata_map = result_metadata if isinstance(result_metadata, Mapping) else {}

    prompt = (
        _normalize_text(input_map.get("prompt"))
        or _normalize_text(data_map.get("prompt"))
        or "请确认是否继续。"
    )
    blocked_action_name = (
        _normalize_text(input_map.get("blocked_action_name"))
        or _normalize_text(data_map.get("blocked_action_name"))
        or _normalize_text(metadata_map.get("blocked_action_name"))
    )
    blocked_action_input = input_map.get("blocked_action_input")
    if blocked_action_input is None:
        blocked_action_input = data_map.get("blocked_action_input")
    auth_status = {
        "started": "required",
        "completed": "completed",
        "failed": "failed",
    }.get(action_status, "required")

    metadata: dict[str, object] = {
        "auth_required": True,
        "auth_status": auth_status,
        "confirmation_prompt": prompt,
    }
    if blocked_action_name:
        metadata["blocked_action_name"] = blocked_action_name
    if isinstance(blocked_action_input, Mapping):
        metadata["blocked_action_input"] = dict(blocked_action_input)
    return metadata


def _action_event_metadata(
    action_name: str,
    *,
    action_status: str,
    action_input: Mapping[str, object] | None = None,
    result: Mapping[str, object] | None = None,
) -> dict[str, object]:
    descriptor = _action_descriptor(action_name)
    label = _normalize_text(
        descriptor.get("user_visible_label"),
        default=action_name or "未知动作",
    )
    metadata: dict[str, object] = {
        "node_label": label,
        "phase": _action_event_stage(descriptor),
        "runtime_event": f"action_{action_status}",
        "action_name": action_name,
        "action_label": label,
        "action_category": descriptor.get("category"),
        "safety_level": descriptor.get("safety_level"),
        "requires_confirmation": bool(descriptor.get("requires_confirmation")),
        "action_status": action_status,
    }
    if result is not None:
        metadata["ok"] = bool(result.get("ok"))
        error = _normalize_text(result.get("error"))
        if error:
            metadata["error"] = error
    if action_name == "ask_user_confirmation":
        metadata.update(
            _confirmation_metadata(
                action_status,
                action_input=action_input,
                result=result,
            )
        )
    return metadata


def emit_workflow_action_event(
    state: object,
    *,
    action_status: str,
    result: Mapping[str, object] | None = None,
) -> bool:
    if not isinstance(state, Mapping):
        return False
    if not bool(state.get("emit_node_events", True)):
        return False

    action_name = _normalize_text(state.get("action_name"))
    if not action_name:
        return False

    metadata = _action_event_metadata(
        action_name,
        action_status=action_status,
        action_input=(
            state.get("action_input")
            if isinstance(state.get("action_input"), Mapping)
            else None
        ),
        result=result,
    )
    try:
        return message_sender.send_status(
            "running",
            progress=ACTION_EVENT_PROGRESS.get(action_status, 50),
            node_name="act_node",
            metadata=metadata,
            event_type=_action_event_type(action_status),
            event_source="workflow",
            event_stage=metadata["phase"],  # type: ignore[arg-type]
        )
    except Exception:
        logger.exception(
            "Failed to emit workflow action event: action=%s status=%s",
            action_name,
            action_status,
        )
        return False
