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
WORKSPACE_ACTION_MESSAGES = {
    "workspace.read": {
        "started": "正在读取文件...",
        "completed": "文件读取完成。",
        "failed": "文件读取失败。",
    },
    "workspace.write": {
        "started": "正在写入文件...",
        "completed": "文件写入完成。",
        "failed": "文件写入失败。",
    },
    "workspace.list": {
        "started": "正在列出目录...",
        "completed": "目录读取完成。",
        "failed": "目录读取失败。",
    },
    "workspace.move": {
        "started": "正在移动或重命名文件...",
        "completed": "文件移动/重命名完成。",
        "failed": "文件移动/重命名失败。",
    },
    "workspace.copy": {
        "started": "正在复制文件...",
        "completed": "文件复制完成。",
        "failed": "文件复制失败。",
    },
    "workspace.delete": {
        "started": "正在删除文件...",
        "completed": "文件删除完成。",
        "failed": "文件删除失败。",
    },
    "workspace.search": {
        "started": "正在搜索文件内容...",
        "completed": "文件搜索完成。",
        "failed": "文件搜索失败。",
    },
    "workspace.export_desktop": {
        "started": "正在准备桌面导出...",
        "completed": "桌面导出完成。",
        "failed": "桌面导出失败。",
    },
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


def _safe_action_field(value: object, *, limit: int = 160) -> str:
    text = _normalize_text(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _workspace_action_target_metadata(
    action_input: Mapping[str, object] | None,
    result: Mapping[str, object] | None,
) -> dict[str, object]:
    input_map = action_input if isinstance(action_input, Mapping) else {}
    result_data = result.get("data") if isinstance(result, Mapping) else None
    data_map = result_data if isinstance(result_data, Mapping) else {}
    metadata: dict[str, object] = {}

    for source_key, output_key in (
        ("rel_path", "action_rel_path"),
        ("source_path", "action_source_path"),
        ("target_path", "action_target_path"),
        ("query", "action_query"),
        ("target_location", "action_target_location"),
    ):
        value = input_map.get(source_key)
        if value is not None:
            metadata[output_key] = _safe_action_field(value)

    for source_key, output_key in (
        ("path", "result_path"),
        ("source_path", "result_source_path"),
        ("target_path", "result_target_path"),
        ("match_count", "result_match_count"),
    ):
        value = data_map.get(source_key)
        if value is not None:
            metadata[output_key] = (
                value if isinstance(value, int | float | bool) else _safe_action_field(value)
            )

    action_target = (
        metadata.get("action_target_path")
        or metadata.get("action_rel_path")
        or metadata.get("result_target_path")
        or metadata.get("result_path")
        or metadata.get("action_query")
    )
    if action_target is not None:
        metadata["action_target"] = action_target
    return metadata


def _action_status_message(action_name: str, action_status: str) -> str | None:
    status_messages = WORKSPACE_ACTION_MESSAGES.get(action_name)
    if status_messages is None:
        return None
    return status_messages.get(action_status)


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
        result_metadata = result.get("metadata")
        if isinstance(result_metadata, Mapping):
            for key in ("tool_name", "tool_output_kind", "tool_error_code"):
                value = result_metadata.get(key)
                if value is not None:
                    metadata[key] = _safe_action_field(value)
    if action_name.startswith("workspace."):
        metadata.update(_workspace_action_target_metadata(action_input, result))
        message = _action_status_message(action_name, action_status)
        if message is not None:
            metadata["quip"] = message
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
            message=_normalize_text(metadata.get("quip")) or None,
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
