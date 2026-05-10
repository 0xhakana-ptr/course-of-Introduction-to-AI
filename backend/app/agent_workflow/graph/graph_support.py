from collections.abc import Callable, Mapping


AGENT_ROUTER_EDGE_MAP: dict[str, str] = {
    "chat_node": "chat_node",
    "coding_node": "coding_node",
    "unknown_node": "unknown_node",
    "roleplay_node": "roleplay_node",
}

AGENT_CODING_EDGE_MAP: dict[str, str] = {
    "workspace_tool_node": "workspace_tool_node",
    "run_snapshot_node": "run_snapshot_node",
    "run_control_node": "run_control_node",
    "roleplay_node": "roleplay_node",
}

AGENT_LINEAR_EDGES: tuple[tuple[str, str], ...] = (
    ("chat_node", "roleplay_node"),
    ("workspace_tool_node", "run_tool_node"),
    ("run_tool_node", "roleplay_node"),
    ("run_snapshot_node", "roleplay_node"),
    ("run_control_node", "roleplay_node"),
    ("unknown_node", "roleplay_node"),
)


def guard_node(
    node_name: str,
    handler: Callable[[object], object],
    *,
    failure_builder: Callable[..., object],
) -> Callable[[object], object]:
    def wrapped(state: object) -> object:
        try:
            return handler(state)
        except Exception as exc:
            return failure_builder(
                state,
                node_name=node_name,
                exc=exc,
            )

    return wrapped


def register_agent_graph_nodes(
    workflow: object,
    *,
    node_handlers: Mapping[str, Callable[[object], object]],
    failure_builder: Callable[..., object],
) -> None:
    for node_name, handler in node_handlers.items():
        workflow.add_node(
            node_name,
            guard_node(
                node_name,
                handler,
                failure_builder=failure_builder,
            ),
        )


def configure_agent_graph_edges(
    workflow: object,
    *,
    route_by_intent: Callable[[object], str],
    select_coding_next_node: Callable[[object], str],
    end_node: object,
) -> None:
    workflow.set_entry_point("router")
    workflow.add_conditional_edges(
        "router",
        route_by_intent,
        dict(AGENT_ROUTER_EDGE_MAP),
    )
    workflow.add_conditional_edges(
        "coding_node",
        select_coding_next_node,
        dict(AGENT_CODING_EDGE_MAP),
    )
    for start_node, end_target in AGENT_LINEAR_EDGES:
        workflow.add_edge(start_node, end_target)
    workflow.add_edge("roleplay_node", end_node)
