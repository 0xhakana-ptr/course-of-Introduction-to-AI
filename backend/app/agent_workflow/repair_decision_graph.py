from typing import TypedDict

from langgraph.graph import END, StateGraph

from ..core.text_utils import build_preview
from ..llm.client import call_llm_sync, llm_is_configured
from ..services.run_action.codegen import generate_repaired_script_with_llm
from ..services.run_action.formatters import (
    build_attempt_record_snapshot,
    build_attempt_summary,
    build_repair_retry_feedback_text,
)
from ..services.run_action.types import (
    CommandResult,
    RepairDecisionResult,
    RepairWorkflowResult,
    RetryGuidance,
    ScriptGenerationResult,
)
from .summary_support import resolve_summary_text


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
    feedback_text: str | None
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
    return "\n".join(
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
    return {
        **state,
        "failure_summary": failure_summary,
        "analysis_note": failure_summary,
        "analysis_source": "fallback",
    }


def eligibility_node(state: RepairDecisionState) -> RepairDecisionState:
    repair_count = int(state.get("repair_count") or 0)
    max_repair_attempts = int(state.get("max_repair_attempts") or 0)

    if not bool(state.get("llm_configured", False)):
        return {
            **state,
            "eligible": False,
            "decision_reason": "未配置真实大模型，无法自动修复失败脚本。",
        }

    if repair_count >= max_repair_attempts:
        return {
            **state,
            "eligible": False,
            "decision_reason": "已达到自动修复最大次数限制。",
        }

    return {
        **state,
        "eligible": True,
    }


def route_by_eligibility(state: RepairDecisionState) -> str:
    return "qa_node" if bool(state.get("eligible")) else "decision_node"


def build_retry_guidance(
    *,
    current_generator: str,
    should_attempt_repair: bool,
) -> RetryGuidance | None:
    if current_generator != "llm_repair":
        return None

    if should_attempt_repair:
        return RetryGuidance(
            node_name="task_retry_repairing",
            next_action="我会继续分析这次失败，并决定是否进入下一轮自动修复。",
        )

    return RetryGuidance(
        node_name="task_retry_failed",
        next_action="这轮自动修复后的尝试仍未成功，我会结束当前任务并整理失败原因。",
    )


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
    return {
        **state,
        "analysis_note": resolution.text,
        "analysis_source": resolution.source,
    }


def decision_node(state: RepairDecisionState) -> RepairDecisionState:
    repair_count = int(state.get("repair_count") or 0)
    max_repair_attempts = int(state.get("max_repair_attempts") or 0)
    current_generator = str(state.get("current_generator") or "unknown")

    if not bool(state.get("eligible")):
        return {
            **state,
            "should_attempt_repair": False,
            "retry_guidance": build_retry_guidance(
                current_generator=current_generator,
                should_attempt_repair=False,
            ),
        }

    return {
        **state,
        "should_attempt_repair": True,
        "decision_reason": (
            "失败分析已完成，准备尝试自动修复"
            f"（{repair_count + 1}/{max_repair_attempts}）。"
        ),
        "retry_guidance": build_retry_guidance(
            current_generator=current_generator,
            should_attempt_repair=True,
        ),
    }


def route_after_decision(state: RepairDecisionState) -> str:
    if not bool(state.get("should_attempt_repair")):
        return "end"
    if bool(state.get("generate_feedback", False)):
        return "compose_feedback_node"
    if bool(state.get("generate_repair_script", False)):
        return "repair_codegen_node"
    return "end"


def compose_feedback_node(state: RepairDecisionState) -> RepairDecisionState:
    attempt_record = build_attempt_record_snapshot(
        attempt_number=int(state.get("attempt_number") or 0),
        generator=str(state.get("current_generator") or "unknown"),
        repair_round=int(state.get("repair_count") or 0),
        result=state["failure_result"],
    )
    attempt_summary = build_attempt_summary(attempt_record)
    feedback_text = build_repair_retry_feedback_text(
        run_id=str(state.get("run_id") or ""),
        attempt_summary=attempt_summary,
        analysis_note=state.get("analysis_note"),
        next_repair_round=int(state.get("repair_count") or 0) + 1,
    )
    return {
        **state,
        "feedback_text": feedback_text,
    }


def route_after_feedback(state: RepairDecisionState) -> str:
    if bool(state.get("generate_repair_script", False)):
        return "repair_codegen_node"
    return "end"


def repair_codegen_node(state: RepairDecisionState) -> RepairDecisionState:
    repaired_result = generate_repaired_script_with_llm(
        prompt=str(state.get("prompt") or ""),
        context=state.get("context"),
        file_name=str(state.get("file_name") or "main.py"),
        script_content=str(state.get("script_content") or ""),
        failure_result=state["failure_result"],
    )
    return {
        **state,
        "repaired_result": repaired_result,
    }


def build_repair_initial_state(
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
    generate_repair_script: bool,
    generate_feedback: bool,
) -> RepairDecisionState:
    return {
        "run_id": run_id,
        "prompt": prompt,
        "context": context,
        "file_name": file_name,
        "script_content": script_content,
        "failure_result": failure_result,
        "attempt_number": attempt_number,
        "current_generator": current_generator,
        "repair_count": repair_count,
        "max_repair_attempts": max_repair_attempts,
        "llm_configured": llm_configured,
        "eligible": False,
        "failure_summary": "",
        "analysis_note": "",
        "analysis_source": "fallback",
        "decision_reason": "",
        "should_attempt_repair": False,
        "generate_repair_script": generate_repair_script,
        "generate_feedback": generate_feedback,
        "feedback_text": None,
        "retry_guidance": None,
        "repaired_result": None,
    }


def _build_repair_result_kwargs(result: RepairDecisionState) -> dict[str, object]:
    return {
        "should_attempt_repair": bool(result.get("should_attempt_repair", False)),
        "reason": str(result.get("decision_reason") or "当前运行不满足自动修复条件。"),
        "analysis_note": str(result.get("analysis_note") or result.get("failure_summary") or ""),
        "analysis_source": str(result.get("analysis_source") or "fallback"),
        "failure_summary": str(result.get("failure_summary") or ""),
    }


def _to_repair_decision_result(result: RepairDecisionState) -> RepairDecisionResult:
    return RepairDecisionResult(**_build_repair_result_kwargs(result))


def _to_repair_workflow_result(result: RepairDecisionState) -> RepairWorkflowResult:
    return RepairWorkflowResult(
        **_build_repair_result_kwargs(result),
        repaired_result=result.get("repaired_result"),
        feedback_text=(
            str(result.get("feedback_text"))
            if result.get("feedback_text") is not None
            else None
        ),
        retry_guidance=(
            result.get("retry_guidance")
            if isinstance(result.get("retry_guidance"), RetryGuidance)
            else None
        ),
    )


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
) -> RepairDecisionResult:
    initial_state = build_repair_initial_state(
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
        generate_repair_script=False,
        generate_feedback=False,
    )

    result = repair_decision_graph.invoke(initial_state)
    return _to_repair_decision_result(result)


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
) -> RepairWorkflowResult:
    initial_state = build_repair_initial_state(
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
        generate_repair_script=True,
        generate_feedback=True,
    )

    result = repair_decision_graph.invoke(initial_state)
    return _to_repair_workflow_result(result)
