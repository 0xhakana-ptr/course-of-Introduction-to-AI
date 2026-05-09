from collections.abc import Mapping

from .agent_constants import AGENT_ROUTE_BY_INTENT, RUN_ACTION_INSPECT, RUN_CONTROL_ACTIONS, WORKFLOW_NODE_FAILED_STATUS


def select_agent_next_node(intent: str | None) -> str:
    return AGENT_ROUTE_BY_INTENT.get(str(intent or "").strip(), "unknown_node")


def select_coding_next_node(state: Mapping[str, object]) -> str:
    if str(state.get("ui_status") or "").strip() == WORKFLOW_NODE_FAILED_STATUS:
        return "roleplay_node"
    run_action = str(state.get("run_action") or "").strip()
    if run_action == RUN_ACTION_INSPECT:
        return "run_snapshot_node"
    if run_action in RUN_CONTROL_ACTIONS:
        return "run_control_node"
    return "workspace_tool_node"
