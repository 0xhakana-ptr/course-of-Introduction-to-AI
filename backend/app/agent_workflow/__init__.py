from .node_mappings import get_node_quip_and_expression, should_send_chat_message

__all__ = ["agent_graph", "run_agent", "get_node_quip_and_expression", "should_send_chat_message"]


def __getattr__(name: str):
    if name in {"agent_graph", "run_agent"}:
        from .agent_graph import agent_graph, run_agent

        exports = {
            "agent_graph": agent_graph,
            "run_agent": run_agent,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
