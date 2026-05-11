import logging
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


WORKFLOW_NODE_EVENTS: dict[str, WorkflowNodeEvent] = {
    "router": WorkflowNodeEvent(
        node_name="router",
        quip="我先判断一下该怎么处理。",
        progress=3,
    ),
    "chat_node": WorkflowNodeEvent(
        node_name="chat_node",
        quip="我正在组织回复。",
        progress=15,
    ),
    "coding_node": WorkflowNodeEvent(
        node_name="coding_node",
        quip="我在分析这个任务。",
        progress=15,
    ),
    "workspace_tool_node": WorkflowNodeEvent(
        node_name="workspace_tool_node",
        quip="我先查看一下项目上下文。",
        progress=30,
    ),
    "run_tool_node": WorkflowNodeEvent(
        node_name="run_tool_node",
        quip="我准备创建并执行任务。",
        progress=45,
    ),
    "run_snapshot_node": WorkflowNodeEvent(
        node_name="run_snapshot_node",
        quip="我在读取任务状态。",
        progress=40,
    ),
    "run_control_node": WorkflowNodeEvent(
        node_name="run_control_node",
        quip="我在处理任务控制请求。",
        progress=40,
    ),
    "unknown_node": WorkflowNodeEvent(
        node_name="unknown_node",
        quip="我需要先把这句话整理清楚。",
        progress=80,
    ),
    "roleplay_node": WorkflowNodeEvent(
        node_name="roleplay_node",
        quip="我整理一下结果再告诉你。",
        progress=90,
    ),
    "perceive_node": WorkflowNodeEvent(
        node_name="perceive_node",
        quip="我先理解你的目标。",
        progress=8,
    ),
    "plan_node": WorkflowNodeEvent(
        node_name="plan_node",
        quip="我在决定下一步怎么做。",
        progress=20,
    ),
    "act_node": WorkflowNodeEvent(
        node_name="act_node",
        quip="我开始执行选定的动作。",
        progress=45,
    ),
    "observe_node": WorkflowNodeEvent(
        node_name="observe_node",
        quip="我在确认执行结果。",
        progress=70,
    ),
    "decide_continue_node": WorkflowNodeEvent(
        node_name="decide_continue_node",
        quip="我判断一下是否还要继续。",
        progress=82,
    ),
    "finalize_node": WorkflowNodeEvent(
        node_name="finalize_node",
        quip="我整理最终回复。",
        progress=92,
    ),
    "failure_node": WorkflowNodeEvent(
        node_name="failure_node",
        quip="这一步遇到了问题，我先收口说明。",
        progress=95,
        status="error",
    ),
}


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
        metadata = get_workflow_node_metadata(node_name)
        label = metadata.get("label") or node_name
        event = WorkflowNodeEvent(
            node_name=node_name,
            quip=f"我进入了{label}节点。",
            progress=5,
        )

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
        return quip_ok and status_ok
    except Exception:
        logger.exception("Failed to emit workflow node-entered event: node=%s", node_name)
        return False
