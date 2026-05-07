from collections.abc import Callable

from .chat_action.coding import build_coding_reply
from .chat_action.intent import detect_intent
from .chat_action.replies import build_chat_reply, build_unknown_reply
from .chat_action.test_commands import handle_test_command, is_test_command
from .chat_action.types import ChatServiceResult
from .character_interface import send_chat_done, send_chat_failed, send_chat_started
from ..storage.conversation_store import conversation_store

RunScheduler = Callable[[str], None]


async def generate_chat_response(
    prompt: str,
    context: str | None,
    session_id: str | None = None,
    schedule_run: RunScheduler | None = None,
) -> ChatServiceResult:
    active_session_id = conversation_store.get_or_create_session_id(session_id)

    if is_test_command(prompt):
        return ChatServiceResult(
            intent="chat",
            ok=True,
            output=handle_test_command(prompt),
            session_id=active_session_id,
        )

    intent = detect_intent(prompt)
    if intent == "chat":
        send_chat_started()
        effective_context = conversation_store.build_context(active_session_id, context)
        result = await build_chat_reply(prompt, effective_context)
        if result.ok:
            send_chat_done()
            conversation_store.append_exchange(
                active_session_id,
                user_prompt=prompt,
                assistant_output=result.output,
            )
        else:
            send_chat_failed()
            conversation_store.append_message(active_session_id, "user", prompt)
        return ChatServiceResult(
            intent=intent,
            ok=result.ok,
            output=result.output,
            error=result.error,
            session_id=active_session_id,
        )
    if intent == "coding":
        effective_context = conversation_store.build_context(active_session_id, context)
        result = build_coding_reply(
            prompt,
            effective_context,
            session_id=active_session_id,
            schedule_run=schedule_run,
        )
        conversation_store.append_exchange(
            active_session_id,
            user_prompt=prompt,
            assistant_output=result.output if result.ok else None,
        )
        result.session_id = active_session_id
        return result

    result = build_unknown_reply(prompt)
    conversation_store.append_exchange(
        active_session_id,
        user_prompt=prompt,
        assistant_output=result.output,
    )
    result.session_id = active_session_id
    return result
