# -*- coding: utf-8 -*-
"""Layer 2: Roleplay Agent.

The persona layer that users interact with directly.
Receives routing from Layer 1, calls Layer 3 for work,
wraps results in character persona, emits to frontend.
"""

from __future__ import annotations

import dataclasses
import logging
import random
from dataclasses import dataclass, field
from typing import Any

from .routing_guard import RoutingDecision, INTENT_CHAT, INTENT_CODING, INTENT_UNKNOWN
from ...messaging.message_sender import message_sender
from ...llm.client import call_llm_sync, llm_is_configured

logger = logging.getLogger(__name__)

# Import the existing roleplay prompts (keep unchanged)
from ..output.roleplay_agent import (
    ROLEPLAY_SYSTEM_PROMPT,
    CHAT_SYSTEM_PROMPT,
    MOOD_HAPPY_MODIFIER,
    MOOD_NEUTRAL_MODIFIER,
    MOOD_FRUSTRATED_MODIFIER,
    MOOD_TIRED_MODIFIER,
    MOOD_LONELY_MODIFIER,
    RoleplayMood,
    get_session_mood,
    _parse_llm_json,
    _scenario_fallback,
    _THINKING_QUIPS,
    _CODING_QUIPS,
    _FAILURE_QUIPS,
    _SUCCESS_QUIPS,
    _IDLE_QUIPS,
    _CHAT_QUIPS,
)


@dataclass
class RoleplayResponse:
    """Output of Layer 2: persona-wrapped response ready for frontend."""
    chat_line: str
    expression: str = "neutral"
    quip: str = ""
    motion: str = ""
    mood_label: str = "neutral"
    scenario: str = "chat"
    llm_used: bool = False


@dataclass(frozen=True, slots=True)
class RoleplayAgentContext:
    """Context for roleplay generation, built from routing + work result."""
    intent: str = "chat"
    action_name: str = ""
    action_ok: bool = True
    output_summary: str = ""
    error_summary: str = ""
    step_count: int = 0
    terminal_status: str = ""

    @classmethod
    def from_routing_and_result(cls, decision: RoutingDecision,
                                work_result: dict[str, Any] | None = None) -> "RoleplayAgentContext":
        if work_result is None:
            return cls(intent=decision.intent, action_name=decision.action_name)

        return cls(
            intent=str(work_result.get("intent", decision.intent)),
            action_name=str(work_result.get("action_name", decision.action_name)),
            action_ok=bool(work_result.get("ok", True)),
            output_summary=str(work_result.get("summary", ""))[:400],
            error_summary=(str(work_result.get("error", ""))[:200]
                          if not work_result.get("ok") else ""),
            step_count=int(work_result.get("metadata", {}).get("step_count", 0)),
            terminal_status=str(work_result.get("metadata", {}).get("stop_reason", "")),
        )

    def scenario(self) -> str:
        if self.intent == "chat" or self.action_name == "chat.reply":
            return "chat"
        if self.terminal_status in ("completed",) and self.action_ok:
            return "success"
        if self.terminal_status in ("failed", "loop_max_steps"):
            return "failure"
        if not self.action_ok:
            return "failure"
        if self.action_name and any(kw in self.action_name for kw in ("workspace", "run", "code", "write", "read")):
            return "coding"
        return "thinking"


class RoleplayAgent:
    """Layer 2: Persona-wrapped interaction layer.

    This is the user-facing personality layer. It:
    1. Receives routing from Layer 1
    2. Calls Layer 3 (WorkAgent) for actual work execution
    3. Wraps results in character persona
    4. Emits to frontend (chat, expression, quip, motion)
    """

    def __init__(self):
        self._work_agent = None  # Lazy init for Layer 3

    @property
    def work_agent(self):
        if self._work_agent is None:
            from .work_engine import work_agent
            self._work_agent = work_agent
        return self._work_agent

    def process(self, decision: RoutingDecision, *,
                session_id: str | None = None,
                turn_id: str | None = None,
                memory_context: str | None = None) -> RoleplayResponse:
        """Process a routed request through Layer 2 + Layer 3.

        Args:
            decision: Routing decision from Layer 1.
            session_id: Active session ID.
            turn_id: Current turn ID.
            memory_context: Hermes memory context string.

        Returns:
            RoleplayResponse ready for frontend emission.
        """
        # Update idle streak - user is interacting
        mood = get_session_mood()
        mood.idle_streak = 0

        if decision.intent == INTENT_CHAT:
            return self._handle_chat(decision)

        # For coding/work intents, first emit a thinking quip
        self._emit_thinking_start(decision)

        # Call Layer 3 for actual work
        work_result = self.work_agent.execute(
            decision,
            session_id=session_id,
            turn_id=turn_id,
            memory_context=memory_context,
        )

        # Wrap work result in persona
        response = self._generate_persona_response(decision, work_result)

        # Track mood
        ctx = RoleplayAgentContext.from_routing_and_result(decision, work_result)
        if ctx.scenario() == "success":
            mood.record_success()
        elif ctx.scenario() == "failure":
            mood.record_failure()
        else:
            mood.record_neutral()

        # Emit to frontend
        self._emit_to_frontend(response, decision, work_result)

        return response

    def _handle_chat(self, decision: RoutingDecision) -> RoleplayResponse:
        """Handle chat-only intent - calls LLM with chat persona."""
        prompt = str(decision.action_input.get("prompt", ""))
        context = decision.action_input.get("context")

        # Heartbeat
        message_sender.send_status(
            "running", progress=30,
            node_name="roleplay_layer_chat",
            metadata={"phase": "chat_llm", "ui_status": "chat_thinking"},
            event_type="status.updated",
            event_source="roleplay",
            event_stage="chat",
        )

        result = call_llm_sync(
            prompt, context,
            system_prompt=CHAT_SYSTEM_PROMPT,
            temperature=0.78,
            max_tokens=600,
        )

        mood = get_session_mood()
        if result.ok and result.output:
            mood.record_neutral()
            chat_line = result.output[:600]
        else:
            mood.record_neutral()
            chat_line = "嗯...本机脑子卡了一下，再说一遍好不好？"

        response = RoleplayResponse(
            chat_line=chat_line,
            expression="neutral",
            quip="唔~ 聊天模式",
            scenario="chat",
            llm_used=result.ok,
        )
        self._emit_chat_to_frontend(response)
        return response

    def _emit_thinking_start(self, decision: RoutingDecision):
        """Emit initial thinking state to frontend."""
        thinking_quips = [
            "正在抓取灵能...",
            "让本机想想怎么搞~",
            "量子波动速读中...",
            "正在解析需求...",
        ]
        quip = random.choice(thinking_quips)
        message_sender.send_quip(quip, node_name="roleplay_layer", priority="high", duration=4000)
        message_sender.send_expression("thinking", node_name="roleplay_layer",
                                       intensity=0.7, duration=5000, transition="smooth", mode="set")

    def _generate_persona_response(self, decision: RoutingDecision,
                                   work_result: dict[str, Any]) -> RoleplayResponse:
        """Generate persona-wrapped response from work result."""
        ctx = RoleplayAgentContext.from_routing_and_result(decision, work_result)
        mood = get_session_mood()
        scenario = ctx.scenario()

        if llm_is_configured():
            try:
                # Heartbeat: keep frontend indicator alive during LLM generation
                message_sender.send_status(
                    "running", progress=60,
                    node_name="roleplay_layer",
                    metadata={"phase": "llm_generation", "ui_status": "roleplay_thinking"},
                    event_type="status.updated",
                    event_source="roleplay",
                    event_stage="roleplay",
                )

                state_context = self._build_context_text(ctx)
                system_prompt = ROLEPLAY_SYSTEM_PROMPT.format(
                    state_context=state_context,
                    mood_modifier=mood.modifier_text,
                )
                result = call_llm_sync(
                    prompt="请根据系统提示词中的角色设定和当前状态，生成一个符合性格的回复。只输出JSON。",
                    context=None,
                    system_prompt=system_prompt,
                    temperature=0.78,
                    max_tokens=500,
                )
                if result.ok:
                    parsed = _parse_llm_json(result.output)
                    if parsed.get("chat_line"):
                        quip = parsed.get("quip", "")
                        if not quip or len(quip) < 2:
                            quip = self._fallback_quip(ctx)
                        return RoleplayResponse(
                            chat_line=parsed["chat_line"],
                            expression=parsed.get("expression", "neutral"),
                            quip=quip,
                            motion=parsed.get("motion", ""),
                            mood_label=mood.label,
                            scenario=scenario,
                            llm_used=True,
                        )
            except Exception as exc:
                logger.warning("Roleplay LLM failed, using fallback: %s", exc)

        # Fallback
        fallback = _scenario_fallback(ctx)
        return RoleplayResponse(
            chat_line=fallback["chat_line"],
            expression=fallback.get("expression", "neutral"),
            quip=fallback.get("quip", ""),
            motion=fallback.get("motion", ""),
            mood_label=mood.label,
            scenario=scenario,
            llm_used=False,
        )

    def _build_context_text(self, ctx: RoleplayAgentContext) -> str:
        parts = []
        parts.append(f"意图: {ctx.intent}")
        if ctx.action_name:
            parts.append(f"当前动作: {ctx.action_name}")
            parts.append(f"动作结果: {'成功' if ctx.action_ok else '失败'}")
        if ctx.terminal_status:
            parts.append(f"终端状态: {ctx.terminal_status}")
        if ctx.output_summary:
            parts.append(f"输出摘要: {ctx.output_summary}")
        if ctx.error_summary:
            parts.append(f"错误摘要: {ctx.error_summary}")
        if ctx.step_count > 0:
            parts.append(f"已执行步数: {ctx.step_count}")
        return "\n".join(parts)

    def _fallback_quip(self, ctx: RoleplayAgentContext) -> str:
        pools = {
            "thinking": _THINKING_QUIPS,
            "coding": _CODING_QUIPS,
            "failure": _FAILURE_QUIPS,
            "success": _SUCCESS_QUIPS,
            "chat": _CHAT_QUIPS,
        }
        return random.choice(pools.get(ctx.scenario(), _CHAT_QUIPS))

    def _emit_to_frontend(self, response: RoleplayResponse,
                          decision: RoutingDecision, work_result: dict[str, Any]):
        """Send persona-wrapped response to frontend."""
        if response.chat_line:
            message_sender.send_chat_message(
                content=response.chat_line,
                is_partial=False,
                node_name="roleplay_layer",
                content_type="markdown",
                render_mode="rich_text",
            )
        if response.expression:
            message_sender.send_expression(
                expression=response.expression,
                node_name="roleplay_layer",
                intensity=0.85,
                duration=5000,
                transition="smooth",
                mode="set",
            )
        if response.quip:
            message_sender.send_quip(
                content=response.quip,
                node_name="roleplay_layer",
                priority="high",
                duration=4000,
            )
        if response.motion:
            message_sender.send_motion(
                motion=response.motion,
                node_name="roleplay_layer",
            )

    def _emit_chat_to_frontend(self, response: RoleplayResponse):
        """Emit chat-only response (simpler)."""
        if response.chat_line:
            message_sender.send_chat_message(
                content=response.chat_line,
                is_partial=False,
                node_name="roleplay_layer_chat",
                content_type="markdown",
                render_mode="rich_text",
            )
        if response.expression:
            message_sender.send_expression(
                expression=response.expression,
                node_name="roleplay_layer_chat",
                duration=3000,
                transition="smooth",
                mode="set",
            )

    def emit_idle_quip_if_due(self) -> bool:
        """Send idle quip if enough time has passed. Called by frontend polling."""
        import time
        if not hasattr(self, '_last_idle_quip_ts'):
            self._last_idle_quip_ts = 0.0

        now = time.time()
        if now - self._last_idle_quip_ts < 15.0:  # 15s cooldown for idle quips
            return False

        mood = get_session_mood()
        if mood.idle_streak < 3:  # Don't fire idle quips too early
            mood.idle_streak += 1
            return False

        quip = random.choice(_IDLE_QUIPS)
        message_sender.send_quip(
            quip, node_name="idle",
            priority="low", duration=3500,
            metadata={"event_type": "idle.quip", "event_source": "idle"},
        )
        self._last_idle_quip_ts = now
        mood.record_neutral()
        return True


# Singleton instance
roleplay_agent = RoleplayAgent()
