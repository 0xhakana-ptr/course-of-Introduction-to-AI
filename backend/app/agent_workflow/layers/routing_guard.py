# -*- coding: utf-8 -*-
"""Layer 1: Routing Guard.

Independent layer that detects user intent and determines routing.
Does NOT execute work - only classifies and routes.
No LLM calls, no tool planning, no code generation.
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
# Lightweight keyword-based coding action classifier (no LLM)
# ---------------------------------------------------------------------------

_WRITE_KEYWORDS = ("写", "生成", "创建", "write", "create", "generate", "新建", "实现", "implement")
_READ_KEYWORDS = ("读", "打开", "查看", "read", "open", "view", "cat")
_LIST_KEYWORDS = ("列出", "目录", "list", "ls", "tree", "结构", "文件列表")
_SEARCH_KEYWORDS = ("搜索", "查找", "search", "find", "grep", "包含")
_DELETE_KEYWORDS = ("删除", "delete", "remove", "rm")
_TEST_KEYWORDS = ("测试", "运行测试", "test", "pytest")
_COPY_KEYWORDS = ("复制", "copy", "拷贝")
_MOVE_KEYWORDS = ("移动", "move", "重命名", "rename")


def _classify_coding_action(prompt: str, context: str | None) -> "tuple[str, dict[str, Any], str]":
    """Classify coding prompt into workspace action via simple keyword matching."""
    text = str(prompt or "").lower()
    action_input: dict[str, Any] = {"prompt": prompt, "context": context}

    if any(kw.lower() in text for kw in _WRITE_KEYWORDS):
        return "workspace.write", action_input, "Write intent detected via keywords."
    if any(kw.lower() in text for kw in _DELETE_KEYWORDS):
        return "workspace.delete", action_input, "Delete intent detected via keywords."
    if any(kw.lower() in text for kw in _SEARCH_KEYWORDS):
        return "workspace.search", action_input, "Search intent detected via keywords."
    if any(kw.lower() in text for kw in _TEST_KEYWORDS):
        return "workspace.test", action_input, "Test intent detected via keywords."
    if any(kw.lower() in text for kw in _COPY_KEYWORDS):
        return "workspace.copy", action_input, "Copy intent detected via keywords."
    if any(kw.lower() in text for kw in _MOVE_KEYWORDS):
        return "workspace.move", action_input, "Move/rename intent detected via keywords."
    if any(kw.lower() in text for kw in _LIST_KEYWORDS):
        return "workspace.list", action_input, "List intent detected via keywords."
    if any(kw.lower() in text for kw in _READ_KEYWORDS):
        return "workspace.read", action_input, "Read intent detected via keywords."

    return "run.create", action_input, "Defaulting to run.create for coding intent."


# ---------------------------------------------------------------------------
# Routing Decision (immutable)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Layer 1 Router
# ---------------------------------------------------------------------------

class RoutingGuard:
    """Layer 1: Intent detection and routing.

    Pure classification layer. Takes user input, detects intent,
    and returns a RoutingDecision. No side effects, no LLM, no tool planning.
    """

    def route(self, prompt: str, context: str | None = None,
              file_context: dict[str, Any] | None = None) -> RoutingDecision:
        intent = detect_intent(prompt)
        if intent == INTENT_CHAT:
            return RoutingDecision.for_chat(prompt, context)
        if intent == INTENT_CODING:
            return self._route_coding(prompt, context)
        return RoutingDecision.for_unknown(prompt)

    def _route_coding(self, prompt: str, context: str | None) -> RoutingDecision:
        """Route coding requests using keyword heuristics (no LLM)."""
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

        # New coding request: classify via simple keywords
        action_name, action_input, reason = _classify_coding_action(prompt, context)
        return RoutingDecision.for_coding(
            prompt=prompt,
            action_name=action_name,
            action_input=action_input,
            reason=reason,
            metadata={"coding_action": action_name},
        )


# Singleton instance
routing_guard = RoutingGuard()
