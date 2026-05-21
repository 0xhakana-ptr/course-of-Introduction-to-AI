from collections.abc import Callable
from dataclasses import dataclass, replace

from ..schemas import INTENT_TYPE
from ..agent_workflow.contracts.workflow_results import WorkflowAgentResult
from ..agent_workflow.output.text import sanitize_user_visible_run_output


VALID_CHAT_SERVICE_INTENTS: set[str] = {"chat", "coding", "unknown"}


def _normalize_optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(slots=True)
class ChatServiceResult:
    intent: INTENT_TYPE
    ok: bool
    output: str
    error: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    run_action: str | None = None
    runtime_mode: str | None = None
    route_scope: str | None = None
    runtime_warning: str | None = None
    content_type: str = "markdown"
    render_mode: str = "rich_text"

    def with_updates(self, **updates: object) -> "ChatServiceResult":
        return replace(self, **updates)

    def is_intent(self, intent: INTENT_TYPE) -> bool:
        return self.intent == intent

    def attach_session(self, session_id: str | None) -> "ChatServiceResult":
        if session_id is None:
            return self
        return self.with_updates(session_id=session_id)

    def with_user_visible_output(self) -> "ChatServiceResult":
        if not self.is_intent("coding"):
            return self
        return self.with_updates(output=sanitize_user_visible_run_output(self.output))

    @classmethod
    def from_agent_result(
        cls,
        result: object,
        *,
        intent_hint: INTENT_TYPE | None = None,
        fallback_output_builder: Callable[[INTENT_TYPE], str] | None = None,
    ) -> "ChatServiceResult":
        normalized_result = WorkflowAgentResult.from_value(
            result,
            default_intent=intent_hint or "unknown",
        )
        resolved_intent = normalized_result.resolved_intent(
            valid_intents=VALID_CHAT_SERVICE_INTENTS,
            default_intent="unknown",
        )
        output = normalized_result.resolved_output(
            intent=resolved_intent,
            fallback_output_builder=fallback_output_builder,
        )
        run_id, _ = normalized_result.run_payload()

        return cls(
            intent=resolved_intent,
            ok=normalized_result.ok,
            output=sanitize_user_visible_run_output(output) if resolved_intent == "coding" else output,
            error=_normalize_optional_str(normalized_result.error),
            run_id=_normalize_optional_str(run_id),
            run_action=_normalize_optional_str(normalized_result.run_action_name()),
        )

import anyio
from collections.abc import Callable

# ChatServiceResult defined above in this file
from .character import send_chat_done, send_chat_failed, send_chat_started
from ..storage.conversation_store import conversation_store
from ..agent_workflow.router import routing_guard
from ..agent_workflow.roleplay import roleplay_agent
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
        assistant_output = result.error or "抱歉，出了一点问题，请再试一次。"

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
    process_result = await anyio.to_thread.run_sync(
        partial(
            roleplay_agent.process,
            decision,
            session_id=active_session_id,
            memory_context=memory_context,
            # /chat returns the full assistant output via HTTP; avoid also
            # enqueueing the same content as an agent:chat runtime event.
            emit_chat_message=False,
        )
    )

    # Record turn in Hermes memory
    hermes_memory.record_turn(
        session_id=active_session_id,
        user_input=prompt,
        intent=decision.intent,
        action_name=decision.action_name,
        result_summary=process_result.response.chat_line[:200],
        ok=True,
    )

    # Build result — extract run metadata from ProcessResult (work-engine layer)
    run_id = process_result.work_metadata.get("run_id") if isinstance(process_result.work_metadata, dict) else None
    run_action = process_result.work_metadata.get("run_action") if isinstance(process_result.work_metadata, dict) else None

    chat_ok = True
    chat_error: str | None = None
    if isinstance(process_result.work_metadata, dict):
        if "chat_ok" in process_result.work_metadata:
            chat_ok = bool(process_result.work_metadata.get("chat_ok"))
        raw_error = process_result.work_metadata.get("chat_error")
        chat_error = _normalize_optional_str(raw_error)
    
    result = ChatServiceResult(
        run_id=str(run_id) if run_id else None,
        run_action=str(run_action) if run_action else None,
        intent=decision.intent,
        ok=chat_ok,
        output=process_result.response.chat_line,
        error=chat_error,
        session_id=active_session_id,
    )

    result = _schedule_coding_run_if_needed(result, schedule_run=schedule_run)
    result = result.with_user_visible_output()
    _persist_result_to_conversation(active_session_id, prompt=prompt, result=result)
    return result.attach_session(active_session_id)
