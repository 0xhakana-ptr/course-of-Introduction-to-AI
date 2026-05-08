from collections.abc import Callable

from .chat_action.agent import build_agent_reply
from .chat_action.intent import detect_intent
from .chat_action.test_commands import handle_test_command, is_test_command
from .chat_action.types import ChatServiceResult
from .character_interface import send_chat_done, send_chat_failed, send_chat_started
from ..storage.conversation_store import conversation_store

RunScheduler = Callable[[str], None]
QUEUED_CODING_OUTPUT = "已通过 LangGraph 创建代码任务，并交给 `/runs` 链路处理。"
SCHEDULED_CODING_OUTPUT = "已通过 LangGraph 创建代码任务，并开始后台执行。"


def _schedule_coding_run_if_needed(
    result: ChatServiceResult,
    *,
    schedule_run: RunScheduler | None,
) -> ChatServiceResult:
    if not result.is_intent("coding") or not result.ok or not result.run_id or schedule_run is None:
        return result

    try:
        schedule_run(result.run_id)
    except Exception as exc:
        return result.with_updates(
            ok=False,
            output=f"代码任务已创建，但后台执行调度失败。\n\nrun_id: {result.run_id}",
            error=str(exc),
        )

    return result.with_updates(
        output=result.output.replace(
            QUEUED_CODING_OUTPUT,
            SCHEDULED_CODING_OUTPUT,
        )
    )


def _persist_result_to_conversation(
    session_id: str,
    *,
    prompt: str,
    result: ChatServiceResult,
) -> None:
    if result.is_intent("chat"):
        if result.ok:
            send_chat_done()
            conversation_store.append_exchange(
                session_id,
                user_prompt=prompt,
                assistant_output=result.output,
            )
        else:
            send_chat_failed()
            conversation_store.append_message(session_id, "user", prompt)
        return

    assistant_output = result.output
    if result.is_intent("coding") and not result.ok:
        assistant_output = None
    conversation_store.append_exchange(
        session_id,
        user_prompt=prompt,
        assistant_output=assistant_output,
    )


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

    intent_hint = detect_intent(prompt)
    if intent_hint == "chat":
        send_chat_started()

    effective_context = conversation_store.build_context(active_session_id, context)
    result = await build_agent_reply(
        prompt,
        effective_context,
        session_id=active_session_id,
        intent=intent_hint,
        emit_chat_message=False,
    )
    result = _schedule_coding_run_if_needed(
        result,
        schedule_run=schedule_run,
    )
    _persist_result_to_conversation(
        active_session_id,
        prompt=prompt,
        result=result,
    )
    return result.attach_session(active_session_id)
