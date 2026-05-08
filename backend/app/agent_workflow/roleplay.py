from collections.abc import Mapping

from ..messaging.message_sender import message_sender


def emit_roleplay_chat(
    content: str,
    *,
    node_name: str = "agent_roleplay",
    emit_chat_message: bool = True,
) -> None:
    output = content.strip()
    if not output or not emit_chat_message:
        return

    message_sender.send_chat_message(
        content=output,
        is_partial=False,
        node_name=node_name,
    )


def emit_roleplay_message(
    message: object,
    *,
    default_node_name: str = "agent_roleplay",
    emit_chat_message: bool = True,
) -> None:
    node_name = default_node_name
    content: object = message

    if hasattr(message, "content") and hasattr(message, "node_name"):
        content = getattr(message, "content", "")
        resolved_node_name = getattr(message, "node_name", None)
        if resolved_node_name:
            node_name = str(resolved_node_name)

    emit_roleplay_chat(
        str(content or ""),
        node_name=node_name,
        emit_chat_message=emit_chat_message,
    )


def emit_roleplay_state(
    state: Mapping[str, object],
    *,
    default_node_name: str,
) -> dict[str, object]:
    emit_roleplay_message(
        state.get("output") or "",
        default_node_name=str(state.get("node_name") or default_node_name),
        emit_chat_message=bool(state.get("emit_chat_message", True)),
    )
    return dict(state)
