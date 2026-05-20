from ..messaging.message_sender import message_sender
# ---- Character event definitions (merged from character_action/events.py) ----
from dataclasses import dataclass

from ..agent_workflow.contracts.workflow_nodes import (
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
from ..messaging.event_types import AGENT_EVENT_SOURCE, AGENT_EVENT_STAGE, AGENT_EVENT_TYPE
from ..schemas import MESSAGE_STATUS


@dataclass(frozen=True, slots=True)
class CharacterEvent:
    node_name: str
    event_type: AGENT_EVENT_TYPE
    event_source: AGENT_EVENT_SOURCE
    event_stage: AGENT_EVENT_STAGE
    quip: str | None = None
    expression: str | None = None
    motion: str | None = None
    status: MESSAGE_STATUS | None = None
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

CHARACTER_EVENTS: tuple[CharacterEvent, ...] = (
    CHAT_STARTED_EVENT,
    CHAT_DONE_EVENT,
    CHAT_FAILED_EVENT,
    TASK_QUEUED_EVENT,
    TASK_STARTED_EVENT,
    TASK_REPAIRING_EVENT,
    TASK_DONE_EVENT,
    TASK_FAILED_EVENT,
    TASK_CANCELLED_EVENT,
)

# ---- End merged events ----



def dispatch_character_event(event: CharacterEvent) -> bool:
    results: list[bool] = []
    if event.quip:
        results.append(
            message_sender.send_quip(
                content=event.quip,
                node_name=event.node_name,
                priority=event.priority,
                duration=event.duration,
                event_type=event.event_type,
                event_source=event.event_source,
                event_stage=event.event_stage,
            )
        )
    if event.expression:
        results.append(
            message_sender.send_expression(
                expression=event.expression,
                node_name=event.node_name,
                duration=event.duration,
                mode="set",
                event_type=event.event_type,
                event_source=event.event_source,
                event_stage=event.event_stage,
            )
        )
    if event.motion:
        results.append(
            message_sender.send_motion(
                motion=event.motion,
                node_name=event.node_name,
                duration=event.duration,
                event_type=event.event_type,
                event_source=event.event_source,
                event_stage=event.event_stage,
            )
        )
    if event.status:
        results.append(
            message_sender.send_status(
                status=event.status,
                progress=event.progress,
                node_name=event.node_name,
                event_type=event.event_type,
                event_source=event.event_source,
                event_stage=event.event_stage,
            )
        )
    return all(results) if results else True


def send_chat_started() -> bool:
    return dispatch_character_event(CHAT_STARTED_EVENT)


def send_chat_done() -> bool:
    return dispatch_character_event(CHAT_DONE_EVENT)


def send_chat_failed() -> bool:
    return dispatch_character_event(CHAT_FAILED_EVENT)


def send_task_queued() -> bool:
    return dispatch_character_event(TASK_QUEUED_EVENT)


def send_task_started() -> bool:
    return dispatch_character_event(TASK_STARTED_EVENT)


def send_task_repairing() -> bool:
    return dispatch_character_event(TASK_REPAIRING_EVENT)


def send_task_done() -> bool:
    return dispatch_character_event(TASK_DONE_EVENT)


def send_task_failed() -> bool:
    return dispatch_character_event(TASK_FAILED_EVENT)


def send_task_cancelled() -> bool:
    return dispatch_character_event(TASK_CANCELLED_EVENT)
