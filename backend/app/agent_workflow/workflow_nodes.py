AGENT_ROLEPLAY_NODE = "agent_roleplay"

CHAT_NODE = "chat"
CHAT_DONE_NODE = "chat_done"
CHAT_ERROR_NODE = "chat_error"

TASK_QUEUED_NODE = "task_queued"
TASK_STARTED_NODE = "task_started"
TASK_REPAIRING_NODE = "task_repairing"
TASK_DONE_NODE = "task_done"
TASK_FAILED_NODE = "task_failed"
TASK_CANCELLED_NODE = "task_cancelled"

TASK_RETRY_DONE_NODE = "task_retry_done"
TASK_RETRY_CANCELLED_NODE = "task_retry_cancelled"
TASK_RETRY_CANCELLED_REQUESTED_NODE = "task_retry_cancelled_requested"
TASK_RETRY_FAILED_NODE = "task_retry_failed"
TASK_RETRY_REPAIRING_NODE = "task_retry_repairing"


RUN_TERMINAL_NODE_BY_STATUS: dict[str, str] = {
    "done": TASK_DONE_NODE,
    "failed": TASK_FAILED_NODE,
    "cancelled": TASK_CANCELLED_NODE,
}


def get_run_terminal_node_name(status: str, *, default: str = TASK_FAILED_NODE) -> str:
    return RUN_TERMINAL_NODE_BY_STATUS.get(str(status or "").strip(), default)
