from collections.abc import Mapping

from .workflow_nodes import get_workflow_node_metadata


def build_failure_descriptor(
    *,
    error_type: str,
    failure_event: str | None,
    failure_phase: str,
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

    descriptor_by_event = {
        "llm_response_failed": {
            "summary": "聊天节点返回了失败结果。",
            "error_code": "CHAT_LLM_RESPONSE_FAILED",
            "failure_domain": "llm",
        },
        "workspace_tool_failed": {
            "summary": "工作区工具执行失败。",
            "error_code": "WORKSPACE_TOOL_FAILED",
            "failure_domain": "workspace_tool",
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


def build_trace_event_label(event: str) -> str:
    return {
        "intent_routed": "意图已路由",
        "llm_response_ready": "聊天回复完成",
        "llm_response_failed": "聊天回复失败",
        "coding_request_prepared": "代码任务请求已解析",
        "workspace_tool_applied": "工作区工具已执行",
        "workspace_tool_failed": "工作区工具失败",
        "workspace_tool_skipped": "工作区工具已跳过",
        "run_created": "代码任务已创建",
        "run_create_failed": "代码任务创建失败",
        "run_snapshot_ready": "任务快照已读取",
        "run_snapshot_in_progress": "任务仍在执行",
        "run_snapshot_terminal": "任务已到终态",
        "run_snapshot_failed": "任务快照读取失败",
        "run_control_done": "任务控制已完成",
        "run_control_failed": "任务控制失败",
        "unknown_intent_done": "未知意图已收口",
        "roleplay_emit": "角色收口已发送",
        "route_selected": "诊断路由已确定",
        "coding_path_selected": "诊断 coding 路径已确定",
        "node_exception": "节点异常",
    }.get(event, event)


def build_trace_status_level(event: str) -> str:
    if "failed" in event or "exception" in event:
        return "error"
    if "skipped" in event:
        return "warning"
    return "info"


def build_trace_message(item: Mapping[str, object]) -> str | None:
    event = str(item.get("event") or "").strip()
    node = str(item.get("node") or "").strip()
    node_label = str(item.get("node_label") or node or "节点").strip()
    details = item.get("details")
    detail_map = details if isinstance(details, Mapping) else {}

    if event == "intent_routed":
        intent = str(detail_map.get("intent") or "unknown").strip()
        return f"{node_label}已将输入路由到 `{intent}` 意图。"
    if event == "llm_response_ready":
        return f"{node_label}已完成 LLM 回复生成。"
    if event == "llm_response_failed":
        return f"{node_label}返回了失败结果，请优先检查 LLM 配置和响应内容。"
    if event == "coding_request_prepared":
        run_action = str(detail_map.get("run_action") or "create").strip()
        target_run_id = str(detail_map.get("target_run_id") or "").strip()
        if target_run_id:
            return f"{node_label}已解析 coding 请求，动作为 `{run_action}`，目标 run_id 为 `{target_run_id}`。"
        return f"{node_label}已解析 coding 请求，动作为 `{run_action}`。"
    if event == "workspace_tool_applied":
        tool_name = str(detail_map.get("tool_name") or "unknown").strip()
        return f"{node_label}已执行工作区工具 `{tool_name}` 并补充上下文。"
    if event == "workspace_tool_failed":
        tool_name = str(detail_map.get("tool_name") or "unknown").strip()
        return f"{node_label}执行工作区工具 `{tool_name}` 时失败。"
    if event == "workspace_tool_skipped":
        return f"{node_label}当前未选择工作区工具，直接进入后续流程。"
    if event == "run_created":
        run_id = str(detail_map.get("run_id") or "").strip()
        status = str(detail_map.get("status") or "").strip()
        return f"{node_label}已创建代码任务 `{run_id}`，当前状态为 `{status}`。"
    if event == "run_create_failed":
        return f"{node_label}创建代码任务失败。"
    if event == "run_snapshot_ready":
        run_id = str(detail_map.get("run_id") or "").strip()
        status = str(detail_map.get("status") or "").strip()
        return f"{node_label}已读取任务 `{run_id}` 的快照，状态为 `{status}`。"
    if event == "run_snapshot_in_progress":
        run_id = str(detail_map.get("run_id") or "").strip()
        status = str(detail_map.get("status") or "").strip()
        return f"{node_label}确认任务 `{run_id}` 仍处于 `{status}` 中间态。"
    if event == "run_snapshot_terminal":
        run_id = str(detail_map.get("run_id") or "").strip()
        status = str(detail_map.get("status") or "").strip()
        return f"{node_label}确认任务 `{run_id}` 已进入 `{status}` 终态。"
    if event == "run_snapshot_failed":
        return f"{node_label}读取代码任务快照失败。"
    if event == "run_control_done":
        action = str(detail_map.get("action") or "control").strip()
        run_id = str(detail_map.get("run_id") or "").strip()
        status = str(detail_map.get("status") or "").strip()
        return f"{node_label}已完成 `{action}` 控制动作，任务 `{run_id}` 当前状态为 `{status}`。"
    if event == "run_control_failed":
        action = str(detail_map.get("action") or "control").strip()
        return f"{node_label}执行 `{action}` 控制动作失败。"
    if event == "unknown_intent_done":
        return f"{node_label}已按未知意图生成引导回复。"
    if event == "roleplay_emit":
        return f"{node_label}已完成最终输出收口。"
    if event == "route_selected":
        selected_route = str(detail_map.get("selected_route") or "").strip()
        return f"诊断预览已确认当前输入会进入 `{selected_route}`。"
    if event == "coding_path_selected":
        next_node = str(detail_map.get("next_node") or "").strip()
        run_action = str(detail_map.get("run_action") or "").strip()
        if run_action:
            return f"诊断预览已确认 coding 分支后续节点为 `{next_node}`，动作为 `{run_action}`。"
        return f"诊断预览已确认 coding 分支后续节点为 `{next_node}`。"
    if event == "node_exception":
        error_type = str(detail_map.get("error_type") or "Exception").strip()
        return f"{node_label}抛出了未捕获异常 `{error_type}`。"
    return None


def enrich_trace_item(item: Mapping[str, object]) -> dict[str, object]:
    enriched_item = dict(item)
    metadata = get_workflow_node_metadata(str(item.get("node") or ""))
    enriched_item["node_label"] = metadata.get("label")
    enriched_item["phase"] = metadata.get("phase")
    event = str(item.get("event") or "").strip()
    enriched_item["event_label"] = build_trace_event_label(event)
    enriched_item["status_level"] = build_trace_status_level(event)
    enriched_item["message"] = build_trace_message(enriched_item)
    return enriched_item


def normalize_trace_items(trace_items: list[Mapping[str, object]] | None) -> list[dict[str, object]]:
    if not isinstance(trace_items, list):
        return []
    return [
        enrich_trace_item(item)
        for item in trace_items
        if isinstance(item, Mapping)
    ]


def trace_items_from_state(state: Mapping[str, object]) -> list[dict[str, object]]:
    return normalize_trace_items(state.get("workflow_trace"))


def find_failure_trace(trace_items: list[dict[str, object]]) -> dict[str, object] | None:
    for item in reversed(trace_items):
        event = str(item.get("event") or "").strip()
        details = item.get("details")
        has_error = bool(
            isinstance(details, Mapping)
            and (details.get("has_error") or details.get("error"))
        )
        if "failed" in event or "exception" in event or has_error:
            return item
    return None
