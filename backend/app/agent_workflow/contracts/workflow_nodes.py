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
    "router": {"label": "意图路由", "phase": "routing"},
    "chat_node": {"label": "聊天回复", "phase": "chat"},
    "coding_node": {"label": "代码任务预处理", "phase": "coding"},
    "workspace_tool_node": {"label": "工作区工具", "phase": "tools"},
    "run_tool_node": {"label": "任务创建", "phase": "run_create"},
    "run_snapshot_node": {"label": "任务读取", "phase": "run_read"},
    "run_control_node": {"label": "任务控制", "phase": "run_control"},
    "unknown_node": {"label": "未知意图收口", "phase": "fallback"},
    "roleplay_node": {"label": "角色收口", "phase": "roleplay"},
    # Tri-layer isolation mapping (keep node names stable for tests & frontend).
    # Layer 1: Intent Router
    "perceive_node": {"label": "Intent Router（意图路由）", "phase": "routing"},
    # Layer 3: Coding Workflow (PM/Coder/QA/Debugger)
    "plan_node": {"label": "PM（任务规划）", "phase": "coding"},
    "act_node": {"label": "Coder/Executor（执行）", "phase": "coding"},
    "observe_node": {"label": "QA（结果过滤）", "phase": "coding"},
    "decide_continue_node": {"label": "Debugger（决定继续）", "phase": "coding"},
    # Layer 2: Roleplay(UI)
    "finalize_node": {"label": "Roleplay(UI)（收口输出）", "phase": "roleplay"},
    "failure_node": {"label": "失败收口", "phase": "fallback"},
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
