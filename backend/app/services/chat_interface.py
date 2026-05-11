from collections.abc import Callable

from .chat_action.agent import build_agent_reply
from .chat_action.intent import detect_intent
from .chat_action.test_commands import handle_test_command, is_test_command
from .chat_action.types import ChatServiceResult
from .character_interface import send_chat_done, send_chat_failed, send_chat_started
from ..storage.conversation_store import conversation_store

RunScheduler = Callable[[str], None]
SCHEDULABLE_RUN_ACTIONS = {"create", "retry", "rerun"}
SCHEDULED_OUTPUT_REPLACEMENTS = {
    "create": (
        "我已经创建了代码任务，并交给后端执行。",
        "我已经创建了代码任务，并开始后台执行。",
    ),
    "retry": (
        "我已为这个代码任务创建重试任务。",
        "我已为这个代码任务创建重试任务，并开始后台执行。",
    ),
    "rerun": (
        "我已为这个代码任务创建重新运行任务。",
        "我已为这个代码任务创建重新运行任务，并开始后台执行。",
    ),
}


def _agent_intent_hint(detected_intent: str) -> str | None:
    # Natural chat should enter the Agent graph without being forced by the
    # frontend-facing deterministic intent gate. Keep operational
    # paths pinned so run control and file/tool tasks stay stable.
    return detected_intent if detected_intent in {"coding", "unknown"} else None


def _apply_scheduled_output(result: ChatServiceResult) -> ChatServiceResult:
    replacement = SCHEDULED_OUTPUT_REPLACEMENTS.get(str(result.run_action or "").strip())
    if replacement is None:
        return result

    queued_output, scheduled_output = replacement
    if queued_output not in result.output:
        return result

    return result.with_updates(
        output=result.output.replace(queued_output, scheduled_output),
    )


def _schedule_coding_run_if_needed(
    result: ChatServiceResult,
    *,
    schedule_run: RunScheduler | None,
) -> ChatServiceResult:
    if (
        not result.is_intent("coding")
        or not result.ok
        or result.run_action not in SCHEDULABLE_RUN_ACTIONS
        or not result.run_id
        or schedule_run is None
    ):
        return result

    try:
        schedule_run(result.run_id)
    except Exception as exc:
        return result.with_updates(
            ok=False,
            output=(
                "代码任务已创建，但后台执行调度失败。\n\n"
                "任务记录仍然保留在任务详情里，可以稍后查看或重新启动。"
            ),
            error=str(exc),
        )

    return _apply_scheduled_output(result)


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
        intent=_agent_intent_hint(intent_hint),
        emit_chat_message=False,
    )
    result = _schedule_coding_run_if_needed(
        result,
        schedule_run=schedule_run,
    )
    result = result.with_user_visible_output()
    _persist_result_to_conversation(
        active_session_id,
        prompt=prompt,
        result=result,
    )
    return result.attach_session(active_session_id)
