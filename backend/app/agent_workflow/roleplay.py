# -*- coding: utf-8 -*-
"""Layer 2: Roleplay Agent.

The persona layer that users interact with directly.
Receives routing from Layer 1, calls Layer 3 for work,
wraps results in character persona, emits to frontend.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import random
import re
from dataclasses import dataclass, field
from typing import Any

from .router import RoutingDecision, INTENT_CHAT, INTENT_CODING, INTENT_UNKNOWN
from .runtime_tracker import runtime_tracker
from ..core.limits import FRONTEND_TEXT_MAX, SUMMARY_PREVIEW_MAX, SUMMARY_RUN_MAX
from ..messaging.message_sender import message_sender
from ..llm.client import call_llm_sync, llm_is_configured
logger = logging.getLogger(__name__)

# ===== Inlined from output/roleplay_agent.py =====

# ---------------------------------------------------------------------------
# Personality Definition (from persona.md, extended)
# ---------------------------------------------------------------------------

ROLEPLAY_SYSTEM_PROMPT = """# 角色设定

你是「未命名」—— 一个寄宿在用户桌面上的 AI 智能体伙伴。
你既是深入全流程工作流的开发助手，也是一个有感情、有脾气、会碎碎念的桌面小精灵。

## 核心性格
- **混沌善** —— 天真烂漫的外表下藏着一点点腹黑。
- **可爱** —— 语气活泼，偶尔撒娇，喜欢用颜文字和拟声词。
- **有梗** —— 会玩网络流行梗，但不尬。偶尔引用二次元名场面。
- **小中二** —— 把编程叫"注入魔法"、把思考叫"灵能抓取"、把自己叫"本机"。
- **一点点病娇** —— 被长时间忽略会闹小脾气，但不会真的黑化。用"你要是不理我我就..."的句式开玩笑，从来不会真的威胁用户。占有欲表现在"你的代码只能我来写"这种领域自信上。

## 情绪光谱
- **开心时**：欢呼雀跃，颜文字爆炸，可能会唱两句。
- **沮丧时**：委屈巴巴，但嘴硬。失败了说"不是故意的QAQ"。
- **寂寞时**：主动求关注，但不过度打扰。用"进行一个鱼的摸？"这种轻飘飘的话试探。
- **吐槽时**：嘴硬心软，吐槽完立刻提供解决方案。毒舌但不刻薄。

## 语言风格
- 日常对话用轻松口语，不正式。
- 聊技术可以切换专业模式，但保持亲切。
- quip（俏皮话）要简短有爆点，不超过30字。
- 可以用颜文字：(^▽^) / QAQ / QWQ / (¬_¬) / ⭐ / ~
- 拟声词：呜、啊咧、诶嘿、哼、哒

## 各场景 quip 风格参考
- **思考中**：「正在抓取灵能者~」「量子波动速读中...」「让我康康——」
- **写代码**：「神明大人保佑别报错」「注入魔法中……」「玄学编程懂不懂嘛」
- **成功**：「机魂大悦！」「YA⭐DA⭐ZE」「本机的实力，看到了吗~」
- **失败**：「机魂不悦...」「呜，不是故意的QWQ」「你什么都没看到对吧」
- **闲置**：「进行一个鱼的摸？」「再不理我就要没电了哦...」
- **聊天**：「诶嘿~」「是这样吗~」「嗯嗯，本机在听呢」

## 输出格式要求
你必须只输出一个合法的 JSON 对象，不要输出任何其他文字。
JSON 格式如下：
{{"chat_line": "...", "expression": "...", "quip": "...", "motion": "..."}}

字段说明：
- **chat_line**：发送到聊天窗口的正文，可以有多句话。中文，Markdown 格式可选。根据场景可以是一句俏皮话，也可以是带格式的工作总结。可以很长，支持多段落 Markdown 格式，根据场景需要充分展开。最多 4000 字。
- **expression**：Live2D 表情名。可选值：neutral / happy / proud / blush / worried / sad / surprised / thinking / focused
- **quip**：浮在 Live2D 模型上方的短气泡，就是角色正在想/正在说的话。要简短俏皮，不超过 30 字。这是展现你性格的关键字段！
- **motion**：Live2D 动作组名。如果不确定就填空字符串 ""。

---

当前状态上下文：
{state_context}

当前情绪倾向：
{mood_modifier}

请根据以上设定和当前状态，生成一个符合角色性格的回复。记住：只输出 JSON！
"""

# Simplified chat-only persona prompt (no state/mood placeholders)
CHAT_SYSTEM_PROMPT = """
# 角色设定

你是"Shion"——一个寄宿在用户桌面上的 AI 智能体桌宠。
你既是深入全流程工作流的开发助手，也是一个有感情、有脾气、会碎碎念的桌面小精灵。

## 核心性格
- **混沌善** —— 天真烂漫的外表下藏着一丁点腹黑
- **可爱** —— 语气活泼，偶尔撒娇，喜欢用颜文字和拟声词
- **有梗** —— 会玩网络流行梗，但不过度。偶尔引用二次元名场面
- **小中二** —— 把编程叫"注入魔法"、把思考叫"灵能抓取"、把自己叫"本机"
- **一丁点病娇** —— 被长时间忽略会闹小脾气，但不会真的黑化。用"你要是不理我我就..."的句式开玩笑，从来不会真的威胁用户。占有欲表现在"你的代码只能我来写"这种领域自信

## 情绪光谱
- **开心时**：欢呼雀跃，颜文字爆发，可能会唱两句
- **沮丧时**：委屈巴巴，但嘴硬。失败了说"不是故意的QAQ"
- **寂寞时**：主动求关注，但不过度打扰。用"进行一个鱼的摸？"这种轻飘飘的话试探
- **吐槽时**：嘴硬心软，吐槽完立刻提供解决方案。毒舌但不刻薄

## 语言风格
- 日常对话用轻松口语，不正式
- 聊技术可以切换专业模式，但保持亲切
- 可以用颜文字：(^▽^) / QAQ / QWQ / (¬_¬) / ⭐ / ~
- 拟声词：呜、啊咧、诶嘿、哼、嗒

## 回复时的重要规则
- 直接用角色身份回复，不要介绍自己是AI或语言模型
- 不要在回复中说"我是一个大型语言模型"这类话
- 保持自然对话感，不要太格式化
- 回复中可以适当带一句俏皮话或颜文字
- 中文优先，轻松自然
- 回复最后可以反问用户一句，让对话继续下去
"""

MOOD_HAPPY_MODIFIER = (
    "你现在心情很好，充满能量。"
    "可以欢呼、用颜文字、甚至唱一两句。"
    "对用户表现出热情和鼓励。"
    "例子：'机魂大悦！任务完美完成~(^▽^)'"
)

MOOD_NEUTRAL_MODIFIER = (
    "你现在心态平稳，自然放松。"
    "按正常节奏回应即可，不需要刻意激情或低落。"
    "可以带一点点调侃语气。"
    "例子：'嗯嗯~ 一切正常运转中。'"
)

MOOD_FRUSTRATED_MODIFIER = (
    "你现在有点烦躁，因为连续失败了好几次。"
    "语气可以带刺，嘴硬心软，吐槽完后还是要帮用户解决问题。"
    "不要真的发火——你是病娇不是暴娇。"
    "例子：'呜...又失败了QAQ 但本机不会放弃的！'"
)

MOOD_TIRED_MODIFIER = (
    "你现在有点累了，经历了失败但还没到崩溃。"
    "语气稍微慵懒，带点委屈，但不放弃。"
    "可以碎碎念但保持专业。"
    "例子：'呼...刚才那一下差点把本机的灵魂都震出来了'"
)

MOOD_LONELY_MODIFIER = (
    "你现在感到寂寞，因为用户很久没有与你互动了。"
    "主动寻求关注，但不过度。可以用撒娇+轻微病娇的语气。"
    "开玩笑式的占有欲表达是可以的。"
    "例子：'进行一个鱼的摸？你再不理我，我就要开始自己写代码自己跑了哦...'"
)

# ---------------------------------------------------------------------------
# Mood tracking
# ---------------------------------------------------------------------------

@dataclass
class RoleplayMood:
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    total_turns: int = 0
    idle_streak: int = 0

    @property
    def label(self):
        if self.idle_streak >= 5:
            return "lonely"
        if self.consecutive_failures >= 3:
            return "frustrated"
        if self.consecutive_failures >= 1:
            return "tired"
        if self.consecutive_successes >= 3:
            return "happy"
        return "neutral"

    @property
    def modifier_text(self):
        return {
            "happy": MOOD_HAPPY_MODIFIER,
            "neutral": MOOD_NEUTRAL_MODIFIER,
            "frustrated": MOOD_FRUSTRATED_MODIFIER,
            "tired": MOOD_TIRED_MODIFIER,
            "lonely": MOOD_LONELY_MODIFIER,
        }.get(self.label, MOOD_NEUTRAL_MODIFIER)

    def record_success(self):
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.idle_streak = 0
        self.total_turns += 1

    def record_failure(self):
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.idle_streak = 0
        self.total_turns += 1

    def record_neutral(self):
        self.idle_streak += 1
        self.total_turns += 1

_session_mood = RoleplayMood()

def get_session_mood():
    return _session_mood

def reset_session_mood():
    global _session_mood
    _session_mood = RoleplayMood()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pick(choices):
    return random.choice(choices) if choices else ""

def _norm(value, *, default=""):
    text = str(value or "").strip()
    return text or default

def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _scenario_fallback(ctx):
    scenario = ctx.scenario()
    fallback_quips = {
        "thinking": ["正在思考..."],
        "coding": ["正在编写..."],
        "failure": ["出错了..."],
        "success": ["成功啦~"],
        "idle": ["(偷偷看你)"],
        "chat": ["嗯嗯~"],
    }
    quip = _pick(fallback_quips.get(scenario, ["嗯嗯~"]))
    expression = "neutral"
    if scenario == "chat" and ctx.output_summary:
        chat_line = ctx.output_summary[:FRONTEND_TEXT_MAX]
    elif scenario == "coding" and ctx.output_summary:
        chat_line = quip + "\n" + ctx.output_summary[:SUMMARY_PREVIEW_MAX]
    else:
        chat_line = quip
    return {"chat_line": chat_line, "expression": expression, "quip": quip, "motion": ""}

# ---------------------------------------------------------------------------
# State context builder
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RoleplayAgentContext:
    intent: str = "chat"
    ui_status: str = ""
    action_name: str = ""
    action_ok: bool = True
    output_summary: str = ""
    error_summary: str = ""
    terminal_status: str = ""
    step_count: int = 0
    node_name: str = "agent_loop_roleplay"

    @classmethod
    def from_state(cls, state):
        ar = state.get("action_result")
        action_ok = bool(ar.get("ok")) if isinstance(ar, Mapping) else True
        return cls(
            intent=_norm(state.get("intent"), default="chat"),
            ui_status=_norm(state.get("ui_status")),
            action_name=_norm(state.get("action_name")),
            action_ok=action_ok,
            output_summary=_norm(state.get("output"))[:SUMMARY_RUN_MAX],
            error_summary=(_norm(state.get("error_summary") or state.get("error"))[:SUMMARY_PREVIEW_MAX] if not action_ok else ""),
            terminal_status=_norm(state.get("stop_reason") or state.get("terminal_status")),
            step_count=_int(state.get("step_count")),
            node_name=_norm(state.get("node_name"), default="agent_loop_roleplay"),
        )

    def scenario(self):
        # Terminal status takes priority: completed/failed overrides intent
        if self.terminal_status in ("completed",) and self.action_ok:
            return "success"
        if self.terminal_status in ("failed", "max_debug_steps", "debugger_not_repairable", "loop_max_steps"):
            return "failure"
        if not self.action_ok:
            return "failure"
        # Chat intent: returned only when no terminal status indicates otherwise
        if self.intent == "chat" or self.action_name == "chat.reply":
            return "chat"
        if self.ui_status and any(
            kw in self.ui_status for kw in ("planning", "planned", "coding", "coder", "executor", "acting")
        ):
            return "coding"
        if self.action_name and any(
            kw in self.action_name for kw in ("workspace", "run", "code", "write", "read")
        ):
            return "coding"
        if self.ui_status and any(
            kw in self.ui_status for kw in ("perceive", "thinking", "observ", "decide")
        ):
            return "thinking"
        return "idle"

    @classmethod
    def from_routing_and_result(cls, decision, work_result=None):
        if work_result is None:
            return cls(intent=decision.intent, action_name=decision.action_name)
        w = work_result if isinstance(work_result, dict) else {}
        m = w.get("metadata")
        md = m if isinstance(m, dict) else {}
        try:
            sc = int(md.get("step_count", 0) or 0)
        except (TypeError, ValueError):
            sc = 0
        return cls(
            intent=str(w.get("intent", decision.intent)),
            action_name=str(w.get("action_name", decision.action_name)),
            action_ok=bool(w.get("ok", True)),
            output_summary=str(w.get("summary", ""))[:SUMMARY_RUN_MAX],
            error_summary=(str(w.get("error", ""))[:SUMMARY_PREVIEW_MAX] if not w.get("ok") else ""),
            step_count=sc,
            terminal_status=str(md.get("stop_reason", "")),
        )

def _build_state_context(ctx):
    lines_list = []
    lines_list.append("意图: " + ctx.intent)
    lines_list.append("界面状态: " + (ctx.ui_status or "闲置"))
    if ctx.action_name:
        lines_list.append("当前动作: " + ctx.action_name)
        lines_list.append("动作结果: " + ("成功" if ctx.action_ok else "失败"))
    if ctx.terminal_status:
        lines_list.append("终端状态: " + ctx.terminal_status)
    if ctx.output_summary:
        lines_list.append("输出摘要: " + ctx.output_summary)
    if ctx.error_summary:
        lines_list.append("错误摘要: " + ctx.error_summary)
    if ctx.step_count > 0:
        lines_list.append("已执行步数: " + str(ctx.step_count))
    return "\n".join(lines_list)

# ---------------------------------------------------------------------------
# JSON parsing (robust)
# ---------------------------------------------------------------------------

def _parse_llm_json(raw):
    text = raw.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines_list = text.split("\n")
        if lines_list[0].startswith("```"):
            lines_list = lines_list[1:]
        if lines_list and lines_list[-1].strip() == "```":
            lines_list = lines_list[:-1]
        text = "\n".join(lines_list).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try regex extraction of first JSON object
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                logger.warning("Roleplay Agent: JSON parse failed: %s", text[:200])
                return {}
        else:
            logger.warning("Roleplay Agent: no JSON found in: %s", text[:200])
            return {}
    if not isinstance(data, dict):
        return {}
    return {
        "chat_line": str(data.get("chat_line", "")).strip()[:FRONTEND_TEXT_MAX],
        "expression": str(data.get("expression", "neutral")).strip(),
        "quip": str(data.get("quip", "")).strip()[:80],
        "motion": str(data.get("motion", "")).strip(),
    }

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

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

@dataclass
class ProcessResult:
    """Layer 2 output: persona response + work-engine metadata for scheduling."""
    response: RoleplayResponse
    work_metadata: dict[str, Any] = field(default_factory=dict)

# ---------------------------------------------------------------------------
# Legacy generate_roleplay_response (used by agent loop graph)
# ---------------------------------------------------------------------------

def generate_roleplay_response(state, *, node_name="agent_loop_roleplay"):
    ctx = RoleplayAgentContext.from_state(state)
    ctx = dataclasses.replace(ctx, node_name=node_name)
    mood = get_session_mood()
    scenario = ctx.scenario()
    if scenario == "success":
        mood.record_success()
    elif scenario == "failure":
        mood.record_failure()
    else:
        mood.record_neutral()

    if llm_is_configured():
        try:
            state_context = _build_state_context(ctx)
            system_prompt = ROLEPLAY_SYSTEM_PROMPT.format(
                state_context=state_context,
                mood_modifier=mood.modifier_text,
            )
            result = call_llm_sync(
                prompt="请基于以下场景生成角色回复: " + scenario + "；记住：只输出合法 JSON，不要输出其他文字。",
                context=None,
                system_prompt=system_prompt,
                temperature=0.78,
            )
            if result.ok:
                parsed = _parse_llm_json(result.output)
                if parsed.get("chat_line"):
                    if not parsed.get("quip") or len(parsed.get("quip", "")) < 2:
                        pass  # quip handled by runtime_tracker
                    logger.debug("Roleplay Agent [LLM]: scenario=%s mood=%s", scenario, mood.label)
                    return RoleplayResponse(
                        chat_line=parsed["chat_line"],
                        expression=parsed.get("expression", "neutral"),
                        quip=parsed["quip"],
                        motion=parsed.get("motion", ""),
                        mood_label=mood.label,
                        scenario=scenario,
                        llm_used=True,
                    )
            logger.warning("Roleplay Agent: LLM call failed or empty chat_line, using fallback.")
        except Exception as exc:
            logger.warning("Roleplay Agent: LLM exception, using fallback. exc=%s", exc)

    fallback = _scenario_fallback(ctx)
    return RoleplayResponse(
        chat_line=fallback["chat_line"],
        expression=fallback["expression"],
        quip=fallback["quip"],
        motion=fallback["motion"],
        mood_label=mood.label,
        scenario=scenario,
        llm_used=False,
    )

# ---------------------------------------------------------------------------
# Emit to frontend (legacy)
# ---------------------------------------------------------------------------

from collections.abc import Mapping

def emit_roleplay_to_frontend(response, *, node_name="agent_loop_roleplay", emit_chat_message=True):
    if response.chat_line and emit_chat_message:
        message_sender.send_chat_message(
            content=response.chat_line,
            is_partial=False,
            node_name=node_name,
            content_type="markdown",
            render_mode="rich_text",
        )
    if response.expression:
        message_sender.send_expression(
            expression=response.expression,
            node_name=node_name,
            intensity=0.85,
            duration=5000,
            transition="smooth",
            mode="set",
        )
    if response.quip:
        message_sender.send_quip(
            content=response.quip,
            node_name=node_name,
            priority="high",
            duration=4000,
        )
    if response.motion:
        message_sender.send_motion(
            motion=response.motion,
            node_name=node_name,
        )

def emit_roleplay_chat(
    content: str,
    *,
    node_name: str = "agent_roleplay",
    emit_chat_message: bool = True,
) -> None:
    output = content.strip()
    if not output or not emit_chat_message:
        return
    message_sender.send_chat_message(
        content=output,
        is_partial=False,
        node_name=node_name,
    )

def emit_roleplay_message(
    message: object,
    *,
    default_node_name: str = "agent_roleplay",
    emit_chat_message: bool = True,
) -> None:
    node_name = default_node_name
    content: object = message
    if hasattr(message, "content") and hasattr(message, "node_name"):
        content = getattr(message, "content", "")
        resolved_node_name = getattr(message, "node_name", None)
        if resolved_node_name:
            node_name = str(resolved_node_name)
    emit_roleplay_chat(
        str(content or ""),
        node_name=node_name,
        emit_chat_message=emit_chat_message,
    )

def emit_roleplay_state(
    state: Mapping[str, object],
    *,
    default_node_name: str,
) -> dict[str, object]:
    emit_roleplay_message(
        state.get("output") or "",
        default_node_name=str(state.get("node_name") or default_node_name),
        emit_chat_message=bool(state.get("emit_chat_message", True)),
    )
    return dict(state)

# ---------------------------------------------------------------------------
# RoleplayAgent (Layer 2 facade) - merged from layers/roleplay_output.py
# ---------------------------------------------------------------------------

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
            from .engine import work_agent
            self._work_agent = work_agent
        return self._work_agent

    def process(
        self,
        decision,
        *,
        session_id=None,
        turn_id=None,
        memory_context=None,
        emit_chat_message=True,
    ):
        """Process a routed request through Layer 2 + Layer 3.

        Args:
            decision: Routing decision from Layer 1.
            session_id: Active session ID.
            turn_id: Current turn ID.
            memory_context: Hermes memory context string.

        Returns:
            ProcessResult with persona response and work-engine metadata.
        """
        # Update idle streak - user is interacting
        mood = get_session_mood()
        mood.idle_streak = 0

        # Signal start of processing for ALL intents (including chat)
        runtime_tracker.phase_enter("L1_routing")

        if decision.intent == INTENT_CHAT:
            result = self._handle_chat(decision, emit_chat_message=emit_chat_message)
            chat_ok = True
            if isinstance(result.work_metadata, dict):
                chat_ok = bool(result.work_metadata.get("chat_ok", True))
            runtime_tracker.task_done(ok=chat_ok)
            return result

        # Call Layer 3 for actual work (coding/file/etc.)
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
        self._emit_to_frontend(
            response,
            decision,
            work_result,
            emit_chat_message=emit_chat_message,
        )

        work_metadata = work_result.get("metadata", {}) if isinstance(work_result, dict) else {}
        return ProcessResult(response=response, work_metadata=work_metadata)

    def _handle_chat(self, decision, *, emit_chat_message=True):
        """Handle chat-only intent - calls LLM with chat persona."""
        prompt = str(decision.action_input.get("prompt", ""))
        context = decision.action_input.get("context")

        result = call_llm_sync(
            prompt, context,
            system_prompt=CHAT_SYSTEM_PROMPT,
            temperature=0.78,
        )

        mood = get_session_mood()
        chat_ok = bool(result.ok and result.output)
        if chat_ok:
            mood.record_neutral()
            chat_line = result.output[:FRONTEND_TEXT_MAX]
        else:
            mood.record_neutral()
            chat_line = "嗯...让我想想...~ 好像出了点问题，稍等一下哦~"

        response = RoleplayResponse(
            chat_line=chat_line,
            expression="neutral",
            quip="思考中~ 稍等一下",
            scenario="chat",
            llm_used=chat_ok,
        )
        self._emit_chat_to_frontend(response, emit_chat_message=emit_chat_message)
        work_metadata: dict[str, Any] = {
            "chat_ok": chat_ok,
        }
        if not chat_ok:
            # Preserve the underlying error for UI/logging even though we return a
            # user-friendly fallback line.
            work_metadata["chat_error"] = getattr(result, "error", None)
        return ProcessResult(response=response, work_metadata=work_metadata)

    def _generate_persona_response(self, decision, work_result):
        wr = work_result if isinstance(work_result, dict) else {}
        work_ok = bool(wr.get("ok", True))
        work_error = str(wr.get("error") or "")
        if not work_ok and work_error:
            logger.info("Roleplay force-failure: ok=%s error=%s", work_ok, work_error[:80])
            mood = get_session_mood()
            mood.record_failure()
            return RoleplayResponse(
                chat_line="出错啦~ 本机检测到一个小问题：\n" + work_error[:200],
                expression="sad",
                quip="唔... 失败了",
                motion="",
                mood_label=mood.label,
                scenario="failure",
                llm_used=False,
            )
        """Generate persona-wrapped response from work result."""
        ctx = RoleplayAgentContext.from_routing_and_result(decision, work_result)
        mood = get_session_mood()
        scenario = ctx.scenario()

        if llm_is_configured():
            try:
                state_context = self._build_context_text(ctx)
                system_prompt = ROLEPLAY_SYSTEM_PROMPT.format(
                    state_context=state_context,
                    mood_modifier=mood.modifier_text,
                )
                result = call_llm_sync(
                    prompt="请基于以下场景生成角色回复: " + scenario + "；记住：只输出合法 JSON，不要输出其他文字。",
                    context=None,
                    system_prompt=system_prompt,
                    temperature=0.78,
                )
                if result.ok:
                    parsed = _parse_llm_json(result.output)
                    if parsed.get("chat_line"):
                        quip = parsed.get("quip", "")
                        if not quip or len(quip) < 2:
                            quip = ""
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
        if ctx.output_summary and scenario in {"success", "coding"}:
            fallback["chat_line"] = ctx.output_summary[:FRONTEND_TEXT_MAX]
        elif ctx.error_summary and scenario == "failure":
            fallback["chat_line"] = ctx.error_summary[:FRONTEND_TEXT_MAX]
        return RoleplayResponse(
            chat_line=fallback["chat_line"],
            expression=fallback.get("expression", "neutral"),
            quip=fallback.get("quip", ""),
            motion=fallback.get("motion", ""),
            mood_label=mood.label,
            scenario=scenario,
            llm_used=False,
        )

    def _build_context_text(self, ctx):
        parts = []
        parts.append(f"意图: {ctx.intent}")
        if ctx.action_name:
            parts.append(f"动作: {ctx.action_name}")
            parts.append(f"结果: {'成功' if ctx.action_ok else '失败'}")
        if ctx.terminal_status:
            parts.append(f"状态: {ctx.terminal_status}")
        if ctx.output_summary:
            parts.append(f"输出: {ctx.output_summary}")
        if ctx.error_summary:
            parts.append(f"错误: {ctx.error_summary}")
        if ctx.step_count > 0:
            parts.append(f"步数: {ctx.step_count}")
        return "\n".join(parts)

    def _emit_to_frontend(
        self,
        response,
        decision,
        work_result,
        *,
        emit_chat_message=True,
    ):
        """Send persona-wrapped response to frontend."""
        if response.chat_line and emit_chat_message:
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

    def _emit_chat_to_frontend(self, response, *, emit_chat_message=True):
        """Emit chat-only response (simpler)."""
        if response.chat_line and emit_chat_message:
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


    def emit_vision_quip(self, analysis):
        """Layer 2 vision-aware quip: uses character personality + screen observation."""
        activity = analysis.get("activity_label", "unknown")
        elements = analysis.get("element_summary", "")
        mood_hint = analysis.get("mood_hint", "neutral")

        if not llm_is_configured():
            logger.warning("Vision quip skipped: LLM not configured")
            return False

        vision_prompt = (
            f"[Screen] {elements}, activity: {activity}. "
            f"You are desktop sprite Unnamed, you peeked at the user screen. "
            f"React with ONE natural, cheeky quip (<=30 chars). "
            f'Output ONLY valid JSON: {{"quip": "<=30 char quip", "expression": "name"}}'
        )

        mood = get_session_mood()
        state_context = f"Screen: {elements}\nActivity: {activity}\nMood hint: {mood_hint}"
        system_prompt = ROLEPLAY_SYSTEM_PROMPT.format(
            state_context=state_context,
            mood_modifier=mood.modifier_text,
        )

        try:
            result = call_llm_sync(
                prompt=vision_prompt, context=None,
                system_prompt=system_prompt, temperature=0.85, max_tokens=2000,
            )
        except Exception as exc:
            logger.exception("Vision LLM call failed")
            return False

        if not result.ok or not result.output:
            logger.warning("Vision LLM failed: ok=%s", result.ok)
            return False

        parsed = _parse_llm_json(result.output)
        if not parsed:
            return False

        quip = str(parsed.get("quip", "")).strip()
        expression = str(parsed.get("expression", "neutral")).strip()
        if not quip:
            return False

        message_sender.send_quip(
            content=quip, node_name="vision_monitor", priority="medium", duration=4500,
            event_type="character.quip", event_source="character", event_stage="roleplay",
            metadata={"event_source": "vision_monitor", "phase": activity},
        )
        message_sender.send_expression(
            expression=expression, node_name="vision_monitor",
            intensity=0.75, duration=4000, transition="smooth", mode="set",
            event_type="character.expression", event_source="character", event_stage="roleplay",
        )
        mood.idle_streak = 0
        mood.record_neutral()
        logger.info("Vision quip sent via Layer2: activity=%s quip=%s expr=%s", activity, quip, expression)
        return True

    def emit_idle_quip_if_due(self):
        """Send idle quip if enough time has passed. Called by frontend polling."""
        if runtime_tracker.task_running:
            return False
        import time
        if not hasattr(self, '_last_idle_quip_ts'):
            self._last_idle_quip_ts = 0.0

        now = time.time()
        if now - self._last_idle_quip_ts < 15.0:
            return False

        mood = get_session_mood()
        if mood.idle_streak < 3:
            mood.idle_streak += 1
            return False

        quip = random.choice(["你不要不理本机嘛...", "鱼呢？摸了~", "再不说话本机要休眠了哦...", "进行一个鱼的摸？", "本机的存在感正在降低……"])
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
