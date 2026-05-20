from backend.app.agent_workflow.contracts.workflow_nodes import WORKFLOW_NODE_METADATA
from backend.app.agent_workflow.output.node_events import WORKFLOW_NODE_EVENTS


def test_agent_loop_node_metadata_excludes_removed_route_graph_nodes():
    legacy_route_nodes = {
        "router",
        "chat_node",
        "coding_node",
        "workspace_tool_node",
        "run_tool_node",
        "run_snapshot_node",
        "run_control_node",
        "unknown_node",
    }

    assert legacy_route_nodes.isdisjoint(WORKFLOW_NODE_METADATA)
    assert legacy_route_nodes.isdisjoint(WORKFLOW_NODE_EVENTS)


def test_agent_loop_node_metadata_keeps_current_runtime_nodes():
    current_loop_nodes = {
        "plan_node",
        "plan_node",
        "act_node",
        "observe_node",
        "decide_continue_node",
        "finalize_node",
        "failure_node",
    }

    assert current_loop_nodes.issubset(WORKFLOW_NODE_METADATA)
    assert current_loop_nodes.issubset(WORKFLOW_NODE_EVENTS)
