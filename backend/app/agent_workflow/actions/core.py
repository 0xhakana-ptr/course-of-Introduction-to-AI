from __future__ import annotations

from collections.abc import Mapping

from ...messaging.message_sender import message_sender
from .models import AgentActionDefinition, AgentActionDescriptor, AgentActionResult
from ..utils.shared import normalize_text



def _chat_reply(action_input: Mapping[str, object]) -> AgentActionResult:
    content = normalize_text(action_input.get("content"))
    return AgentActionResult(
        action_name="chat.reply",
        ok=True,
        summary=content,
        data={"content": content},
    )


def _final_answer(action_input: Mapping[str, object]) -> AgentActionResult:
    content = normalize_text(action_input.get("content"))
    return AgentActionResult(
        action_name="final.answer",
        ok=True,
        summary=content,
        data={"content": content},
    )


def _ask_user_confirmation(action_input: Mapping[str, object]) -> AgentActionResult:
    prompt = normalize_text(action_input.get("prompt"), default="请确认是否继续。")
    blocked_action_name = normalize_text(action_input.get("blocked_action_name")) or None
    blocked_action_input = (
        dict(action_input.get("blocked_action_input"))
        if isinstance(action_input.get("blocked_action_input"), Mapping)
        else None
    )
    return AgentActionResult(
        action_name="ask_user_confirmation",
        ok=True,
        summary=prompt,
        data={
            "prompt": prompt,
            "requires_confirmation": True,
            "blocked_action_name": blocked_action_name,
            "blocked_action_input": blocked_action_input,
        },
        metadata={
            "requires_confirmation": True,
            "blocked_action_name": blocked_action_name,
        },
    )


def _character_quip(action_input: Mapping[str, object]) -> AgentActionResult:
    content = normalize_text(action_input.get("content"))
    node_name = normalize_text(action_input.get("node_name"), default="agent_action")
    ok = message_sender.send_quip(content, node_name=node_name)
    return AgentActionResult(
        action_name="character.quip",
        ok=ok,
        summary=content,
        data={"content": content, "node_name": node_name},
        error=None if ok else "failed to send quip",
    )


def _character_motion(action_input: Mapping[str, object]) -> AgentActionResult:
    motion = normalize_text(action_input.get("motion"))
    node_name = normalize_text(action_input.get("node_name"), default="agent_action")
    ok = message_sender.send_motion(motion, node_name=node_name)
    return AgentActionResult(
        action_name="character.motion",
        ok=ok,
        summary=motion,
        data={"motion": motion, "node_name": node_name},
        error=None if ok else "failed to send motion",
    )


def _character_expression(action_input: Mapping[str, object]) -> AgentActionResult:
    expression = normalize_text(action_input.get("expression"))
    node_name = normalize_text(action_input.get("node_name"), default="agent_action")
    ok = message_sender.send_expression(expression, node_name=node_name)
    return AgentActionResult(
        action_name="character.expression",
        ok=ok,
        summary=expression,
        data={"expression": expression, "node_name": node_name},
        error=None if ok else "failed to send expression",
    )


def list_core_action_definitions() -> list[AgentActionDefinition]:
    return [
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="chat.reply",
                description="Return a direct chat reply without calling tools.",
                category="chat",
                input_keys=("content",),
                output_keys=("content",),
                safety_level="low",
                user_visible_label="直接回复",
            ),
            executor=_chat_reply,
        ),
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="final.answer",
                description="Finalize the current Agent turn with a user-visible answer.",
                category="final",
                input_keys=("content",),
                output_keys=("content",),
                safety_level="low",
                user_visible_label="最终回复",
            ),
            executor=_final_answer,
        ),
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="ask_user_confirmation",
                description="Stop and ask the user to confirm a risky action.",
                category="confirmation",
                input_keys=("prompt",),
                output_keys=("prompt", "requires_confirmation"),
                safety_level="low",
                requires_confirmation=True,
                user_visible_label="请求确认",
            ),
            executor=_ask_user_confirmation,
        ),
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="character.quip",
                description="Send a short quip to the desktop pet UI.",
                category="character",
                input_keys=("content", "node_name"),
                output_keys=("sent",),
                safety_level="low",
                user_visible_label="发送提示语",
            ),
            executor=_character_quip,
        ),
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="character.motion",
                description="Send a motion command to the desktop pet UI.",
                category="character",
                input_keys=("motion", "node_name"),
                output_keys=("sent",),
                safety_level="low",
                user_visible_label="切换动作",
            ),
            executor=_character_motion,
        ),
        AgentActionDefinition(
            descriptor=AgentActionDescriptor(
                name="character.expression",
                description="Send an expression command to the desktop pet UI.",
                category="character",
                input_keys=("expression", "node_name"),
                output_keys=("sent",),
                safety_level="low",
                user_visible_label="切换表情",
            ),
            executor=_character_expression,
        ),
    ]
