from collections.abc import Mapping
from dataclasses import dataclass

from ..services.run_action.formatters import (
    build_attempt_record_snapshot,
    build_attempt_summary,
    build_repair_retry_feedback_text,
)
from ..services.run_action.types import CommandResult, ScriptGenerationResult, WorkflowChatMessage
from .workflow_results import WorkflowRepairResult


@dataclass(frozen=True, slots=True)
class RepairWorkflowMode:
    generate_feedback: bool = False
    generate_repair_script: bool = False


REPAIR_DECISION_ONLY_MODE = RepairWorkflowMode()
REPAIR_EXECUTION_MODE = RepairWorkflowMode(
    generate_feedback=True,
    generate_repair_script=True,
)


def select_repair_graph_next_step(
    state: Mapping[str, object],
    *,
    after_feedback: bool = False,
) -> str:
    if not bool(state.get("should_attempt_repair")):
        return "end"
    if not after_feedback and bool(state.get("generate_feedback", False)):
        return "compose_feedback_node"
    if bool(state.get("generate_repair_script", False)):
        return "repair_codegen_node"
    return "end"


def build_repair_feedback_message(
    *,
    run_id: str,
    attempt_number: int,
    current_generator: str,
    repair_count: int,
    failure_result: CommandResult,
    analysis_note: str | None,
) -> WorkflowChatMessage:
    attempt_record = build_attempt_record_snapshot(
        attempt_number=attempt_number,
        generator=current_generator,
        repair_round=repair_count,
        result=failure_result,
    )
    attempt_summary = build_attempt_summary(attempt_record)
    feedback_text = build_repair_retry_feedback_text(
        run_id=run_id,
        attempt_summary=attempt_summary,
        analysis_note=analysis_note,
        next_repair_round=repair_count + 1,
    )
    return WorkflowChatMessage(
        node_name="task_repairing",
        content=feedback_text,
    )


def build_repair_initial_state(
    *,
    workflow_mode: RepairWorkflowMode,
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
) -> dict[str, object]:
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
        "generate_repair_script": workflow_mode.generate_repair_script,
        "generate_feedback": workflow_mode.generate_feedback,
        "feedback_message": None,
        "retry_guidance": None,
        "repaired_result": None,
    }


def invoke_repair_graph(
    graph: object,
    *,
    workflow_mode: RepairWorkflowMode,
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
    initial_state = build_repair_initial_state(
        workflow_mode=workflow_mode,
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
    result = graph.invoke(initial_state)
    return WorkflowRepairResult.from_state(result)
