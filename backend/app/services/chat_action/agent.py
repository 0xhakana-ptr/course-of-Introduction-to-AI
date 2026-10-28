"""Chat reply seam between chat orchestration and the 3-layer pipeline.

``build_agent_reply`` is the stable seam: ``chat_interface.generate_chat_response``
resolves the session and builds conversation context, then delegates the actual
reply generation to this function. Tests monkeypatch this seam to isolate the
orchestration layer from the agent pipeline.
"""

from functools import partial

import anyio

from ...agent_workflow.memory import hermes_memory
from ...agent_workflow.roleplay import roleplay_agent
from ...agent_workflow.router import routing_guard
from ...storage.file_context_store import file_context_store
from .types import ChatServiceResult, _normalize_optional_str


async def build_agent_reply(
    prompt: str,
    context: str | None,
    *,
    session_id: str | None = None,
    intent: str | None = None,
    emit_chat_message: bool = False,
) -> ChatServiceResult:
    """Run one turn through routing guard -> roleplay agent -> work engine.

    Args:
        prompt: User prompt for this turn.
        context: Built conversation context (history + external context).
        session_id: Active session ID.
        intent: Cheap keyword-level intent hint (``chat`` hints are passed as
            ``None`` so the routing guard makes the final call).
        emit_chat_message: Whether the roleplay layer may also enqueue the
            reply as an ``agent:chat`` runtime event.
    """
    memory_context = hermes_memory.build_context(session_id) if session_id else None

    routing_context = context
    if memory_context:
        routing_context = (
            f"{memory_context}\n\n---\n\n{context}" if context else memory_context
        )

    file_context = None
    if session_id:
        stored_file_context = file_context_store.get_context(session_id)
        if stored_file_context:
            file_context = stored_file_context

    decision = routing_guard.route(prompt, routing_context, file_context)

    # Layers 2 + 3 run in a worker thread so the event loop stays responsive.
    process_result = await anyio.to_thread.run_sync(
        partial(
            roleplay_agent.process,
            decision,
            session_id=session_id,
            memory_context=memory_context,
            emit_chat_message=emit_chat_message,
        )
    )

    work_metadata = (
        process_result.work_metadata if isinstance(process_result.work_metadata, dict) else {}
    )
    hermes_memory.record_turn(
        session_id=session_id,
        user_input=prompt,
        intent=decision.intent,
        action_name=decision.action_name,
        result_summary=process_result.response.chat_line[:200],
        ok=bool(work_metadata.get("chat_ok", True)),
    )

    chat_ok = True
    chat_error: str | None = None
    if "chat_ok" in work_metadata:
        chat_ok = bool(work_metadata.get("chat_ok"))
    chat_error = _normalize_optional_str(work_metadata.get("chat_error"))

    return ChatServiceResult(
        run_id=_normalize_optional_str(work_metadata.get("run_id")),
        run_action=_normalize_optional_str(work_metadata.get("run_action")),
        intent=decision.intent,
        ok=chat_ok,
        output=process_result.response.chat_line,
        error=chat_error,
        session_id=session_id,
        runtime_mode="loop",
        route_scope="primary_loop",
    )
