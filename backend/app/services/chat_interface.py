import anyio
from collections.abc import Callable

from .chat_action.types import ChatServiceResult
from .character_interface import send_chat_done, send_chat_failed, send_chat_started
from ..storage.conversation_store import conversation_store
from ..agent_workflow.layers import routing_guard, roleplay_agent
from ..agent_workflow.memory import hermes_memory

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
    # Always save user message first
    conversation_store.append_message(session_id, "user", prompt)

    assistant_output = result.output
    if not result.ok and not assistant_output:
        # Generate fallback even on error so history shows something
        assistant_output = result.error or "???????????????"

    if assistant_output:
        conversation_store.append_message(session_id, "assistant", assistant_output)

    if result.is_intent("chat"):
        if result.ok:
            send_chat_done()
        else:
            send_chat_failed()


async def generate_chat_response(
    prompt: str,
    context: str | None,
    session_id: str | None = None,
    schedule_run: RunScheduler | None = None,
) -> ChatServiceResult:
    """Process chat request through the 3-layer architecture.

    Layer 1 (Routing Guard): Detect intent, decide routing.
    Layer 2 (Roleplay Agent): Persona wrapper, user-facing interaction.
    Layer 3 (Work Agent): Actual work execution (called by Layer 2).
    """
    active_session_id = conversation_store.get_or_create_session_id(session_id)

    # === Layer 1: Routing Guard ===
    intent_hint = routing_guard.route(prompt, context).intent

    if intent_hint == "chat":
        send_chat_started()

    # Build combined context: conversation history + Hermes memory
    effective_context = conversation_store.build_context(active_session_id, context)
    memory_context = hermes_memory.build_context(active_session_id)
    if memory_context:
        if effective_context:
            effective_context = f"{memory_context}\n\n---\n\n{effective_context}"
        else:
            effective_context = memory_context

    # === Layer 1: Routing Decision ===
    file_context = None
    from ..storage.file_context_store import file_context_store
    stored_fc = file_context_store.get_context(active_session_id)
    if stored_fc:
        file_context = stored_fc

    decision = routing_guard.route(prompt, effective_context, file_context)

    # === Layer 2 + 3: Roleplay Agent calls Work Agent internally ===
    # Run Layer 2+3 in thread pool to avoid blocking event loop
    from functools import partial
    roleplay_response = await anyio.to_thread.run_sync(
        partial(
            roleplay_agent.process,
            decision,
            session_id=active_session_id,
            memory_context=memory_context,
        )
    )

    # Record turn in Hermes memory
    hermes_memory.record_turn(
        session_id=active_session_id,
        user_input=prompt,
        intent=decision.intent,
        action_name=decision.action_name,
        result_summary=roleplay_response.chat_line[:200],
        ok=True,
    )

    # Build result
    result = ChatServiceResult(
        intent=decision.intent,
        ok=True,
        output=roleplay_response.chat_line,
        session_id=active_session_id,
    )

    result = _schedule_coding_run_if_needed(result, schedule_run=schedule_run)
    result = result.with_user_visible_output()
    _persist_result_to_conversation(active_session_id, prompt=prompt, result=result)
    return result.attach_session(active_session_id)
