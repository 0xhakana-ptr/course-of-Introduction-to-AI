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

WORKFLOW_NODE_METADATA: dict[str, dict[str, str]] = {
    "perceive_node": {"label": "理解请求", "phase": "routing"},
    "plan_node": {"label": "规划动作", "phase": "routing"},
    "act_node": {"label": "执行动作", "phase": "tools"},
    "observe_node": {"label": "观察结果", "phase": "tools"},
    "decide_continue_node": {"label": "判断是否继续", "phase": "routing"},
    "finalize_node": {"label": "最终收口", "phase": "roleplay"},
    "failure_node": {"label": "失败收口", "phase": "fallback"},
    "roleplay_node": {"label": "角色收口", "phase": "roleplay"},
    "diagnostics_preview": {"label": "诊断预览", "phase": "diagnostics"},
}


RUN_TERMINAL_NODE_BY_STATUS: dict[str, str] = {
    "done": TASK_DONE_NODE,
    "failed": TASK_FAILED_NODE,
    "cancelled": TASK_CANCELLED_NODE,
}


def get_run_terminal_node_name(status: str, *, default: str = TASK_FAILED_NODE) -> str:
    return RUN_TERMINAL_NODE_BY_STATUS.get(str(status or "").strip(), default)


def get_workflow_node_metadata(node_name: str) -> dict[str, str]:
    normalized_node_name = str(node_name or "").strip()
    return WORKFLOW_NODE_METADATA.get(
        normalized_node_name,
        {
            "label": normalized_node_name or "未知节点",
            "phase": "unknown",
        },
    )
