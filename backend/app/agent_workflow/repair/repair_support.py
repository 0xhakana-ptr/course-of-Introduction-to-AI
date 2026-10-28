from collections.abc import Mapping
from dataclasses import dataclass

from ..formatters import (
    build_attempt_record_snapshot,
    build_attempt_summary,
    build_repair_retry_feedback_text,
)
from ..types.run_types import CommandResult, ScriptGenerationResult, WorkflowChatMessage
from .repair_retry_guidance import maybe_build_retry_guidance_for_repair_decision
from ..contracts.workflow_nodes import TASK_REPAIRING_NODE
from ..contracts.workflow_results import WorkflowRepairResult, invoke_graph_with_result


@dataclass(frozen=True, slots=True)
class RepairWorkflowMode:
    generate_feedback: bool = False
    generate_repair_script: bool = False


REPAIR_DECISION_ONLY_MODE = RepairWorkflowMode()
REPAIR_EXECUTION_MODE = RepairWorkflowMode(
    generate_feedback=True,
    generate_repair_script=True,
)


def merge_repair_state(
    state: Mapping[str, object],
    **updates: object,
) -> dict[str, object]:
    return {
        **state,
        **updates,
    }


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
        node_name=TASK_REPAIRING_NODE,
        content=feedback_text,
    )


def build_failure_inspected_state(
    state: Mapping[str, object],
    *,
    failure_summary: str,
) -> dict[str, object]:
    return merge_repair_state(
        state,
        failure_summary=failure_summary,
        analysis_note=failure_summary,
        analysis_source="fallback",
    )


def build_repair_eligibility_state(
    state: Mapping[str, object],
    *,
    eligible: bool,
    decision_reason: str | None = None,
) -> dict[str, object]:
    updates: dict[str, object] = {
        "eligible": eligible,
    }
    if decision_reason is not None:
        updates["decision_reason"] = decision_reason
    return merge_repair_state(state, **updates)


def build_repair_decision_state(
    state: Mapping[str, object],
    *,
    current_generator: str,
    should_attempt_repair: bool,
    decision_reason: str | None = None,
) -> dict[str, object]:
    return merge_repair_state(
        state,
        should_attempt_repair=should_attempt_repair,
        decision_reason=decision_reason if decision_reason is not None else state.get("decision_reason"),
        retry_guidance=maybe_build_retry_guidance_for_repair_decision(
            current_generator=current_generator,
            should_attempt_repair=should_attempt_repair,
        ),
    )


def build_feedback_composed_state(
    state: Mapping[str, object],
    *,
    feedback_message: WorkflowChatMessage,
) -> dict[str, object]:
    return merge_repair_state(
        state,
        feedback_message=feedback_message,
    )


def build_repair_codegen_state(
    state: Mapping[str, object],
    *,
    repaired_result: ScriptGenerationResult,
) -> dict[str, object]:
    return merge_repair_state(
        state,
        repaired_result=repaired_result,
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
    return invoke_graph_with_result(
        graph,
        initial_state=initial_state,
        on_success=WorkflowRepairResult.from_state,
        on_error=WorkflowRepairResult.from_error,
    )
