from collections.abc import Callable, Mapping


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
