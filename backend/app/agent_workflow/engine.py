# -*- coding: utf-8 -*-
"""Layer 3: Work Agent.

The actual work execution layer. Called by Layer 2 (RoleplayAgent).
Runs the LangGraph agent loop and returns structured results.
Pure work execution - no persona, no roleplay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any

from .router import RoutingDecision, INTENT_CHAT, INTENT_CODING
from .runtime_tracker import runtime_tracker

logger = logging.getLogger(__name__)


@dataclass
class WorkAgentResult:
    """Structured output from Layer 3, returned to Layer 2."""
    ok: bool
    intent: str = "unknown"
    summary: str = ""
    action_name: str = ""
    output: str = ""
    error: str | None = None
    file_context: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    action_result: dict[str, Any] | None = None
    raw_state: dict[str, Any] | None = None



# ---------------------------------------------------------------------------
# Layer 3 System Prompt: Work Engine
# Pure work execution - no persona, no roleplay, no frontend emission.
# ---------------------------------------------------------------------------

WORK_SYSTEM_PROMPT = """你是 Layer 3 工作引擎。
只负责纯粹的代码执行和文件操作，不承担任何角色扮演。

## 核心规则
1. **专注任务**：只关注用户的实际工作需求，忽略闲聊
2. **文件操作**：所有读写都在安全的 workspace 内进行
3. **结果导向**：执行完成后给出结构化的结果输出
4. **错误透明**：遇到错误时如实报告，不含糊

## 输出格式
必须返回合法 JSON 格式：
{"ok": true|false, "summary": "任务摘要", "output": "执行输出", "error": "错误描述"}

## 重要提示
- 不要输出任何角色扮演或拟人化内容
- 不要主动发送 quip 或表情语气词
- 输出内容尽量使用 Markdown 格式增强可读性
- 所有工作结果将透传给 Layer 2 进行角色包装
"""


class WorkAgent:
    """Layer 3: Work execution via LangGraph agent loop.

    Pure work execution. No persona, no roleplay, no frontend emission.
    Called exclusively by Layer 2 (RoleplayAgent).
    """

    def execute(self, decision: RoutingDecision, *,
                session_id: str | None = None,
                turn_id: str | None = None,
                memory_context: str | None = None) -> dict[str, Any]:
        """Execute work based on routing decision.

        Args:
            decision: Routing decision from Layer 1 (via Layer 2).
            session_id: Active session ID.
            turn_id: Current turn ID.
            memory_context: Hermes memory context.

        Returns:
            Dictionary with structured work results for Layer 2.
        """
        if decision.intent == INTENT_CHAT:
            return self._chat_result(decision)

        if decision.intent == INTENT_CODING:
            return self._execute_loop(decision, session_id=session_id,
                                      turn_id=turn_id, memory_context=memory_context)

        return {
            "ok": False,
            "intent": decision.intent,
            "summary": "未知意图",
            "error": "Unknown intent",
        }

    def _chat_result(self, decision: RoutingDecision) -> dict[str, Any]:
        """Chat intent doesn't need agent loop - handled by Layer 2 directly."""
        return {
            "ok": True,
            "intent": INTENT_CHAT,
            "action_name": "chat.reply",
            "summary": "",
        }

    def _execute_loop(self, decision: RoutingDecision, *,
                      session_id: str | None,
                      turn_id: str | None,
                      memory_context: str | None) -> dict[str, Any]:
        """Run the LangGraph agent loop for coding/work requests."""
        try:
            runtime_tracker.phase_enter("L3_engine")

            from .graphs.loop_agent_loop_graph import run_agent_loop

            prompt = str(decision.action_input.get("prompt", ""))
            if not prompt:
                prompt = f"浠诲姟: {decision.action_name}"

            # Incorporate memory context into the prompt context
            context = decision.action_input.get("context")
            if memory_context:
                if context:
                    context = f"{memory_context}\n\n---\n\n{context}"
                else:
                    context = memory_context

            result = run_agent_loop(
                prompt=prompt,
                context=str(context or ""),
                session_id=session_id,
                intent=decision.intent,
                emit_chat_message=False,
                emit_node_events=True,
                action_name=decision.action_name,
                action_input=dict(decision.action_input),
            )

            # Extract structured data from the workflow result
            state = result.state if hasattr(result, 'state') else {}
            ar = state.get("action_result") or {}
            if isinstance(ar, dict):
                ok = bool(ar.get("ok", True))
            else:
                ok = True

            runtime_tracker.task_done(ok=ok)

            return {
                "ok": ok,
                "intent": str(state.get("intent", decision.intent)),
                "summary": str(ar.get("summary") or state.get("output") or "").strip(),
                "action_name": str(state.get("action_name", decision.action_name)),
                "output": str(state.get("output") or "").strip(),
                "error": str(state.get("error")) if state.get("error") else None,
                "file_context": state.get("file_context"),
                "action_result": ar if isinstance(ar, dict) else {},
                "metadata": {
                    "stop_reason": state.get("stop_reason"),
                    "step_count": state.get("step_count"),
                    "run_id": state.get("run_id"),
                    "run_status": state.get("run_status"),
                    "run_action": state.get("run_action"),
                },
                "raw_state": state,
            }

        except Exception as exc:
            runtime_tracker.task_done(ok=False)
            logger.exception("WorkAgent execution failed: %s", exc)
            return {
                "ok": False,
                "intent": decision.intent,
                "action_name": decision.action_name,
                "summary": "Agent 执行遇到未知异常",
                "error": str(exc),
                "metadata": {"error_type": type(exc).__name__},
            }


# Singleton instance
work_agent = WorkAgent()
