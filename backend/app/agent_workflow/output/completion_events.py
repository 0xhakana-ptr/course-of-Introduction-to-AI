import logging
from collections.abc import Mapping

from ...messaging.message_sender import message_sender
from ...schemas import MESSAGE_STATUS
from ..contracts.workflow_nodes import get_workflow_node_metadata


logger = logging.getLogger(__name__)


FAILED_UI_STATUS_SUFFIXES = (
    "_failed",
    "_error",
)


def _should_emit_workflow_terminal_event(state: object) -> bool:
    if not isinstance(state, Mapping):
        return False
    return bool(state.get("emit_node_events", True))


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _workflow_has_failed(state: Mapping[str, object]) -> bool:
    if _normalize_optional_text(state.get("error")):
        return True

    ui_status = (_normalize_optional_text(state.get("ui_status")) or "").lower()
    return any(ui_status.endswith(suffix) for suffix in FAILED_UI_STATUS_SUFFIXES)


def _terminal_event_metadata(
    state: Mapping[str, object],
    *,
    node_name: str,
    runtime_event: str,
) -> dict[str, object]:
    metadata = get_workflow_node_metadata(node_name)
    result: dict[str, object] = {
        "node_label": metadata.get("label"),
        "phase": metadata.get("phase"),
        "runtime_event": runtime_event,
    }

    ui_status = _normalize_optional_text(state.get("ui_status"))
    if ui_status:
        result["ui_status"] = ui_status

    run_id = _normalize_optional_text(state.get("run_id"))
    if run_id:
        result["run_id"] = run_id

    run_status = _normalize_optional_text(state.get("run_status"))
    if run_status:
        result["run_status"] = run_status

    return result


def emit_workflow_terminal_status(
    state: object,
    *,
    node_name: str = "roleplay_node",
) -> bool:
    if not _should_emit_workflow_terminal_event(state):
        return False

    state_map = state if isinstance(state, Mapping) else {}
    failed = _workflow_has_failed(state_map)
    status: MESSAGE_STATUS = "error" if failed else "done"
    event_type = "workflow.failed" if failed else "workflow.completed"
    runtime_event = "workflow_failed" if failed else "workflow_completed"

    try:
        return message_sender.send_status(
            status,
            progress=None if failed else 100,
            node_name=node_name,
            metadata=_terminal_event_metadata(
                state_map,
                node_name=node_name,
                runtime_event=runtime_event,
            ),
            event_type=event_type,
            event_source="workflow",
            event_stage="roleplay",
        )
    except Exception:
        logger.exception("Failed to emit workflow terminal event: node=%s", node_name)
        return False
