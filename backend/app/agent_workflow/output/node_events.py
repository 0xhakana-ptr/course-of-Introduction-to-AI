import logging
import random
import time
import dataclasses
from dataclasses import dataclass
from typing import Literal

from ...messaging.event_types import AGENT_EVENT_STAGE
from ...messaging.message_sender import message_sender
from ...schemas import MESSAGE_STATUS
from ..contracts.workflow_nodes import get_workflow_node_metadata

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WorkflowNodeEvent:
    node_name: str
    quip: str
    progress: int
    status: MESSAGE_STATUS = "running"
    priority: Literal["low", "medium", "high"] = "medium"
    duration: int = 2200


# ============================================================================
# Character Quip Pools (Shion persona: cute, witty, chuunibyou, slight yandere)
# Each pool maps to one or more workflow nodes.  Node handler picks randomly.
# ============================================================================

_PERCEIVE_QUIPS = [
    "嗯哼~",
    "让本机看看你在说什么...",
    "感知灵能波动——",
    "捕获到信号了...",
    "正在读取信息流",
    "哦~ 有新消息！",
]

_PLAN_QUIPS = [
    "让本机想想怎么搞~",
    "制定计划中 (推眼镜)",
    "魔导书翻到第几页了？",
    "战术规划完成——",
    "嗯...来个完美的方案！",
]

_ACT_QUIPS = [
    "开始执行！——",
    "魔法注入中(≧▽≦)",
    "代码正在跳舞中——",
    "交给我吧！",
    "看我操作~",
]

_OBSERVE_QUIPS = [
    "让我观察一下结果...",
    "正在分析输出~",
    "嗯...有意思",
    "检查完毕！",
    "数据读取完成...",
]

_DECIDE_QUIPS = [
    "判断中...",
    "做出决定了——",
    "嗯...下一步...",
    "就这么定了！",
]

_FINALIZE_QUIPS = [
    "大功告成(^▽^)/",
    "收工咯~ 准备汇报",
    "一切尘埃落定啦",
    "呼~ 本机真是天才！",
    "任务完美收官的说！",
]

_FAILURE_QUIPS = [
    "呜...出了点小问题 QAQ",
    "机魂不悦...",
    "失败乃成功之母啦",
    "呜...你什么都没看到 (￣▽￣*)",
    "不许笑本机！——",
]

_ROLEPLAY_QUIPS = [
    "正在组织语言...",
    "让本机想想怎么回复~",
    "唔~ 这样啊",
    "嗯哼... 有道理呢",
]

_CODING_START_QUIPS = [
    "编码模式启动！——",
    "让本机看看你的需求...",
    "准备写代码咯——",
    "交给我来搞定！",
]

_CODING_PM_QUIPS = [
    "分析需求中~",
    "拆分任务... 嗯",
    "做个详细计划先",
]

_CODING_CODER_QUIPS = [
    "开始写代码！",
    "敲敲... 键盘要冒烟了",
    "这段逻辑... 有点意思",
]

_CODING_EXECUTOR_QUIPS = [
    "运行中... 千万别报错",
    "执行完成！",
    "来看结果如何？",
]

_CODING_QA_QUIPS = [
    "检查代码质量...",
    "嗯... 这里改改...",
    "QA 环节不能马虎！",
]

_CODING_DEBUGGER_QUIPS = [
    "又报错了啊啊啊(╯°□°)╯",
    "Bug 给我现形！",
    "调试中... 耐心... 深呼吸...",
]

_CODING_FINISH_QUIPS = [
    "所有任务全部搞定！ (双手合十)",
    "代码写得漂亮吧~",
    "不愧是本机的作品！满分！",
]

_CODING_FAILURE_QUIPS = [
    "啊...又失败了...",
    "这个bug有点难缠...再来一次",
    "本机... 还需要更强...",
]

# Idle quips -- fired when no node activity for a while
_IDLE_QUIPS = [
    "进行一个鱼的摸",
    "你再不理我就没电了...",
    "唔~",
    "好无聊好无聊",
    "有人吗——",
    "本机... 在等你哦",
    "盯—— (暗中观察)",
    "哼~ 终于来了",
    "存在感正在降低中",
    "再不找我说话我就自己写代码去了...",
]

# ---- Node -> Pool mapping ----
_NODE_QUIP_POOL: dict[str, list[str]] = {
    "perceive_node": _PERCEIVE_QUIPS,
    "plan_node": _PLAN_QUIPS,
    "act_node": _ACT_QUIPS,
    "observe_node": _OBSERVE_QUIPS,
    "decide_continue_node": _DECIDE_QUIPS,
    "finalize_node": _FINALIZE_QUIPS,
    "failure_node": _FAILURE_QUIPS,
    "roleplay_node": _ROLEPLAY_QUIPS,
    "coding_start_node": _CODING_START_QUIPS,
    "pm_node": _CODING_PM_QUIPS,
    "coder_node": _CODING_CODER_QUIPS,
    "executor_node": _CODING_EXECUTOR_QUIPS,
    "qa_node": _CODING_QA_QUIPS,
    "debugger_node": _CODING_DEBUGGER_QUIPS,
    "coding_finish_node": _CODING_FINISH_QUIPS,
    "coding_failure_node": _CODING_FAILURE_QUIPS,
    "agent_loop_roleplay": _ROLEPLAY_QUIPS,
    "agent_loop_failure": _FAILURE_QUIPS,
}

# ---- Backward-compat WORKFLOW_NODE_EVENTS (kept for existing consumers) ----
# These are now populated from pools; the quip field is set at emit time.
WORKFLOW_NODE_EVENTS: dict[str, WorkflowNodeEvent] = {
    name: WorkflowNodeEvent(
        node_name=name,
        quip="",  # filled at emit time
        progress=prog,
        status="error" if name in ("failure_node", "coding_failure_node", "agent_loop_failure") else "running",
    )
    for name, prog in [
        ("perceive_node", 8),
        ("plan_node", 20),
        ("act_node", 45),
        ("observe_node", 70),
        ("decide_continue_node", 82),
        ("finalize_node", 92),
        ("failure_node", 95),
        ("roleplay_node", 90),
        ("coding_start_node", 30),
        ("pm_node", 34),
        ("coder_node", 38),
        ("executor_node", 52),
        ("qa_node", 64),
        ("debugger_node", 72),
        ("coding_finish_node", 86),
        ("coding_failure_node", 86),
        ("agent_loop_roleplay", 94),
        ("agent_loop_failure", 96),
    ]
}


# ---- Idle quip last-emit timestamp (module-level) ----
_last_quip_ts: float = 0.0
IDLE_QUIP_COOLDOWN_S = 12.0  # fire idle quip after 12s of silence


def _pick_quip(pool: list[str]) -> str:
    """Pick a random quip from a pool."""
    return random.choice(pool)


def pick_idle_quip() -> str:
    """Return a random idle quip.  Caller should send it via message_sender."""
    return _pick_quip(_IDLE_QUIPS)


def emit_idle_quip_if_due() -> bool:
    """Send an idle quip if enough time has passed since the last one.

    Returns True if a quip was sent.
    """
    global _last_quip_ts
    now = time.time()
    if now - _last_quip_ts < IDLE_QUIP_COOLDOWN_S:
        return False
    quip = pick_idle_quip()
    ok = message_sender.send_quip(
        quip,
        node_name="idle",
        priority="low",
        duration=3500,
        metadata={"event_type": "idle.quip", "event_source": "idle"},
    )
    if ok:
        _last_quip_ts = now
    return ok


def _node_event_metadata(node_name: str) -> dict[str, object]:
    metadata = get_workflow_node_metadata(node_name)
    return {
        "node_label": metadata.get("label"),
        "phase": metadata.get("phase"),
        "runtime_event": "node_entered",
    }


def _node_event_stage(node_name: str) -> AGENT_EVENT_STAGE:
    phase = str(get_workflow_node_metadata(node_name).get("phase") or "unknown")
    allowed_stages = {
        "routing",
        "chat",
        "coding",
        "tools",
        "run_create",
        "run_read",
        "run_control",
        "run",
        "repair",
        "fallback",
        "roleplay",
        "diagnostics",
        "unknown",
        "system",
    }
    if phase in allowed_stages:
        return phase  # type: ignore[return-value]
    return "unknown"


def should_emit_workflow_node_events(state: object) -> bool:
    if not isinstance(state, dict):
        return False
    return bool(state.get("emit_node_events", True))


def emit_workflow_node_entered(state: object, node_name: str) -> bool:
    if not should_emit_workflow_node_events(state):
        return False

    event = WORKFLOW_NODE_EVENTS.get(node_name)
    if event is None:
        # Unknown node -- pick a generic idle-style quip
        quip = _pick_quip(_IDLE_QUIPS)
        event = WorkflowNodeEvent(node_name=node_name, quip=quip, progress=5)
    else:
        # Pick randomly from the node's quip pool
        pool = _NODE_QUIP_POOL.get(node_name)
        if pool:
            quip = _pick_quip(pool)
            event = dataclasses.replace(event, quip=quip)

    stage = _node_event_stage(node_name)
    metadata = _node_event_metadata(node_name)
    try:
        quip_ok = message_sender.send_quip(
            event.quip,
            node_name=event.node_name,
            priority=event.priority,
            duration=event.duration,
            metadata=metadata,
            event_type="workflow.node_entered",
            event_source="workflow",
            event_stage=stage,
        )
        status_ok = message_sender.send_status(
            event.status,
            progress=event.progress,
            node_name=event.node_name,
            metadata=metadata,
            event_type="workflow.node_entered",
            event_source="workflow",
            event_stage=stage,
        )
        if quip_ok:
            global _last_quip_ts
            _last_quip_ts = time.time()
        return quip_ok and status_ok
    except Exception:
        logger.exception("Failed to emit workflow node-entered event: node=%s", node_name)
        return False
