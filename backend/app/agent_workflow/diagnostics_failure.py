from collections.abc import Mapping

from ..tools.workspace_tools import (
    WORKSPACE_TOOL_ERROR_EXECUTION_FAILED,
    WORKSPACE_TOOL_ERROR_UNREGISTERED,
)


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_failure_descriptor(
    *,
    error_type: str,
    failure_event: str | None,
    failure_phase: str,
    failure_details: Mapping[str, object] | None = None,
) -> dict[str, str]:
    if error_type == "blocked":
        return {
            "summary": "诊断已拦截：当前输入会进入可能产生副作用的运行路径。",
            "error_code": "DIAGNOSTICS_BLOCKED_SIDE_EFFECT",
            "failure_domain": "diagnostics_guard",
        }

    if failure_event == "node_exception":
        return {
            "summary": "工作流节点抛出了未捕获异常。",
            "error_code": "WORKFLOW_NODE_EXCEPTION",
            "failure_domain": "workflow_node",
        }

    if failure_event == "workspace_tool_failed":
        tool_error_code = _normalize_optional_text(
            failure_details.get("tool_error_code")
            if isinstance(failure_details, Mapping)
            else None
        )
        tool_name = _normalize_optional_text(
            failure_details.get("tool_name")
            if isinstance(failure_details, Mapping)
            else None
        )
        tool_title = _normalize_optional_text(
            failure_details.get("tool_title")
            if isinstance(failure_details, Mapping)
            else None
        )
        tool_label = tool_title or tool_name or "工作区工具"
        if tool_error_code == WORKSPACE_TOOL_ERROR_UNREGISTERED:
            return {
                "summary": f"{tool_label}未注册，无法执行当前工具规划。",
                "error_code": WORKSPACE_TOOL_ERROR_UNREGISTERED,
                "failure_domain": "workspace_tool_registry",
            }
        if tool_error_code == WORKSPACE_TOOL_ERROR_EXECUTION_FAILED:
            return {
                "summary": f"{tool_label}执行失败。",
                "error_code": WORKSPACE_TOOL_ERROR_EXECUTION_FAILED,
                "failure_domain": "workspace_tool_execution",
            }
        return {
            "summary": f"{tool_label}执行失败。",
            "error_code": "WORKSPACE_TOOL_FAILED",
            "failure_domain": "workspace_tool",
        }

    descriptor_by_event = {
        "llm_response_failed": {
            "summary": "聊天节点返回了失败结果。",
            "error_code": "CHAT_LLM_RESPONSE_FAILED",
            "failure_domain": "llm",
        },
        "run_create_failed": {
            "summary": "代码任务创建失败。",
            "error_code": "RUN_CREATE_FAILED",
            "failure_domain": "run_service",
        },
        "run_snapshot_failed": {
            "summary": "代码任务快照读取失败。",
            "error_code": "RUN_SNAPSHOT_FAILED",
            "failure_domain": "run_service",
        },
        "run_control_failed": {
            "summary": "代码任务控制动作执行失败。",
            "error_code": "RUN_CONTROL_FAILED",
            "failure_domain": "run_service",
        },
    }
    if failure_event in descriptor_by_event:
        return descriptor_by_event[failure_event]

    descriptor_by_phase = {
        "routing": {
            "summary": "工作流路由阶段出现异常。",
            "error_code": "WORKFLOW_ROUTING_FAILED",
            "failure_domain": "workflow",
        },
        "chat": {
            "summary": "聊天阶段执行失败。",
            "error_code": "WORKFLOW_CHAT_FAILED",
            "failure_domain": "workflow",
        },
        "coding": {
            "summary": "代码任务预处理阶段执行失败。",
            "error_code": "WORKFLOW_CODING_FAILED",
            "failure_domain": "workflow",
        },
        "tools": {
            "summary": "工作区工具阶段执行失败。",
            "error_code": "WORKFLOW_TOOLS_FAILED",
            "failure_domain": "workflow",
        },
        "run_create": {
            "summary": "代码任务创建阶段执行失败。",
            "error_code": "WORKFLOW_RUN_CREATE_FAILED",
            "failure_domain": "workflow",
        },
        "run_read": {
            "summary": "代码任务读取阶段执行失败。",
            "error_code": "WORKFLOW_RUN_READ_FAILED",
            "failure_domain": "workflow",
        },
        "run_control": {
            "summary": "代码任务控制阶段执行失败。",
            "error_code": "WORKFLOW_RUN_CONTROL_FAILED",
            "failure_domain": "workflow",
        },
        "roleplay": {
            "summary": "角色收口阶段执行失败。",
            "error_code": "WORKFLOW_ROLEPLAY_FAILED",
            "failure_domain": "workflow",
        },
        "diagnostics": {
            "summary": "诊断阶段执行失败。",
            "error_code": "WORKFLOW_DIAGNOSTICS_FAILED",
            "failure_domain": "workflow",
        },
    }
    return descriptor_by_phase.get(
        failure_phase,
        {
            "summary": "工作流执行失败，需要结合 trace 继续定位。",
            "error_code": "WORKFLOW_FAILURE",
            "failure_domain": "workflow",
        },
    )
