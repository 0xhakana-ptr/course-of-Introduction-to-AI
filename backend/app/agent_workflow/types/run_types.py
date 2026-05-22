from dataclasses import dataclass, field
from typing import Any, Literal

# -*- coding: utf-8 -*-
"""Run-related type definitions for agent workflow."""

from ...core.limits import (
    LLM_PREVIEW_MAX,
    RUN_ATTEMPT_OUTPUT_CHUNK_DEFAULT,
    RUN_ATTEMPT_OUTPUT_CHUNK_MAX,
    RUN_ATTEMPT_OUTPUT_PREVIEW_MAX,
    STARTUP_RECOVERY_PREVIEW_MAX,
    SUMMARY_PREVIEW_MAX,
)
from ..contracts.workflow_results import WorkflowRepairResult


LLM_PREVIEW_LIMIT = LLM_PREVIEW_MAX
SUMMARY_PREVIEW_LIMIT = SUMMARY_PREVIEW_MAX
ATTEMPT_OUTPUT_PREVIEW_LIMIT = RUN_ATTEMPT_OUTPUT_PREVIEW_MAX
ATTEMPT_OUTPUT_CHUNK_LIMIT = RUN_ATTEMPT_OUTPUT_CHUNK_DEFAULT
ATTEMPT_OUTPUT_CHUNK_MAX_LIMIT = RUN_ATTEMPT_OUTPUT_CHUNK_MAX
STARTUP_RECOVERY_PREVIEW_LIMIT = STARTUP_RECOVERY_PREVIEW_MAX


RunRecord = dict[str, object]
AttemptRecord = dict[str, object]
CommandResult = dict[str, Any]


@dataclass(slots=True)
class ScriptGenerationResult:
    ok: bool
    file_name: str | None = None
    script_content: str | None = None
    raw_output: str | None = None
    error: str | None = None


@dataclass(slots=True)
class RetryGuidance:
    node_name: str
    next_action: str


@dataclass(slots=True)
class WorkflowChatMessage:
    node_name: str
    content: str


RepairAssessmentResult = WorkflowRepairResult
RepairDecisionResult = WorkflowRepairResult
RepairWorkflowResult = WorkflowRepairResult


@dataclass(slots=True)
class RepairPhaseResolution:
    outcome: Literal["retry", "stop", "cancel"]
    repaired_result: ScriptGenerationResult | None = None
    cancel_reason: str | None = None

    @classmethod
    def retry(cls, repaired_result: ScriptGenerationResult) -> "RepairPhaseResolution":
        return cls(outcome="retry", repaired_result=repaired_result)

    @classmethod
    def stop(cls) -> "RepairPhaseResolution":
        return cls(outcome="stop")

    @classmethod
    def cancel(cls, reason: str) -> "RepairPhaseResolution":
        return cls(outcome="cancel", cancel_reason=reason)

    def require_repaired_result(self) -> ScriptGenerationResult:
        if self.repaired_result is None:
            raise RuntimeError("repair phase did not produce a repaired script")
        return self.repaired_result


@dataclass(slots=True)
class StartupRecoveryResult:
    checked_at: str
    scanned_count: int
    recovered_count: int
    recovered_run_ids: list[str]


class RunActionError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        *,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


@dataclass(slots=True)
class RunExecutionState:
    prompt: str
    context: str | None
    generated_dir: str
    log_path: str
    current_file_name: str
    current_script_content: str
    initial_generator: str
    current_generator: str
    attempt_count: int = 0
    repair_count: int = 0
    repair_attempted: bool = False
    repair_note: str | None = None
    artifacts: list[str] = field(default_factory=list)
    last_result: CommandResult | None = None
