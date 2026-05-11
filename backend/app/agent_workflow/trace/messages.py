from collections.abc import Mapping


TRACE_EVENT_LABELS: dict[str, str] = {
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
    "loop_perceived": "Loop 已理解请求",
    "loop_planned": "Loop 已规划动作",
    "loop_action_executed": "Loop 动作已执行",
    "loop_action_failed": "Loop 动作执行失败",
    "loop_observed": "Loop 已观察结果",
    "loop_decided": "Loop 已判断去向",
    "loop_finalized": "Loop 已收口",
    "loop_failed": "Loop 执行失败",
    "node_exception": "节点异常",
}


def build_trace_event_label(event: str) -> str:
    return TRACE_EVENT_LABELS.get(event, event)


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
        tool_name = str(detail_map.get("workspace_tool_name") or "").strip()
        tool_title = str(detail_map.get("workspace_tool_title") or "").strip()
        tool_category = str(detail_map.get("workspace_tool_category") or "").strip()
        tool_output_kind = str(detail_map.get("workspace_tool_output_kind") or "").strip()
        if target_run_id:
            return f"{node_label}已解析 coding 请求，动作为 `{run_action}`，目标 run_id 为 `{target_run_id}`。"
        if tool_name:
            tool_text = f"`{tool_name}`"
            if tool_title:
                tool_text += f"（{tool_title}）"
            if tool_category and tool_output_kind:
                tool_text += f"，类别 `{tool_category}`，输出 `{tool_output_kind}`"
            return f"{node_label}已解析 coding 请求，动作为 `{run_action}`，并规划工作区工具 {tool_text}。"
        return f"{node_label}已解析 coding 请求，动作为 `{run_action}`。"
    if event == "workspace_tool_applied":
        tool_name = str(detail_map.get("tool_name") or "unknown").strip()
        tool_title = str(detail_map.get("tool_title") or "").strip()
        tool_category = str(detail_map.get("tool_category") or "").strip()
        tool_output_kind = str(detail_map.get("tool_output_kind") or "").strip()
        tool_text = f"`{tool_name}`"
        if tool_title:
            tool_text += f"（{tool_title}）"
        if tool_category and tool_output_kind:
            return (
                f"{node_label}已执行工作区工具 {tool_text}，"
                f"类别为 `{tool_category}`，输出为 `{tool_output_kind}`，并补充上下文。"
            )
        return f"{node_label}已执行工作区工具 {tool_text} 并补充上下文。"
    if event == "workspace_tool_failed":
        tool_name = str(detail_map.get("tool_name") or "unknown").strip()
        tool_title = str(detail_map.get("tool_title") or "").strip()
        tool_error_code = str(detail_map.get("tool_error_code") or "").strip()
        tool_text = f"`{tool_name}`"
        if tool_title:
            tool_text += f"（{tool_title}）"
        if tool_error_code:
            return f"{node_label}执行工作区工具 {tool_text} 时失败，错误码为 `{tool_error_code}`。"
        return f"{node_label}执行工作区工具 {tool_text} 时失败。"
    if event == "workspace_tool_skipped":
        reason = str(detail_map.get("reason") or "").strip()
        if reason:
            return f"{node_label}当前跳过工作区工具，原因：{reason}"
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
    if event == "loop_perceived":
        intent = str(detail_map.get("intent") or "unknown").strip()
        return f"{node_label}已将输入理解为 `{intent}` 意图。"
    if event == "loop_planned":
        action_name = str(detail_map.get("action_name") or "unknown").strip()
        return f"{node_label}已选择下一步动作 `{action_name}`。"
    if event == "loop_action_executed":
        action_name = str(detail_map.get("action_name") or "unknown").strip()
        return f"{node_label}已完成动作 `{action_name}`。"
    if event == "loop_action_failed":
        action_name = str(detail_map.get("action_name") or "unknown").strip()
        return f"{node_label}执行动作 `{action_name}` 失败。"
    if event == "loop_observed":
        action_name = str(detail_map.get("action_name") or "unknown").strip()
        ok = bool(detail_map.get("ok"))
        return f"{node_label}已观察 `{action_name}` 的执行结果，成功状态为 `{ok}`。"
    if event == "loop_decided":
        stop_reason = str(detail_map.get("stop_reason") or "unknown").strip()
        will_replan = bool(detail_map.get("will_replan"))
        if will_replan:
            return f"{node_label}决定继续规划，原因 `{stop_reason}`。"
        return f"{node_label}决定结束本轮，原因 `{stop_reason}`。"
    if event == "loop_finalized":
        stop_reason = str(detail_map.get("stop_reason") or "completed").strip()
        return f"{node_label}已完成本轮收口，原因 `{stop_reason}`。"
    if event == "loop_failed":
        return f"{node_label}确认 Agent Loop 执行失败。"
    if event == "node_exception":
        error_type = str(detail_map.get("error_type") or "Exception").strip()
        return f"{node_label}抛出了未捕获异常 `{error_type}`。"
    return None
