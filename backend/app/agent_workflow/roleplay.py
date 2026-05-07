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
