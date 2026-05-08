from typing import TypedDict

from langgraph.graph import END, StateGraph

from ..core.text_utils import build_preview
from ..llm.client import call_llm_sync, llm_is_configured
from ..services.run_action.codegen import generate_repaired_script_with_llm
from ..services.run_action.types import (
    CommandResult,
    RetryGuidance,
    ScriptGenerationResult,
    WorkflowChatMessage,
)
from .repair_support import (
    REPAIR_DECISION_ONLY_MODE,
    REPAIR_EXECUTION_MODE,
    build_failure_inspected_state,
    build_feedback_composed_state,
    build_repair_feedback_message,
    build_repair_codegen_state,
    build_repair_decision_state,
    build_repair_eligibility_state,
    invoke_repair_graph,
    select_repair_graph_next_step,
)
from .summary_support import apply_text_resolution, build_prompt_text, resolve_summary_text
from .workflow_results import WorkflowRepairResult


REPAIR_ANALYSIS_SYSTEM_PROMPT = """你是 LangGraph 中负责失败分析的 QA 节点。

你会收到一次 Python 脚本执行失败的信息。请输出一条简洁、自然的中文分析，说明最可能的问题和下一步修复方向。

要求：
1. 只输出 1 到 2 句中文。
2. 不要输出列表、标题、Markdown 或代码块。
3. 不要复述全部日志，只保留最关键的问题线索。
4. 语气偏工程分析，不要扮演聊天助手。
"""


FAILURE_PREVIEW_LIMIT = 220
SCRIPT_PREVIEW_LIMIT = 400


class RepairDecisionState(TypedDict, total=False):
    run_id: str
    prompt: str
    context: str | None
    file_name: str
    script_content: str
    failure_result: CommandResult
    attempt_number: int
    current_generator: str
    repair_count: int
    max_repair_attempts: int
    llm_configured: bool
    eligible: bool
    failure_summary: str
    analysis_note: str
    analysis_source: str
    decision_reason: str
    should_attempt_repair: bool
    generate_repair_script: bool
    generate_feedback: bool
    feedback_message: WorkflowChatMessage | None
    retry_guidance: RetryGuidance | None
    repaired_result: ScriptGenerationResult | None


def preview_text(text: str, *, limit: int = FAILURE_PREVIEW_LIMIT) -> str:
    return build_preview(text, limit=limit, collapse_whitespace=False)


def summarize_failure_result(result: CommandResult) -> str:
    command = preview_text(str(result.get("command") or "(not executed)"), limit=120)
    returncode = result.get("returncode")
    error_text = (
        str(result.get("error") or "").strip()
        or str(result.get("stderr") or "").strip()
        or str(result.get("stdout") or "").strip()
        or "未提供更多失败信息"
    )
    error_preview = preview_text(error_text)

    parts = [f"命令 `{command}` 执行失败"]
    if returncode is not None:
        parts.append(f"返回码 {returncode}")
    parts.append(f"错误摘要：{error_preview}")
    return "；".join(parts) + "。"


def build_repair_analysis_prompt(state: RepairDecisionState) -> str:
    script_preview = preview_text(
        str(state.get("script_content") or ""),
        limit=SCRIPT_PREVIEW_LIMIT,
    ) or "(empty)"
    return build_prompt_text(
        [
            "请分析下面这次脚本执行失败，并给出一条简短的中文修复分析。",
            f"用户任务: {state.get('prompt') or '(none)'}",
            f"上下文: {state.get('context') or '(none)'}",
            f"文件名: {state.get('file_name') or '(none)'}",
            f"当前已用自动修复次数: {int(state.get('repair_count') or 0)}",
            f"失败摘要: {state.get('failure_summary') or '(none)'}",
            f"脚本预览:\n{script_preview}",
        ]
    )


def inspect_failure_node(state: RepairDecisionState) -> RepairDecisionState:
    failure_summary = summarize_failure_result(state["failure_result"])
    return build_failure_inspected_state(state, failure_summary=failure_summary)


def eligibility_node(state: RepairDecisionState) -> RepairDecisionState:
    repair_count = int(state.get("repair_count") or 0)
    max_repair_attempts = int(state.get("max_repair_attempts") or 0)

    if not bool(state.get("llm_configured", False)):
        return build_repair_eligibility_state(
            state,
            eligible=False,
            decision_reason="未配置真实大模型，无法自动修复失败脚本。",
        )

    if repair_count >= max_repair_attempts:
        return build_repair_eligibility_state(
            state,
            eligible=False,
            decision_reason="已达到自动修复最大次数限制。",
        )

    return build_repair_eligibility_state(state, eligible=True)


def route_by_eligibility(state: RepairDecisionState) -> str:
    return "qa_node" if bool(state.get("eligible")) else "decision_node"


def qa_node(state: RepairDecisionState) -> RepairDecisionState:
    if not bool(state.get("eligible")):
        return state

    resolution = resolve_summary_text(
        fallback_text=str(state.get("analysis_note") or state.get("failure_summary") or ""),
        prompt=build_repair_analysis_prompt(state),
        system_prompt=REPAIR_ANALYSIS_SYSTEM_PROMPT,
        temperature=0.1,
        llm_is_configured_fn=llm_is_configured,
        call_llm_sync_fn=call_llm_sync,
    )
    return apply_text_resolution(
        state,
        resolution=resolution,
        text_key="analysis_note",
        source_key="analysis_source",
    )


def decision_node(state: RepairDecisionState) -> RepairDecisionState:
    repair_count = int(state.get("repair_count") or 0)
    max_repair_attempts = int(state.get("max_repair_attempts") or 0)
    current_generator = str(state.get("current_generator") or "unknown")

    if not bool(state.get("eligible")):
        return build_repair_decision_state(
            state,
            current_generator=current_generator,
            should_attempt_repair=False,
        )

    return build_repair_decision_state(
        state,
        current_generator=current_generator,
        should_attempt_repair=True,
        decision_reason=(
            "失败分析已完成，准备尝试自动修复"
            f"（{repair_count + 1}/{max_repair_attempts}）。"
        ),
    )


def route_after_decision(state: RepairDecisionState) -> str:
    return select_repair_graph_next_step(state)


def compose_feedback_node(state: RepairDecisionState) -> RepairDecisionState:
    return build_feedback_composed_state(
        state,
        feedback_message=build_repair_feedback_message(
            run_id=str(state.get("run_id") or ""),
            attempt_number=int(state.get("attempt_number") or 0),
            current_generator=str(state.get("current_generator") or "unknown"),
            repair_count=int(state.get("repair_count") or 0),
            failure_result=state["failure_result"],
            analysis_note=(
                str(state.get("analysis_note") or "").strip() or None
            ),
        ),
    )


def route_after_feedback(state: RepairDecisionState) -> str:
    return select_repair_graph_next_step(state, after_feedback=True)


def repair_codegen_node(state: RepairDecisionState) -> RepairDecisionState:
    repaired_result = generate_repaired_script_with_llm(
        prompt=str(state.get("prompt") or ""),
        context=state.get("context"),
        file_name=str(state.get("file_name") or "main.py"),
        script_content=str(state.get("script_content") or ""),
        failure_result=state["failure_result"],
    )
    return build_repair_codegen_state(state, repaired_result=repaired_result)


def create_repair_decision_graph():
    workflow = StateGraph(RepairDecisionState)
    workflow.add_node("inspect_failure_node", inspect_failure_node)
    workflow.add_node("eligibility_node", eligibility_node)
    workflow.add_node("qa_node", qa_node)
    workflow.add_node("decision_node", decision_node)
    workflow.add_node("compose_feedback_node", compose_feedback_node)
    workflow.add_node("repair_codegen_node", repair_codegen_node)
    workflow.set_entry_point("inspect_failure_node")
    workflow.add_edge("inspect_failure_node", "eligibility_node")
    workflow.add_conditional_edges(
        "eligibility_node",
        route_by_eligibility,
        {
            "qa_node": "qa_node",
            "decision_node": "decision_node",
        },
    )
    workflow.add_edge("qa_node", "decision_node")
    workflow.add_conditional_edges(
        "decision_node",
        route_after_decision,
        {
            "compose_feedback_node": "compose_feedback_node",
            "repair_codegen_node": "repair_codegen_node",
            "end": END,
        },
    )
    workflow.add_conditional_edges(
        "compose_feedback_node",
        route_after_feedback,
        {
            "repair_codegen_node": "repair_codegen_node",
            "end": END,
        },
    )
    workflow.add_edge("repair_codegen_node", END)
    return workflow.compile()


repair_decision_graph = create_repair_decision_graph()


def evaluate_repair_decision(
    *,
    prompt: str,
    context: str | None,
    file_name: str,
    script_content: str,
    failure_result: CommandResult,
    repair_count: int,
    max_repair_attempts: int,
    llm_configured: bool,
) -> WorkflowRepairResult:
    return invoke_repair_graph(
        repair_decision_graph,
        workflow_mode=REPAIR_DECISION_ONLY_MODE,
        run_id="",
        prompt=prompt,
        context=context,
        file_name=file_name,
        script_content=script_content,
        failure_result=failure_result,
        attempt_number=0,
        current_generator=str(failure_result.get("generator") or "unknown"),
        repair_count=repair_count,
        max_repair_attempts=max_repair_attempts,
        llm_configured=llm_configured,
    )


def run_repair_workflow(
    *,
    run_id: str,
    prompt: str,
    context: str | None,
    file_name: str,
    script_content: str,
    failure_result: CommandResult,
    attempt_number: int,
    current_generator: str,
    repair_count: int,
    max_repair_attempts: int,
    llm_configured: bool,
) -> WorkflowRepairResult:
    return invoke_repair_graph(
        repair_decision_graph,
        workflow_mode=REPAIR_EXECUTION_MODE,
        run_id=run_id,
        prompt=prompt,
        context=context,
        file_name=file_name,
        script_content=script_content,
        failure_result=failure_result,
        attempt_number=attempt_number,
        current_generator=current_generator,
        repair_count=repair_count,
        max_repair_attempts=max_repair_attempts,
        llm_configured=llm_configured,
    )
