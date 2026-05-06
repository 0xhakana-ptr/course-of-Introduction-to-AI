from .chat_action.coding import build_coding_reply
from .chat_action.intent import detect_intent
from .chat_action.replies import build_chat_reply, build_unknown_reply
from .chat_action.test_commands import handle_test_command, is_test_command
from .chat_action.types import ChatServiceResult


async def generate_chat_response(prompt: str, context: str | None) -> ChatServiceResult:
    if is_test_command(prompt):
        return ChatServiceResult(
            intent="chat",
            ok=True,
            output=handle_test_command(prompt),
        )

    intent = detect_intent(prompt)
    if intent == "chat":
        result = await build_chat_reply(prompt, context)
        return ChatServiceResult(
            intent=intent,
            ok=result.ok,
            output=result.output,
            error=result.error,
        )
    if intent == "coding":
        return build_coding_reply(prompt, context)
    return build_unknown_reply(prompt)
