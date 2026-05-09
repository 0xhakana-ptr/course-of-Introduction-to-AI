from dataclasses import dataclass

from ...agent_workflow.workflow_nodes import (
    CHAT_DONE_NODE,
    CHAT_ERROR_NODE,
    CHAT_NODE,
    TASK_CANCELLED_NODE,
    TASK_DONE_NODE,
    TASK_FAILED_NODE,
    TASK_QUEUED_NODE,
    TASK_REPAIRING_NODE,
    TASK_STARTED_NODE,
)
from ...messaging.event_types import AGENT_EVENT_SOURCE, AGENT_EVENT_STAGE, AGENT_EVENT_TYPE


@dataclass(frozen=True, slots=True)
class CharacterEvent:
    node_name: str
    event_type: AGENT_EVENT_TYPE
    event_source: AGENT_EVENT_SOURCE
    event_stage: AGENT_EVENT_STAGE
    quip: str | None = None
    expression: str | None = None
    motion: str | None = None
    status: str | None = None
    progress: int | None = None
    priority: str = "medium"
    duration: int = 3000


CHAT_STARTED_EVENT = CharacterEvent(
    node_name=CHAT_NODE,
    event_type="chat.started",
    event_source="chat",
    event_stage="chat",
    quip="我想一下。",
    expression="thinking",
    status="running",
    progress=5,
)

CHAT_DONE_EVENT = CharacterEvent(
    node_name=CHAT_DONE_NODE,
    event_type="chat.completed",
    event_source="chat",
    event_stage="chat",
    quip="我想好了。",
    expression="happy",
    status="done",
    progress=100,
)

CHAT_FAILED_EVENT = CharacterEvent(
    node_name=CHAT_ERROR_NODE,
    event_type="chat.failed",
    event_source="chat",
    event_stage="chat",
    quip="这次回复遇到了一点问题。",
    expression="worried",
    status="error",
)

TASK_QUEUED_EVENT = CharacterEvent(
    node_name=TASK_QUEUED_NODE,
    event_type="run.queued",
    event_source="run",
    event_stage="run",
    quip="任务已经排队。",
    expression="thinking",
    status="running",
    progress=0,
)

TASK_STARTED_EVENT = CharacterEvent(
    node_name=TASK_STARTED_NODE,
    event_type="run.started",
    event_source="run",
    event_stage="run",
    quip="任务开始执行。",
    expression="coding",
    status="running",
    progress=10,
)

TASK_REPAIRING_EVENT = CharacterEvent(
    node_name=TASK_REPAIRING_NODE,
    event_type="run.repair_started",
    event_source="run",
    event_stage="repair",
    quip="我在尝试修复刚才的问题。",
    expression="worried",
    status="running",
    progress=70,
)

TASK_DONE_EVENT = CharacterEvent(
    node_name=TASK_DONE_NODE,
    event_type="run.finished",
    event_source="run",
    event_stage="run",
    quip="任务完成了。",
    expression="happy",
    status="done",
    progress=100,
)

TASK_FAILED_EVENT = CharacterEvent(
    node_name=TASK_FAILED_NODE,
    event_type="run.failed",
    event_source="run",
    event_stage="run",
    quip="任务执行失败了。",
    expression="sad",
    status="error",
)

TASK_CANCELLED_EVENT = CharacterEvent(
    node_name=TASK_CANCELLED_NODE,
    event_type="run.cancelled",
    event_source="run",
    event_stage="run",
    quip="任务已经取消。",
    expression="thinking",
    status="cancelled",
)
