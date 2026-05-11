from functools import partial
import logging

from anyio import to_thread

from ...messaging.message_sender import message_sender
from ...schemas import INTENT_TYPE
from .types import ChatServiceResult


logger = logging.getLogger(__name__)
PRIMARY_RUNTIME_MODE = "loop"
PRIMARY_ROUTE_SCOPE = "primary_loop"


def _attach_runtime_metadata(
    result: ChatServiceResult,
) -> ChatServiceResult:
    return result.with_updates(
        runtime_mode=PRIMARY_RUNTIME_MODE,
        route_scope=PRIMARY_ROUTE_SCOPE,
        runtime_warning=None,
    )


def _fallback_output(resolved_intent: INTENT_TYPE) -> str:
    if resolved_intent == "coding":
        return "代码任务已进入 Agent 工作流，但暂时没有返回可展示的说明。"
    if resolved_intent == "chat":
        return "聊天工作流已执行，但暂时没有返回可展示的文本。"
    return "Agent 工作流已执行，但暂时没有返回可展示的文本。"


def _emit_agent_loop_failed_event(
    *,
    emit_node_events: bool,
    node_name: str,
    phase: str,
    ui_status: str,
    error: str,
) -> bool:
    if not emit_node_events:
        return False

    try:
        return message_sender.send_status(
            "error",
            node_name=node_name,
            metadata={
                "node_label": "Agent Loop",
                "phase": phase,
                "runtime_event": "workflow_failed",
                "ui_status": ui_status,
                "error": error,
            },
            event_type="workflow.failed",
            event_source="workflow",
            event_stage="fallback",
        )
    except Exception:
        logger.exception("Failed to emit Agent Loop outer failure event: node=%s", node_name)
        return False


async def build_agent_reply(
    prompt: str,
    context: str | None,
    *,
    session_id: str | None = None,
    intent: INTENT_TYPE | None = None,
    emit_chat_message: bool = False,
    emit_node_events: bool = True,
) -> ChatServiceResult:
    try:
        from ...agent_workflow.loop.agent_loop_graph import run_agent_loop
    except ImportError as exc:
        resolved_intent = intent or "unknown"
        _emit_agent_loop_failed_event(
            emit_node_events=emit_node_events,
            node_name="agent_loop_import",
            phase="system",
            ui_status="workflow_unavailable",
            error=str(exc),
        )
        return _attach_runtime_metadata(
            ChatServiceResult(
                intent=resolved_intent,
                ok=False,
                output="Agent 工作流当前不可用，原因是相关依赖尚未正确加载。",
                error=str(exc),
            ),
        )

    try:
        result = await to_thread.run_sync(
            partial(
                run_agent_loop,
                prompt,
                context,
                session_id=session_id,
                intent=intent,
                emit_chat_message=emit_chat_message,
                emit_node_events=emit_node_events,
            )
        )
    except Exception as exc:
        resolved_intent = intent or "unknown"
        _emit_agent_loop_failed_event(
            emit_node_events=emit_node_events,
            node_name="agent_loop_outer_guard",
            phase="fallback",
            ui_status="workflow_exception",
            error=str(exc),
        )
        return _attach_runtime_metadata(
            ChatServiceResult(
                intent=resolved_intent,
                ok=False,
                output="Agent 工作流执行失败。",
                error=str(exc),
            ),
        )

    return _attach_runtime_metadata(
        ChatServiceResult.from_agent_result(
            result,
            intent_hint=intent,
            fallback_output_builder=_fallback_output,
        ),
    )
