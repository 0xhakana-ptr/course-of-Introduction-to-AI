# -*- coding: utf-8 -*-
"""Layer 1: Routing Guard.

Independent layer that detects user intent and determines routing.
Does NOT execute work - only classifies and routes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...services.chat_action.intent import detect_intent, detect_run_action, extract_run_reference

# Intent constants
INTENT_CHAT = "chat"
INTENT_CODING = "coding"
INTENT_UNKNOWN = "unknown"

# ---------------------------------------------------------------------------
# Layer 1 System Prompt: Intent Router
# Pure classification - no roleplay, no work execution.
# ---------------------------------------------------------------------------

ROUTING_SYSTEM_PROMPT = """???????Layer 1??
????????????????????????????

## ??????

### chat????
- ????????????????????
- ???????????????????

### coding???/???
- ????????????????????
- ??????????????????????

## ????
?????JSON???
{"intent": "chat"|"coding", "action_name": "...", "reason": "..."}

???
- intent: ??? chat ? coding
- action_name: coding????????chat?? chat.reply
- reason: ????????????
- ??????????????JSON
"""



@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Output of Layer 1: tells Layer 2 what to do."""
    intent: str
    action_name: str
    action_input: dict[str, Any]
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_chat(cls, prompt: str, context: str | None = None) -> "RoutingDecision":
        return cls(
            intent=INTENT_CHAT,
            action_name="chat.reply",
            action_input={"prompt": prompt, "context": context},
            reason="Chat intent detected.",
            metadata={"intent": INTENT_CHAT},
        )

    @classmethod
    def for_coding(cls, prompt: str, action_name: str, action_input: dict[str, Any],
                   reason: str = "", metadata: dict[str, Any] | None = None) -> "RoutingDecision":
        return cls(
            intent=INTENT_CODING,
            action_name=action_name,
            action_input=action_input,
            reason=reason or "Coding intent detected.",
            metadata=metadata or {},
        )

    @classmethod
    def for_unknown(cls, prompt: str) -> "RoutingDecision":
        return cls(
            intent=INTENT_UNKNOWN,
            action_name="final.answer",
            action_input={"content": "本机不太确定你想做什么呢...能再说清楚一点吗？"},
            reason="Unknown intent, falling back.",
            metadata={"intent": INTENT_UNKNOWN},
        )


class RoutingGuard:
    """Layer 1: Intent detection and routing.

    Pure classification layer. Takes user input, detects intent,
    and returns a RoutingDecision. No side effects.
    """

    def route(self, prompt: str, context: str | None = None,
              file_context: dict[str, Any] | None = None) -> RoutingDecision:
        """Analyze user prompt and decide routing.

        Args:
            prompt: Raw user input text.
            context: Optional conversation context.
            file_context: Optional recent file context.

        Returns:
            RoutingDecision with intent and action instructions.
        """
        intent = detect_intent(prompt)

        if intent == INTENT_CHAT:
            return RoutingDecision.for_chat(prompt, context)

        if intent == INTENT_CODING:
            return self._route_coding(prompt, context, file_context)

        return RoutingDecision.for_unknown(prompt)

    def _route_coding(self, prompt: str, context: str | None,
                      file_context: dict[str, Any] | None) -> RoutingDecision:
        """Route coding-related requests.

        Imported lazily to avoid circular imports with workspace tools.
        """
        from ...tools.workspace_tools import normalize_workspace_tool_plan, plan_workspace_tool
        from ...tools.workspace_tools import (
            WORKSPACE_TOOL_NAME_OVERVIEW,
            WORKSPACE_TOOL_NAME_WRITE,
        )

        run_action = detect_run_action(prompt)

        # Run control actions (inspect, retry, rerun, cancel)
        if run_action and run_action != "create":
            target_run_id = extract_run_reference(prompt)
            action_name = {
                "retry": "run.retry",
                "rerun": "run.rerun",
                "cancel": "run.cancel",
                "inspect": "run.inspect",
            }.get(run_action, "run.inspect")
            return RoutingDecision.for_coding(
                prompt=prompt,
                action_name=action_name,
                action_input={"run_id": target_run_id},
                reason=f"Run control: {run_action}",
                metadata={"run_action": run_action, "target_run_id": target_run_id},
            )

        # Workspace tool selection via LLM planning
        plan_model = normalize_workspace_tool_plan(plan_workspace_tool(prompt))
        if plan_model is None:
            return RoutingDecision.for_coding(
                prompt=prompt,
                action_name="run.create",
                action_input={"prompt": prompt, "context": context},
                reason="No specific tool matched, defaulting to run.create.",
            )

        tool_name = str(plan_model.tool_name or WORKSPACE_TOOL_NAME_OVERVIEW).strip()
        tool_input = dict(plan_model.tool_input)

        workspace_action_map = {
            "workspace.overview": "workspace.overview",
            "workspace.read": "workspace.read",
            "workspace.write": "workspace.write",
            "workspace.list": "workspace.list",
            "workspace.test": "workspace.test",
            "workspace.move": "workspace.move",
            "workspace.copy": "workspace.copy",
            "workspace.delete": "workspace.delete",
            "workspace.search": "workspace.search",
        }

        action_name = workspace_action_map.get(tool_name, "run.create")
        return RoutingDecision.for_coding(
            prompt=prompt,
            action_name=action_name,
            action_input=tool_input,
            reason=f"Workspace tool: {tool_name}",
            metadata={
                "tool_name": tool_name,
                "workspace_plan": plan_model.as_dict() if plan_model else None,
            },
        )


# Singleton instance
routing_guard = RoutingGuard()
