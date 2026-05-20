from __future__ import annotations

from collections.abc import Mapping

from ...messaging.event_types import (
    AGENT_EVENT_SOURCE,
    AGENT_EVENT_STAGE,
    AGENT_EVENT_TYPE,
)
from ...messaging.runtime_events import build_runtime_event_fields
from ...schemas import AgentWorkflowRuntimeEventSummary
from .trace_messages import (
    build_trace_event_label,
    build_trace_message,
    build_trace_status_level,
)
from ..contracts.workflow_nodes import get_workflow_node_metadata


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


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def coerce_workflow_trace_items(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [
        dict(item)
        for item in value
        if isinstance(item, Mapping)
    ]


def build_workflow_trace_entry(
    *,
    step: int,
    node: str,
    event: str,
    ui_status: str | None = None,
    details: Mapping[str, object] | None = None,
    frontend_visible: bool = False,
) -> dict[str, object]:
    return {
        "step": step,
        "node": node,
        "event": event,
        **build_trace_runtime_event_fields(
            node=node,
            event=event,
            frontend_visible=frontend_visible,
        ),
        "ui_status": ui_status,
        "details": dict(details) if details else None,
    }


def enrich_trace_item(item: Mapping[str, object]) -> dict[str, object]:
    enriched_item = dict(item)
    metadata = get_workflow_node_metadata(str(item.get("node") or ""))
    enriched_item["node_label"] = metadata.get("label")
    enriched_item["phase"] = metadata.get("phase")
    event = str(item.get("event") or "").strip()
    runtime_fields = build_trace_runtime_event_fields(
        node=str(item.get("node") or ""),
        event=event,
        frontend_visible=bool(item.get("frontend_visible", False)),
    )
    for key, value in runtime_fields.items():
        if enriched_item.get(key) is None:
            enriched_item[key] = value
    enriched_item["event_label"] = build_trace_event_label(event)
    enriched_item["status_level"] = build_trace_status_level(event)
    enriched_item["message"] = build_trace_message(enriched_item)
    return enriched_item


def normalize_trace_items(trace_items: object) -> list[dict[str, object]]:
    if not isinstance(trace_items, list):
        return []
    return [
        enrich_trace_item(item)
        for item in trace_items
        if isinstance(item, Mapping)
    ]


def trace_items_from_state(state: Mapping[str, object]) -> list[dict[str, object]]:
    return normalize_trace_items(state.get("workflow_trace"))


def find_failure_trace(trace_items: list[dict[str, object]]) -> dict[str, object] | None:
    for item in reversed(trace_items):
        event = str(item.get("event") or "").strip()
        details = item.get("details")
        has_error = bool(
            isinstance(details, Mapping)
            and (details.get("has_error") or details.get("error"))
        )
        if "failed" in event or "exception" in event or has_error:
            return item
    return None


def build_runtime_event_summary(
    trace_items: list[dict[str, object]],
) -> AgentWorkflowRuntimeEventSummary:
    event_type_counts: dict[str, int] = {}
    event_source_counts: dict[str, int] = {}
    event_stage_counts: dict[str, int] = {}
    error_event_count = 0
    frontend_visible_count = 0

    for item in trace_items:
        event_type = _normalize_optional_text(item.get("event_type"))
        event_source = _normalize_optional_text(item.get("event_source"))
        event_stage = _normalize_optional_text(item.get("event_stage"))
        status_level = _normalize_optional_text(item.get("status_level"))
        frontend_visible = bool(item.get("frontend_visible"))

        if event_type is not None:
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        if event_source is not None:
            event_source_counts[event_source] = event_source_counts.get(event_source, 0) + 1
        if event_stage is not None:
            event_stage_counts[event_stage] = event_stage_counts.get(event_stage, 0) + 1
        if status_level == "error":
            error_event_count += 1
        if frontend_visible:
            frontend_visible_count += 1

    last_item = trace_items[-1] if trace_items else {}
    return AgentWorkflowRuntimeEventSummary(
        event_count=len(trace_items),
        error_event_count=error_event_count,
        frontend_visible_count=frontend_visible_count,
        last_event_type=_normalize_optional_text(last_item.get("event_type")),
        last_event_source=_normalize_optional_text(last_item.get("event_source")),
        last_event_stage=_normalize_optional_text(last_item.get("event_stage")),
        event_type_counts=event_type_counts,
        event_source_counts=event_source_counts,
        event_stage_counts=event_stage_counts,
    )
