from functools import partial

from anyio import to_thread

from ...schemas import INTENT_TYPE
from .types import ChatServiceResult


def _fallback_output(resolved_intent: INTENT_TYPE) -> str:
    if resolved_intent == "coding":
        return "代码任务已进入 Agent 工作流，但暂时没有返回可展示的说明。"
    if resolved_intent == "chat":
        return "聊天工作流已执行，但暂时没有返回可展示的文本。"
    return "Agent 工作流已执行，但暂时没有返回可展示的文本。"


async def build_agent_reply(
    prompt: str,
    context: str | None,
    *,
    session_id: str | None = None,
    intent: INTENT_TYPE | None = None,
    emit_chat_message: bool = False,
) -> ChatServiceResult:
    try:
        from ...agent_workflow.agent_graph import run_agent
    except ImportError as exc:
        resolved_intent = intent or "unknown"
        return ChatServiceResult(
            intent=resolved_intent,
            ok=False,
            output="Agent 工作流当前不可用，原因是相关依赖尚未正确加载。",
            error=str(exc),
        )

    try:
        result = await to_thread.run_sync(
            partial(
                run_agent,
                prompt,
                context,
                session_id=session_id,
                intent=intent,
                emit_chat_message=emit_chat_message,
            )
        )
    except Exception as exc:
        resolved_intent = intent or "unknown"
        return ChatServiceResult(
            intent=resolved_intent,
            ok=False,
            output="Agent 工作流执行失败。",
            error=str(exc),
        )

    resolved_intent = result.intent or intent or "unknown"
    if resolved_intent not in {"chat", "coding", "unknown"}:
        resolved_intent = "unknown"

    output = result.output.strip() or _fallback_output(resolved_intent)
    error = str(result.error) if result.error is not None else None

    return ChatServiceResult(
        intent=resolved_intent,
        ok=result.ok,
        output=output,
        error=error,
        run_id=str(result.run_id) if result.run_id is not None else None,
    )
