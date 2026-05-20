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

from .routing_guard import RoutingDecision, INTENT_CHAT, INTENT_CODING

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

WORK_SYSTEM_PROMPT = """???????Layer 3??
???????????????????

## ????
1. **????**: ????????????????
2. **????**: ?????????workspace???
3. **????**: ?????????????????
4. **????**: ????????????

## ????
??????????JSON?
{"ok": true|false, "summary": "??????", "output": "????", "error": "????"}

## ????
- ????????????????
- ???????????quip???
- ????Markdown????????
- ????????????Layer 2???
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
            "summary": "????????",
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
            # Emit heartbeat status to keep frontend indicator alive
            from ...messaging.message_sender import message_sender
            message_sender.send_status(
                "running", progress=15,
                node_name="work_engine",
                metadata={"phase": "execution", "ui_status": "agent_working"},
                event_type="status.updated",
                event_source="workflow",
                event_stage="coding",
            )

            from ..graphs.loop_agent_loop_graph import run_agent_loop

            prompt = str(decision.action_input.get("prompt", ""))
            if not prompt:
                prompt = f"????: {decision.action_name}"

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

            # Heartbeat: agent loop completed, handing off to roleplay layer
            message_sender.send_status(
                "running", progress=40,
                node_name="work_engine",
                metadata={"phase": "execution_done", "ui_status": "agent_done"},
                event_type="status.updated",
                event_source="workflow",
                event_stage="coding",
            )

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
            logger.exception("WorkAgent execution failed: %s", exc)
            return {
                "ok": False,
                "intent": decision.intent,
                "action_name": decision.action_name,
                "summary": f"Agent ???????",
                "error": str(exc),
                "metadata": {"error_type": type(exc).__name__},
            }


# Singleton instance
work_agent = WorkAgent()
