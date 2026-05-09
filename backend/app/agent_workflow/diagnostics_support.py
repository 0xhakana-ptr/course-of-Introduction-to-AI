from collections.abc import Mapping
from dataclasses import dataclass

from ..schemas import AgentWorkflowRuntimeEventSummary
from ..tools.workspace_tool_models import WorkspaceToolDescriptor
from ..tools.workspace_tools import (
    get_workspace_tool_descriptor,
    normalize_workspace_tool_plan,
    WORKSPACE_TOOL_ERROR_EXECUTION_FAILED,
    WORKSPACE_TOOL_ERROR_UNREGISTERED,
)
from .trace_runtime import build_trace_runtime_event_fields
from .workflow_nodes import get_workflow_node_metadata


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(slots=True)
class WorkspaceToolSnapshot:
    name: str | None = None
    title: str | None = None
    reason: str | None = None
    category: str | None = None
    output_kind: str | None = None
    error_code: str | None = None
    descriptor: dict[str, object] | None = None
    plan: dict[str, object] | None = None

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "WorkspaceToolSnapshot":
        tool_name = _normalize_optional_text(state.get("workspace_tool_name"))
        descriptor_model = WorkspaceToolDescriptor.from_value(
            state.get("workspace_tool_descriptor")
        )
        if descriptor_model is None and tool_name is not None:
            descriptor_model = WorkspaceToolDescriptor.from_value(
                get_workspace_tool_descriptor(tool_name)
            )

        plan_model = normalize_workspace_tool_plan(state.get("workspace_tool_plan"))
        return cls(
            name=tool_name,
            title=descriptor_model.title if descriptor_model is not None else None,
            reason=_normalize_optional_text(state.get("workspace_tool_reason")),
            category=(
                _normalize_optional_text(state.get("workspace_tool_category"))
                or (descriptor_model.category if descriptor_model is not None else None)
            ),
            output_kind=(
                _normalize_optional_text(state.get("workspace_tool_output_kind"))
                or (descriptor_model.output_kind if descriptor_model is not None else None)
            ),
            error_code=_normalize_optional_text(state.get("workspace_tool_error_code")),
            descriptor=descriptor_model.as_dict() if descriptor_model is not None else None,
            plan=plan_model.as_dict() if plan_model is not None else None,
        )

    def merged_with(self, fallback: "WorkspaceToolSnapshot | None") -> "WorkspaceToolSnapshot":
        if fallback is None:
            return self
        return WorkspaceToolSnapshot(
            name=self.name or fallback.name,
            title=self.title or fallback.title,
            reason=self.reason or fallback.reason,
            category=self.category or fallback.category,
            output_kind=self.output_kind or fallback.output_kind,
            error_code=self.error_code or fallback.error_code,
            descriptor=self.descriptor or fallback.descriptor,
            plan=self.plan or fallback.plan,
        )


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
    runtime_fields = build_trace_runtime_event_fields(
        node=str(item.get("node") or ""),
        event=event,
        frontend_visible=bool(item.get("frontend_visible", False)),
    )
    for key, value in runtime_fields.items():
        if enriched_item.get(key) is None:
            enriched_item[key] = value
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


def build_runtime_event_summary(
    trace_items: list[dict[str, object]],
) -> AgentWorkflowRuntimeEventSummary:
    event_type_counts: dict[str, int] = {}
    event_source_counts: dict[str, int] = {}
    event_stage_counts: dict[str, int] = {}
    error_event_count = 0
    frontend_visible_count = 0

    for item in trace_items:
        event_type = _normalize_optional_text(item.get("event_type"))
        event_source = _normalize_optional_text(item.get("event_source"))
        event_stage = _normalize_optional_text(item.get("event_stage"))
        status_level = _normalize_optional_text(item.get("status_level"))
        frontend_visible = bool(item.get("frontend_visible"))

        if event_type is not None:
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        if event_source is not None:
            event_source_counts[event_source] = event_source_counts.get(event_source, 0) + 1
        if event_stage is not None:
            event_stage_counts[event_stage] = event_stage_counts.get(event_stage, 0) + 1
        if status_level == "error":
            error_event_count += 1
        if frontend_visible:
            frontend_visible_count += 1

    last_item = trace_items[-1] if trace_items else {}
    return AgentWorkflowRuntimeEventSummary(
        event_count=len(trace_items),
        error_event_count=error_event_count,
        frontend_visible_count=frontend_visible_count,
        last_event_type=_normalize_optional_text(last_item.get("event_type")),
        last_event_source=_normalize_optional_text(last_item.get("event_source")),
        last_event_stage=_normalize_optional_text(last_item.get("event_stage")),
        event_type_counts=event_type_counts,
        event_source_counts=event_source_counts,
        event_stage_counts=event_stage_counts,
    )
