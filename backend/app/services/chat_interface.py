from collections.abc import Callable

from .chat_action.agent import build_agent_reply
from .chat_action.intent import detect_intent
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

    if result.intent == "chat":
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
            intent=result.intent,
            ok=result.ok,
            output=result.output,
            error=result.error,
            session_id=active_session_id,
            run_id=result.run_id,
        )

    if result.intent == "coding":
        if result.run_id and result.ok and schedule_run is not None:
            try:
                schedule_run(result.run_id)
            except Exception as exc:
                result = ChatServiceResult(
                    intent="coding",
                    ok=False,
                    output=f"代码任务已创建，但后台执行调度失败。\n\nrun_id: {result.run_id}",
                    error=str(exc),
                    run_id=result.run_id,
                )
            else:
                result.output = result.output.replace(
                    "已通过 LangGraph 创建代码任务，并交给 `/runs` 链路处理。",
                    "已通过 LangGraph 创建代码任务，并开始后台执行。",
                )
        conversation_store.append_exchange(
            active_session_id,
            user_prompt=prompt,
            assistant_output=result.output if result.ok else None,
        )
        result.session_id = active_session_id
        return result

    conversation_store.append_exchange(
        active_session_id,
        user_prompt=prompt,
        assistant_output=result.output,
    )
    result.session_id = active_session_id
    return result
