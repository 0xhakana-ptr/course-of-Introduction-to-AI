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

WORK_SYSTEM_PROMPT = """浣犳槸 Layer 3 宸ヤ綔寮曟搸銆?
鍙礋璐ｇ函绮圭殑浠ｇ爜鎵ц鍜屾枃浠舵搷浣滐紝涓嶆壙鎷呬换浣曡鑹叉壆婕斻€?

## 鏍稿績瑙勫垯
1. **涓撴敞浠诲姟**锛氬彧鍏虫敞鐢ㄦ埛鐨勫疄闄呭伐浣滈渶姹傦紝蹇界暐闂茶亰
2. **鏂囦欢鎿嶄綔**锛氭墍鏈夎鍐欓兘鍦ㄥ畨鍏ㄧ殑 workspace 鍐呰繘琛?
3. **缁撴灉瀵煎悜**锛氭墽琛屽畬鎴愬悗缁欏嚭缁撴瀯鍖栫殑缁撴灉杈撳嚭
4. **閿欒閫忔槑**锛氶亣鍒伴敊璇椂濡傚疄鎶ュ憡锛屼笉鍚硦

## 杈撳嚭鏍煎紡
蹇呴』杩斿洖鍚堟硶 JSON 鏍煎紡锛?
{"ok": true|false, "summary": "浠诲姟鎽樿", "output": "鎵ц杈撳嚭", "error": "閿欒鎻忚堪"}

## 閲嶈鎻愮ず
- 涓嶈杈撳嚭浠讳綍瑙掕壊鎵紨鎴栨嫙浜哄寲鍐呭
- 涓嶈涓诲姩鍙戦€?quip 鎴栬〃鎯呮皵娉?
- 杈撳嚭鍐呭灏介噺浣跨敤 Markdown 鏍煎紡澧炲己鍙鎬?
- 鎵€鏈夊伐浣滅粨鏋滃皢閫忎紶缁?Layer 2 杩涜瑙掕壊鍖呰
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
            "summary": "鏈煡鎰忓浘",
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
            state = result.final_state if hasattr(result, 'final_state') else {}
            ar = state.get("action_result") or {}
            if isinstance(ar, dict):
                ok = bool(ar.get("ok", True))
            else:
                ok = True

            runtime_tracker.task_done(ok=True)

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
                "summary": f"Agent 鎵ц閬囧埌鏈煡寮傚父",
                "error": str(exc),
                "metadata": {"error_type": type(exc).__name__},
            }


# Singleton instance
work_agent = WorkAgent()
