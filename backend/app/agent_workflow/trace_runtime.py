from __future__ import annotations

from ..messaging.event_types import (
    AGENT_EVENT_SOURCE,
    AGENT_EVENT_STAGE,
    AGENT_EVENT_TYPE,
)
from ..messaging.runtime_events import build_runtime_event_fields
from .workflow_nodes import get_workflow_node_metadata


TRACE_RUNTIME_METADATA_BY_EVENT: dict[
    str,
    tuple[AGENT_EVENT_TYPE, AGENT_EVENT_SOURCE, AGENT_EVENT_STAGE],
] = {
    "intent_routed": ("workflow.intent_routed", "workflow", "routing"),
    "llm_response_ready": ("chat.response_ready", "chat", "chat"),
    "llm_response_failed": ("chat.response_failed", "chat", "chat"),
    "coding_request_prepared": ("workflow.coding_prepared", "workflow", "coding"),
    "workspace_tool_applied": ("tool.applied", "tool", "tools"),
    "workspace_tool_failed": ("tool.failed", "tool", "tools"),
    "workspace_tool_skipped": ("tool.skipped", "tool", "tools"),
    "run_created": ("run.created", "run", "run_create"),
    "run_create_failed": ("run.create_failed", "run", "run_create"),
    "run_snapshot_ready": ("run.snapshot_ready", "run", "run_read"),
    "run_snapshot_in_progress": ("run.snapshot_in_progress", "run", "run_read"),
    "run_snapshot_terminal": ("run.snapshot_terminal", "run", "run_read"),
    "run_snapshot_failed": ("run.snapshot_failed", "run", "run_read"),
    "run_control_done": ("run.control_completed", "run", "run_control"),
    "run_control_failed": ("run.control_failed", "run", "run_control"),
    "unknown_intent_done": ("workflow.unknown_intent_completed", "workflow", "fallback"),
    "roleplay_emit": ("roleplay.emitted", "roleplay", "roleplay"),
    "route_selected": ("diagnostics.route_selected", "diagnostics", "diagnostics"),
    "coding_path_selected": (
        "diagnostics.coding_path_selected",
        "diagnostics",
        "diagnostics",
    ),
}

TRACE_SOURCE_BY_PHASE: dict[str, AGENT_EVENT_SOURCE] = {
    "routing": "workflow",
    "chat": "chat",
    "coding": "workflow",
    "tools": "tool",
    "run_create": "run",
    "run_read": "run",
    "run_control": "run",
    "run": "run",
    "repair": "run",
    "fallback": "workflow",
    "roleplay": "roleplay",
    "diagnostics": "diagnostics",
    "system": "system",
    "unknown": "workflow",
}


def _resolve_stage_from_node(node: str) -> AGENT_EVENT_STAGE:
    phase = str(get_workflow_node_metadata(node).get("phase") or "unknown").strip()
    return phase if phase in TRACE_SOURCE_BY_PHASE else "unknown"


def _resolve_source_from_stage(stage: AGENT_EVENT_STAGE) -> AGENT_EVENT_SOURCE:
    return TRACE_SOURCE_BY_PHASE.get(stage, "workflow")


def build_trace_runtime_event_fields(
    *,
    node: str,
    event: str,
    frontend_visible: bool = False,
) -> dict[str, object]:
    if event == "node_exception":
        stage = _resolve_stage_from_node(node)
        return build_runtime_event_fields(
            event_type="workflow.node_exception",
            event_source=_resolve_source_from_stage(stage),
            event_stage=stage,
            frontend_visible=frontend_visible,
        )

    metadata = TRACE_RUNTIME_METADATA_BY_EVENT.get(event)
    if metadata is not None:
        event_type, event_source, event_stage = metadata
        return build_runtime_event_fields(
            event_type=event_type,
            event_source=event_source,
            event_stage=event_stage,
            frontend_visible=frontend_visible,
        )

    stage = _resolve_stage_from_node(node)
    return build_runtime_event_fields(
        event_type="workflow.trace",
        event_source=_resolve_source_from_stage(stage),
        event_stage=stage,
        frontend_visible=frontend_visible,
    )
