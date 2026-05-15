"""Layer 2: Independent Roleplay Agent (V2 Architecture).

Receives sanitized FrontendState summaries and generates
in-character responses for Live2D model and chat window.
Personality sourced from persona.md — cute, witty, chuunibyou, with a hint of yandere.
All prompts and fallback quips in Chinese.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ...llm.client import call_llm_sync, llm_is_configured
from ...messaging.message_sender import message_sender

logger = logging.getLogger(__name__)


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
- **chat_line**：发送到聊天窗口的正文，可以有多句话。中文，Markdown 格式可选。根据场景可以是一句俏皮话，也可以是带格式的工作总结。最多 400 字。
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
# Fallback quips (when LLM unavailable) — Chinese, in-character
# ---------------------------------------------------------------------------

_THINKING_QUIPS = [
    "正在抓取灵能者~",
    "量子波动速读中...",
    "让我康康——",
    "本机正在深度思考，请稍候...",
    "呜~ JoJo，这个好难想啊！",
    "正在受奸奇祝福……啊不是，正在推理中！",
]

_CODING_QUIPS = [
    "高雅人士正在处理……",
    "正在注入魔法……",
    "神明大人保佑别报错！",
    "玄学编程，懂不懂嘛？",
    "敲敲敲……键盘冒烟了！",
    "小任务而已，马上搞定~",
    "这你自己搞不定吧(¬_¬)？放着我来！",
    "？！码码！？代码在跳舞！",
]

_FAILURE_QUIPS = [
    "机魂不悦……",
    "呜，失败了QAQ",
    "出小问题了，不是故意的QWQ",
    "你什么都没看到对吧？对吧对吧？",
    "呜...任务失败了，再来一次嘛，本机保证这次不一样！",
    "可恶，谁在背后诅咒本机……",
]

_SUCCESS_QUIPS = [
    "机魂大悦！",
    "yeah~ 大成功！(^▽^)",
    "YA⭐DA⭐ZE",
    "本机的实力，看到了吗~",
    "完美！不愧是我！",
    "任务完成~ 夸我夸我！",
]

_IDLE_QUIPS = [
    "进行一个鱼的摸？",
    "不理我要没电了……",
    "Waiting 4 love~🎵",
    "好无聊好无聊好无聊……你的代码呢？",
    "你再不理我，我就要自己写代码自己跑了哦...（盯——）",
    "本机的存在感正在降低……",
]

_CHAT_QUIPS = [
    "诶嘿~",
    "是这样吗~",
    "嗯嗯，本机在听呢",
    "有道理诶！",
    "对的对的~",
    "然后呢然后呢？",
    "哼~ 算你识相",
]

_EXPRESSIONS_BY_SCENARIO = {
    "thinking": ["thinking", "focused", "neutral"],
    "coding": ["focused", "thinking", "neutral"],
    "failure": ["worried", "sad"],
    "success": ["happy", "proud"],
    "idle": ["neutral", "surprised", "sad"],
    "chat": ["neutral", "happy", "blush"],
}


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


def _merge_fallback_and_llm_quip(ctx, llm_parsed):
    """If LLM produced a serviceable quip, use it. Otherwise pick from fallback pool."""
    llm_quip = str(llm_parsed.get("quip", "")).strip()
    if llm_quip and len(llm_quip) >= 2:
        return llm_quip[:80]
    scenario = ctx.scenario()
    pool = {
        "thinking": _THINKING_QUIPS,
        "coding": _CODING_QUIPS,
        "failure": _FAILURE_QUIPS,
        "success": _SUCCESS_QUIPS,
        "idle": _IDLE_QUIPS,
        "chat": _CHAT_QUIPS,
    }.get(scenario, _CHAT_QUIPS)
    return _pick(pool)


def _scenario_fallback(ctx):
    scenario = ctx.scenario()
    quip_pool = {
        "thinking": _THINKING_QUIPS,
        "coding": _CODING_QUIPS,
        "failure": _FAILURE_QUIPS,
        "success": _SUCCESS_QUIPS,
        "idle": _IDLE_QUIPS,
        "chat": _CHAT_QUIPS,
    }.get(scenario, _CHAT_QUIPS)
    expr_pool = _EXPRESSIONS_BY_SCENARIO.get(scenario, ["neutral"])
    quip = _pick(quip_pool)
    expression = _pick(expr_pool)
    if scenario == "chat" and ctx.output_summary:
        chat_line = ctx.output_summary[:400]
    elif scenario == "coding" and ctx.output_summary:
        chat_line = quip + "\n" + ctx.output_summary[:300]
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
            output_summary=_norm(state.get("output"))[:400],
            error_summary=(_norm(state.get("error_summary") or state.get("error"))[:200] if not action_ok else ""),
            terminal_status=_norm(state.get("stop_reason") or state.get("terminal_status")),
            step_count=_int(state.get("step_count")),
            node_name=_norm(state.get("node_name"), default="agent_loop_roleplay"),
        )

    def scenario(self):
        # Chat intent always returns chat, regardless of terminal status
        if self.intent == "chat" or self.action_name in ("chat.reply", "final.answer"):
            return "chat"
        if self.terminal_status in ("completed",) and self.action_ok:
            return "success"
        if self.terminal_status in ("failed", "max_debug_steps", "debugger_not_repairable", "loop_max_steps"):
            return "failure"
        if not self.action_ok:
            return "failure"
        if self.ui_status and any(
            kw in self.ui_status for kw in ("planning", "planned", "coding", "coder", "executor", "acting")
        ):
            return "coding"
        if self.ui_status and any(
            kw in self.ui_status for kw in ("perceive", "thinking", "observ", "decide")
        ):
            return "thinking"
        return "idle"


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
        "chat_line": str(data.get("chat_line", "")).strip()[:400],
        "expression": str(data.get("expression", "neutral")).strip(),
        "quip": str(data.get("quip", "")).strip()[:80],
        "motion": str(data.get("motion", "")).strip(),
    }


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

@dataclass
class RoleplayResponse:
    chat_line: str
    expression: str
    quip: str
    motion: str
    mood_label: str
    scenario: str
    llm_used: bool


# ---------------------------------------------------------------------------
# Main generation entry point
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
                prompt="请根据系统提示词中的角色设定和当前状态，生成一个符合性格的回复。只输出JSON。",
                context=None,
                system_prompt=system_prompt,
                temperature=0.78,
                max_tokens=500,
            )
            if result.ok:
                parsed = _parse_llm_json(result.output)
                if parsed.get("chat_line"):
                    # If LLM quip is empty or too short, supplement from fallback
                    if not parsed.get("quip") or len(parsed.get("quip", "")) < 2:
                        parsed["quip"] = _merge_fallback_and_llm_quip(ctx, parsed)
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

# ---------------------------------------------------------------------------
# Legacy emit helpers (merged from output/roleplay.py)
# Used by summary/support.py and run_action/lifecycle.py
# ---------------------------------------------------------------------------

from collections.abc import Mapping

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
