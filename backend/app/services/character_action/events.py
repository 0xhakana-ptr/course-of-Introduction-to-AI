from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CharacterEvent:
    node_name: str
    quip: str | None = None
    expression: str | None = None
    motion: str | None = None
    status: str | None = None
    progress: int | None = None
    priority: str = "medium"
    duration: int = 3000


CHAT_STARTED_EVENT = CharacterEvent(
    node_name="chat",
    quip="我想一下。",
    expression="thinking",
    status="running",
    progress=5,
)

CHAT_DONE_EVENT = CharacterEvent(
    node_name="chat_done",
    quip="我想好了。",
    expression="happy",
    status="done",
    progress=100,
)

CHAT_FAILED_EVENT = CharacterEvent(
    node_name="chat_error",
    quip="这次回复遇到了一点问题。",
    expression="worried",
    status="error",
)

TASK_QUEUED_EVENT = CharacterEvent(
    node_name="task_queued",
    quip="任务已经排队。",
    expression="thinking",
    status="running",
    progress=0,
)

TASK_STARTED_EVENT = CharacterEvent(
    node_name="task_started",
    quip="任务开始执行。",
    expression="coding",
    status="running",
    progress=10,
)

TASK_REPAIRING_EVENT = CharacterEvent(
    node_name="task_repairing",
    quip="我在尝试修复刚才的问题。",
    expression="worried",
    status="running",
    progress=70,
)

TASK_DONE_EVENT = CharacterEvent(
    node_name="task_done",
    quip="任务完成了。",
    expression="happy",
    status="done",
    progress=100,
)

TASK_FAILED_EVENT = CharacterEvent(
    node_name="task_failed",
    quip="任务执行失败了。",
    expression="sad",
    status="error",
)

TASK_CANCELLED_EVENT = CharacterEvent(
    node_name="task_cancelled",
    quip="任务已经取消。",
    expression="thinking",
    status="cancelled",
)
