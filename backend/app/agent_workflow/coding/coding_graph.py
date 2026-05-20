from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath

import re
from langgraph.graph import END, StateGraph

from ..actions import default_action_registry
from ..utils.shared import coerce_bool, coerce_int, compact_text, normalize_text, safe_mapping
from ..contracts.workflow_results import invoke_graph_with_result
from ..output.node_events import emit_workflow_node_entered
from ..runtime.graph_nodes import register_agent_graph_nodes
from ..state import CodingWorkflowState
from ..trace.runtime import build_workflow_trace_entry, coerce_workflow_trace_items
from .artifacts import read_coding_artifact, store_coding_artifact
from .planner import CodingPlannerResult, CodingTaskPlan, plan_coding_task_with_llm
from .result import CodingWorkflowResult
from .state import CodingGraphState
from .worker_payloads import (
    build_coder_worker_payload,
    build_debugger_worker_payload,
    build_executor_worker_payload,
    build_pm_worker_payload,
    build_qa_worker_payload,
)


CODING_START_NODE = "coding_start_node"
PM_NODE = "pm_node"
CODER_NODE = "coder_node"
EXECUTOR_NODE = "executor_node"
WORKSPACE_EXECUTOR_NODE = EXECUTOR_NODE
QA_NODE = "qa_node"
DEBUGGER_NODE = "debugger_node"
CODING_FINISH_NODE = "coding_finish_node"
CODING_FAILURE_NODE = "coding_failure_node"
# Simple workspace actions (write/read/list) now bypass the coding workflow.
# They go directly through the action registry in agent_loop_graph.
RUN_ACTIONS_FOR_CODING_WORKFLOW = frozenset({"run.create"})
EXECUTOR_ACTIONS_FOR_CODING_WORKFLOW = RUN_ACTIONS_FOR_CODING_WORKFLOW
DEBUGGER_FALLBACK_LIST_KEYWORDS = (
    "列出",
    "目录",
    "结构",
    "上级",
    "父目录",
    "list",
    "ls",
    "tree",
)
DEBUGGER_MISSING_PATH_KEYWORDS = (
    "不存在",
    "找不到",
    "没有找到",
    "missing",
    "not found",
    "if missing",
    "if not exists",
)


def _merge_state(state, **updates):
    return {**state, **updates}





def _append_coding_trace(
    state: Mapping[str, object],
    *,
    node: str,
    event: str,
    ui_status: str,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    trace = coerce_workflow_trace_items(state.get("workflow_trace"))
    trace.append(
        build_workflow_trace_entry(
            step=len(trace) + 1,
            node=node,
            event=event,
            ui_status=ui_status,
            details=details,
            frontend_visible=False,
        )
    )
    return _merge_state(state, workflow_trace=trace)


def _first_task_from_prompt(prompt: str) -> str:
    return f"分析并准备执行用户的 coding 需求：{prompt}" if prompt else "分析用户的 coding 需求"


def _build_initial_tasks(prompt: str) -> list[str]:
    return [_first_task_from_prompt(prompt)]


def _partition_state(state: Mapping[str, object]) -> dict[str, object]:
    return CodingWorkflowState.from_mapping(state).as_dict()


def compact_text(value: object, *, limit: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _sanitize_action_result_for_state(
    action_result: Mapping[str, object],
    *,
    error_summary: str | None = None,
    raw_error_ref: str | None = None,
) -> dict[str, object]:
    metadata = dict(action_result.get("metadata") if isinstance(action_result.get("metadata"), Mapping) else {})
    if raw_error_ref:
        metadata["raw_error_ref"] = raw_error_ref
    if error_summary:
        metadata["error_summary"] = error_summary

    sanitized = {
        "action_name": action_result.get("action_name"),
        "ok": bool(action_result.get("ok")),
        "summary": error_summary or action_result.get("summary"),
        "data": action_result.get("data") if bool(action_result.get("ok")) else None,
        "error": error_summary if error_summary else action_result.get("error"),
        "metadata": metadata,
    }
    return sanitized


def _build_error_summary(raw_artifact: Mapping[str, object] | None) -> str:
    if raw_artifact is None:
        return "执行失败，但没有可读取的错误详情。"

    action_name = normalize_text(raw_artifact.get("action_name"), default="coding action")
    summary = compact_text(raw_artifact.get("summary"), limit=700)
    error = compact_text(raw_artifact.get("error"), limit=700)
    metadata = raw_artifact.get("metadata")
    error_code = ""
    if isinstance(metadata, Mapping):
        error_code = normalize_text(metadata.get("tool_error_code") or metadata.get("error_code"))

    detail = summary or error or "没有返回具体错误文本。"
    if error_code:
        return f"{action_name} 执行失败，错误码 `{error_code}`。摘要：{detail}"
    return f"{action_name} 执行失败。摘要：{detail}"


def _append_artifact_ref(value: object, artifact_ref: str | None) -> list[str]:
    refs = [
        str(item).strip()
        for item in value
        if isinstance(value, list) and str(item or "").strip()
    ] if isinstance(value, list) else []
    if artifact_ref:
        refs.append(artifact_ref)
    return refs


def coerce_int(value: object, *, default: int = 0) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _prompt_allows_missing_path_probe(prompt: object) -> bool:
    text = str(prompt or "").strip().lower()
    return (
        any(keyword.lower() in text for keyword in DEBUGGER_MISSING_PATH_KEYWORDS)
        and any(keyword.lower() in text for keyword in DEBUGGER_FALLBACK_LIST_KEYWORDS)
    )


def _parent_rel_path(rel_path: str) -> str:
    normalized = rel_path.replace("\\", "/").strip().strip("/")
    if not normalized:
        return "."
    parent = PurePosixPath(normalized).parent
    return "." if str(parent) in {"", "."} else str(parent)


def build_coding_workflow_node_failure_state(
    state: Mapping[str, object],
    *,
    node_name: str,
    exc: Exception,
) -> dict[str, object]:
    error = str(exc).strip() or exc.__class__.__name__
    next_state = _merge_state(
        state,
        output=f"Coding workflow 在 `{node_name}` 节点执行失败：{error}",
        error=error,
        ui_status="coding_workflow_failed",
        stop_reason="failed",
    )
    return _append_coding_trace(
        next_state,
        node=node_name,
        event="node_exception",
        ui_status="coding_workflow_failed",
        details={
            "error": error,
            "error_type": exc.__class__.__name__,
        },
    )


def coding_start_node(state: CodingGraphState) -> CodingGraphState:
    emit_workflow_node_entered(state, CODING_START_NODE)
    prompt = normalize_text(state.get("user_input"))
    if not prompt:
        raise ValueError("coding workflow requires non-empty user_input")
    next_state = _merge_state(
        state,
        intent=normalize_text(state.get("intent"), default="coding"),
        error=None,
        output="",
        ui_status="coding_started",
        stop_reason=None,
        tasks_list=[],
        current_task=None,
        raw_error_ref=None,
        error_summary=None,
        repair_count=0,
        max_debug_steps=coerce_int(state.get("max_debug_steps"), default=1),
        artifact_refs=[],
    )
    return _append_coding_trace(
        next_state,
        node=CODING_START_NODE,
        event="coding_started",
        ui_status="coding_started",
        details={"has_user_input": True},
    )


def pm_node(state: CodingGraphState) -> CodingGraphState:
    emit_workflow_node_entered(state, PM_NODE)
    worker_payload = build_pm_worker_payload(state, target_node=PM_NODE)
    prompt = normalize_text(worker_payload.payload.get("user_requirement"))
    tasks_list = _build_initial_tasks(prompt)
    current_task = tasks_list[0] if tasks_list else None
    next_state = _merge_state(
        state,
        tasks_list=tasks_list,
        current_task=current_task,
        ui_status="coding_pm_planned",
    )
    return _append_coding_trace(
        next_state,
        node=PM_NODE,
        event="coding_pm_planned",
        ui_status="coding_pm_planned",
        details={
            "task_count": len(tasks_list),
            "current_task": current_task,
            "worker_payload": worker_payload.as_dict(),
        },
    )


def _build_coder_action_plan(
    worker_payload: Mapping[str, object],
) -> tuple[str, dict[str, object]] | None:
    workspace_action_name = normalize_text(worker_payload.get("workspace_action_name"))
    if workspace_action_name:
        workspace_action_input = worker_payload.get("workspace_action_input")
        return (
            workspace_action_name,
            dict(workspace_action_input) if isinstance(workspace_action_input, Mapping) else {},
        )

    run_action_name = normalize_text(worker_payload.get("run_action_name"))
    if run_action_name:
        run_action_input = worker_payload.get("run_action_input")
        return (
            run_action_name,
            dict(run_action_input) if isinstance(run_action_input, Mapping) else {},
        )

    return None


def _planner_result_details(result: CodingPlannerResult) -> dict[str, object]:
    details = result.as_dict()
    details.pop("plan", None)
    return details


def _build_llm_coder_plan(
    worker_payload: Mapping[str, object],
    *,
    current_task: str,
) -> CodingPlannerResult:
    return plan_coding_task_with_llm(
        user_input=current_task,
        current_task=current_task,
        context=normalize_text(worker_payload.get("project_context_preview")) or None,
    )


def _state_updates_from_llm_plan(
    state: Mapping[str, object],
    plan: CodingTaskPlan,
) -> dict[str, object]:
    tasks_list = list(plan.tasks_list) or _build_initial_tasks(normalize_text(state.get("user_input")))
    current_task = tasks_list[0] if tasks_list else None
    coder_plan = plan.as_dict()
    return {
        "tasks_list": tasks_list,
        "current_task": current_task,
        "target_files": list(plan.target_files),
        "coder_plan": coder_plan,
        "executor_action_name": plan.executor_action_name,
        "executor_action_input": dict(plan.executor_action_input),
        "ui_status": "coding_coder_planned",
    }


def coder_node(state: CodingGraphState) -> CodingGraphState:
    emit_workflow_node_entered(state, CODER_NODE)
    worker_payload = build_coder_worker_payload(state, target_node=CODER_NODE)
    # Read action plan from state directly so that text values (e.g. file content)
    # are not silently truncated to MAX_WORKER_TEXT_CHARS by _safe_mapping.
    action_plan = _build_coder_action_plan_from_state(state)
    current_task = normalize_text(state.get("current_task"), default="准备 coding 执行动作")
    if action_plan is None:
        llm_result = _build_llm_coder_plan(worker_payload.payload, current_task=current_task)
        if llm_result.ok and llm_result.plan and llm_result.plan.executor_action_name:
            plan = llm_result.plan
            if plan.executor_action_name not in EXECUTOR_ACTIONS_FOR_CODING_WORKFLOW:
                raise ValueError(
                    f"unsupported coding executor action: {plan.executor_action_name}"
                )
            next_state = _merge_state(
                state,
                **_state_updates_from_llm_plan(state, plan),
            )
            return _append_coding_trace(
                next_state,
                node=CODER_NODE,
                event="coding_coder_llm_planned",
                ui_status="coding_coder_planned",
                details={
                    "action_name": plan.executor_action_name,
                    "current_task": plan.tasks_list[0] if plan.tasks_list else current_task,
                    "planner_result": _planner_result_details(llm_result),
                    "worker_payload": worker_payload.as_dict(),
                },
            )

        next_state = _merge_state(
            state,
            coder_plan={
                "task": current_task,
                "executor_action_name": None,
                "reason": (
                    llm_result.error
                    or "No executable action was provided to the coding workflow."
                ),
                "planner_source": "llm" if llm_result.error_kind != "unconfigured" else "rules",
                "planner_result": _planner_result_details(llm_result),
            },
            ui_status="coding_coder_noop",
        )
        return _append_coding_trace(
            next_state,
            node=CODER_NODE,
            event="coding_coder_noop",
            ui_status="coding_coder_noop",
            details={
                "current_task": current_task,
                "planner_result": _planner_result_details(llm_result),
                "worker_payload": worker_payload.as_dict(),
            },
        )

    action_name, action_input = action_plan
    if action_name not in EXECUTOR_ACTIONS_FOR_CODING_WORKFLOW:
        raise ValueError(f"unsupported coding executor action: {action_name}")

    coder_plan = {
        "task": current_task,
        "executor_action_name": action_name,
        "executor_action_input": action_input,
        "planner_source": "rules",
    }
    next_state = _merge_state(
        state,
        coder_plan=coder_plan,
        executor_action_name=action_name,
        executor_action_input=action_input,
        ui_status="coding_coder_planned",
    )
    return _append_coding_trace(
        next_state,
        node=CODER_NODE,
        event="coding_coder_planned",
        ui_status="coding_coder_planned",
        details={
            "action_name": action_name,
            "current_task": current_task,
            "worker_payload": worker_payload.as_dict(),
        },
    )


def executor_node(state: CodingGraphState) -> CodingGraphState:
    emit_workflow_node_entered(state, EXECUTOR_NODE)
    worker_payload = build_executor_worker_payload(state, target_node=EXECUTOR_NODE)
    action_name = normalize_text(state.get("executor_action_name"))
    if action_name not in EXECUTOR_ACTIONS_FOR_CODING_WORKFLOW:
        raise ValueError(f"unsupported coding executor action: {action_name}")

    executor_action_input = state.get("executor_action_input")
    action_input = dict(executor_action_input) if isinstance(executor_action_input, Mapping) else {}
    result = default_action_registry.execute(action_name, action_input)
    action_result = result.as_dict()
    metadata = dict(action_result.get("metadata") if isinstance(action_result.get("metadata"), Mapping) else {})
    metadata.update(
        {
            "workflow_name": "coding",
            "workflow_node": EXECUTOR_NODE,
            "effective_action_name": action_name,
            "effective_action_input": action_input,
            "coder_plan": dict(worker_payload.payload.get("coder_plan")) if isinstance(worker_payload.payload.get("coder_plan"), Mapping) else {},
            "debugger_plan": dict(worker_payload.payload.get("debugger_plan")) if isinstance(worker_payload.payload.get("debugger_plan"), Mapping) else {},
            "repair_count": coerce_int(state.get("repair_count")),
            "worker_payload": worker_payload.as_dict(),
        }
    )
    action_result["metadata"] = metadata
    raw_error_ref = None
    if not result.ok:
        raw_error_ref = store_coding_artifact("raw-error", action_result)
        action_result = _sanitize_action_result_for_state(
            action_result,
            error_summary=compact_text(result.summary or result.error, limit=900),
            raw_error_ref=raw_error_ref,
        )
    next_state = _merge_state(
        state,
        action_result=action_result,
        output=result.summary,
        error=None if result.ok else result.error or result.summary,
        error_summary=None if result.ok else state.get("error_summary"),
        raw_error_ref=raw_error_ref,
        artifact_refs=_append_artifact_ref(state.get("artifact_refs"), raw_error_ref),
        ui_status="coding_executor_done" if result.ok else "coding_executor_failed",
        stop_reason=None if result.ok else "tool_failed",
    )
    return _append_coding_trace(
        next_state,
        node=EXECUTOR_NODE,
        event="coding_executor_done" if result.ok else "coding_executor_failed",
        ui_status=normalize_text(next_state.get("ui_status")),
        details={
            "action_name": action_name,
            "ok": result.ok,
            "tool_error_code": metadata.get("tool_error_code"),
            "raw_error_ref": raw_error_ref,
            "worker_payload": worker_payload.as_dict(),
        },
    )


def qa_node(state: CodingGraphState) -> CodingGraphState:
    emit_workflow_node_entered(state, QA_NODE)
    worker_payload = build_qa_worker_payload(state, target_node=QA_NODE)
    raw_error_ref = normalize_text(worker_payload.payload.get("raw_error_ref"))
    raw_artifact = read_coding_artifact(raw_error_ref) if raw_error_ref else None
    error_summary = _build_error_summary(raw_artifact)
    action_result = state.get("action_result")
    sanitized_action_result = (
        _sanitize_action_result_for_state(
            action_result,
            error_summary=error_summary,
            raw_error_ref=raw_error_ref or None,
        )
        if isinstance(action_result, Mapping)
        else None
    )
    next_state = _merge_state(
        state,
        action_result=sanitized_action_result,
        error=error_summary,
        output=error_summary,
        error_summary=error_summary,
        raw_error_ref=None,
        ui_status="coding_qa_summarized",
        stop_reason="qa_failed_summary",
    )
    return _append_coding_trace(
        next_state,
        node=QA_NODE,
        event="coding_qa_summarized",
        ui_status="coding_qa_summarized",
        details={
            "raw_error_ref": raw_error_ref or None,
            "has_error_summary": bool(error_summary),
            "worker_payload": worker_payload.as_dict(),
        },
    )


def _build_debugger_plan(state: Mapping[str, object]) -> dict[str, object]:
    error_summary = normalize_text(state.get("error_summary") or state.get("error"))
    coder_plan = state.get("coder_plan")
    coder_plan_map = dict(coder_plan) if isinstance(coder_plan, Mapping) else {}
    action_name = normalize_text(
        coder_plan_map.get("executor_action_name") or state.get("executor_action_name")
    )
    action_input = (
        dict(coder_plan_map.get("executor_action_input"))
        if isinstance(coder_plan_map.get("executor_action_input"), Mapping)
        else dict(state.get("executor_action_input"))
        if isinstance(state.get("executor_action_input"), Mapping)
        else {}
    )
    current_task = normalize_text(state.get("current_task"))
    prompt = current_task

    if (
        action_name == "workspace.read"
        and _prompt_allows_missing_path_probe(prompt)
        and "没有找到 workspace 路径" in error_summary
    ):
        rel_path = normalize_text(action_input.get("rel_path"))
        if rel_path:
            parent_path = _parent_rel_path(rel_path)
            return {
                "repairable": True,
                "reason": "The requested read path is missing and the user allowed listing a parent directory.",
                "current_task": current_task,
                "error_summary": error_summary,
                "revised_action_name": "workspace.list",
                "revised_action_input": {
                    "rel_path": parent_path,
                    "recursive": False,
                },
            }

    return {
        "repairable": False,
        "reason": "No safe local debugger repair rule matched.",
        "current_task": current_task,
        "error_summary": error_summary,
        "original_action_name": action_name,
    }


def debugger_node(state: CodingGraphState) -> CodingGraphState:
    emit_workflow_node_entered(state, DEBUGGER_NODE)
    worker_payload = build_debugger_worker_payload(state, target_node=DEBUGGER_NODE)
    worker_state = worker_payload.payload
    repair_count = coerce_int(worker_state.get("repair_count"))
    max_debug_steps = coerce_int(worker_state.get("max_debug_steps"), default=1)
    if repair_count >= max_debug_steps:
        next_state = _merge_state(
            state,
            debugger_plan={
                "repairable": False,
                "reason": "max_debug_steps reached",
                "repair_count": repair_count,
                "max_debug_steps": max_debug_steps,
            },
            ui_status="coding_debugger_stopped",
            stop_reason="max_debug_steps",
        )
        return _append_coding_trace(
            next_state,
            node=DEBUGGER_NODE,
            event="coding_debugger_stopped",
            ui_status="coding_debugger_stopped",
            details={
                "repair_count": repair_count,
                "max_debug_steps": max_debug_steps,
                "worker_payload": worker_payload.as_dict(),
            },
        )

    debugger_plan = _build_debugger_plan(worker_state)
    if not bool(debugger_plan.get("repairable")):
        next_state = _merge_state(
            state,
            debugger_plan=debugger_plan,
            ui_status="coding_debugger_not_repairable",
            stop_reason="debugger_not_repairable",
        )
        return _append_coding_trace(
            next_state,
            node=DEBUGGER_NODE,
            event="coding_debugger_not_repairable",
            ui_status="coding_debugger_not_repairable",
            details={
                "reason": debugger_plan.get("reason"),
                "repair_count": repair_count,
                "max_debug_steps": max_debug_steps,
                "worker_payload": worker_payload.as_dict(),
            },
        )

    revised_action_name = normalize_text(debugger_plan.get("revised_action_name"))
    revised_action_input = (
        dict(debugger_plan.get("revised_action_input"))
        if isinstance(debugger_plan.get("revised_action_input"), Mapping)
        else {}
    )
    next_state = _merge_state(
        state,
        debugger_plan=debugger_plan,
        executor_action_name=revised_action_name,
        executor_action_input=revised_action_input,
        action_result=None,
        error=None,
        output="",
        raw_error_ref=None,
        repair_count=repair_count + 1,
        ui_status="coding_debugger_revised",
        stop_reason="debugger_revised",
    )
    return _append_coding_trace(
        next_state,
        node=DEBUGGER_NODE,
        event="coding_debugger_revised",
        ui_status="coding_debugger_revised",
        details={
            "revised_action_name": revised_action_name,
            "repair_count": repair_count + 1,
            "max_debug_steps": max_debug_steps,
            "worker_payload": worker_payload.as_dict(),
        },
    )


def coding_finish_node(state: CodingGraphState) -> CodingGraphState:
    emit_workflow_node_entered(state, CODING_FINISH_NODE)
    output = normalize_text(
        state.get("output"),
        default="Coding workflow skeleton completed. No tools were executed.",
    )
    finish_ui_status = "coding_workflow_done" if state.get("action_result") else "coding_skeleton_ready"
    next_state = _merge_state(
        state,
        output=output,
        ui_status=finish_ui_status,
        stop_reason="completed",
        error=None,
    )
    next_state = _append_coding_trace(
        next_state,
        node=CODING_FINISH_NODE,
        event="coding_finished",
        ui_status=finish_ui_status,
        details={
            "tool_execution": "executor_action"
            if state.get("action_result")
            else "not_connected"
        },
    )
    return _merge_state(
        next_state,
        coding_state=_partition_state(next_state),
    )


def coding_failure_node(state: CodingGraphState) -> CodingGraphState:
    emit_workflow_node_entered(state, CODING_FAILURE_NODE)
    next_state = _merge_state(
        state,
        output=normalize_text(
            state.get("output"),
            default="Coding workflow skeleton failed.",
        ),
        ui_status="coding_workflow_failed",
        stop_reason=normalize_text(state.get("stop_reason"), default="failed"),
    )
    next_state = _append_coding_trace(
        next_state,
        node=CODING_FAILURE_NODE,
        event="coding_failed",
        ui_status="coding_workflow_failed",
        details={"error": state.get("error")},
    )
    return _merge_state(
        next_state,
        coding_state=_partition_state(next_state),
    )


def route_after_node(state: Mapping[str, object]) -> str:
    return CODING_FAILURE_NODE if state.get("error") else "continue"


def route_after_executor(state: Mapping[str, object]) -> str:
    if state.get("error"):
        return QA_NODE
    return "continue"


def route_after_debugger(state: Mapping[str, object]) -> str:
    if state.get("error"):
        return CODING_FAILURE_NODE
    executor_action_name = normalize_text(state.get("executor_action_name"))
    if executor_action_name:
        return EXECUTOR_NODE
    return CODING_FAILURE_NODE


def route_after_pm(state: Mapping[str, object]) -> str:
    if state.get("error"):
        return CODING_FAILURE_NODE
    return CODER_NODE


def route_after_coder(state: Mapping[str, object]) -> str:
    if state.get("error"):
        return CODING_FAILURE_NODE
    executor_action_name = normalize_text(state.get("executor_action_name"))
    if executor_action_name:
        return EXECUTOR_NODE
    return CODING_FINISH_NODE


def create_coding_workflow_graph():
    workflow = StateGraph(CodingGraphState)
    register_agent_graph_nodes(
        workflow,
        node_handlers={
            CODING_START_NODE: coding_start_node,
            PM_NODE: pm_node,
            CODER_NODE: coder_node,
            EXECUTOR_NODE: executor_node,
            QA_NODE: qa_node,
            DEBUGGER_NODE: debugger_node,
            CODING_FINISH_NODE: coding_finish_node,
            CODING_FAILURE_NODE: coding_failure_node,
        },
        failure_builder=build_coding_workflow_node_failure_state,
    )
    workflow.set_entry_point(CODING_START_NODE)
    workflow.add_conditional_edges(
        CODING_START_NODE,
        route_after_node,
        {
            "continue": PM_NODE,
            CODING_FAILURE_NODE: CODING_FAILURE_NODE,
        },
    )
    workflow.add_conditional_edges(
        PM_NODE,
        route_after_pm,
        {
            CODER_NODE: CODER_NODE,
            CODING_FAILURE_NODE: CODING_FAILURE_NODE,
        },
    )
    workflow.add_conditional_edges(
        CODER_NODE,
        route_after_coder,
        {
            EXECUTOR_NODE: EXECUTOR_NODE,
            CODING_FINISH_NODE: CODING_FINISH_NODE,
            CODING_FAILURE_NODE: CODING_FAILURE_NODE,
        },
    )
    workflow.add_conditional_edges(
        EXECUTOR_NODE,
        route_after_executor,
        {
            "continue": CODING_FINISH_NODE,
            QA_NODE: QA_NODE,
        },
    )
    workflow.add_edge(QA_NODE, DEBUGGER_NODE)
    workflow.add_conditional_edges(
        DEBUGGER_NODE,
        route_after_debugger,
        {
            EXECUTOR_NODE: EXECUTOR_NODE,
            CODING_FAILURE_NODE: CODING_FAILURE_NODE,
        },
    )
    workflow.add_edge(CODING_FINISH_NODE, END)
    workflow.add_edge(CODING_FAILURE_NODE, END)
    return workflow.compile()


coding_workflow_graph = create_coding_workflow_graph()


def run_coding_workflow(
    prompt: str,
    *,
    context: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
    workspace_action_name: str | None = None,
    workspace_action_input: Mapping[str, object] | None = None,
    run_action_name: str | None = None,
    run_action_input: Mapping[str, object] | None = None,
    max_debug_steps: int = 1,
) -> CodingWorkflowResult:
    initial_state: CodingGraphState = {
        "turn_id": turn_id,
        "session_id": session_id,
        "user_input": prompt,
        "intent": "coding",
        "workflow_trace": [],
        "max_debug_steps": max_debug_steps,
    }
    if context is not None:
        initial_state["context"] = context
    if workspace_action_name is not None:
        initial_state["workspace_action_name"] = workspace_action_name
        initial_state["workspace_action_input"] = dict(workspace_action_input or {})
    if run_action_name is not None:
        initial_state["run_action_name"] = run_action_name
        initial_state["run_action_input"] = dict(run_action_input or {})

    return invoke_graph_with_result(
        coding_workflow_graph,
        initial_state=initial_state,
        on_success=CodingWorkflowResult.from_state,
        on_error=CodingWorkflowResult.from_error,
    )


# ---------------------------------------------------------------------------
# Coder action-plan helpers (reads from state directly, not from
# worker_payload, so that file content and other long text values are not
# truncated by _safe_mapping in build_coder_worker_payload).
# ---------------------------------------------------------------------------

def _build_coder_action_plan_from_state(
    state: Mapping[str, object],
) -> tuple[str, dict[str, object]] | None:
    workspace_action_name = normalize_text(state.get("workspace_action_name"))
    if workspace_action_name:
        action_input = state.get("workspace_action_input")
        return (
            workspace_action_name,
            dict(action_input) if isinstance(action_input, Mapping) else {},
        )

    run_action_name = normalize_text(state.get("run_action_name"))
    if run_action_name:
        action_input = state.get("run_action_input")
        return (
            run_action_name,
            dict(action_input) if isinstance(action_input, Mapping) else {},
        )
    return None
