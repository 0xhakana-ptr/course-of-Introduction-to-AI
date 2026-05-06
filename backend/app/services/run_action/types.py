from dataclasses import dataclass, field
from typing import Any


LLM_PREVIEW_LIMIT = 400
SUMMARY_PREVIEW_LIMIT = 120
ATTEMPT_OUTPUT_PREVIEW_LIMIT = 2000
ATTEMPT_OUTPUT_CHUNK_LIMIT = 4000
ATTEMPT_OUTPUT_CHUNK_MAX_LIMIT = 20000
STARTUP_RECOVERY_PREVIEW_LIMIT = 10


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
class StartupRecoveryResult:
    checked_at: str
    scanned_count: int
    recovered_count: int
    recovered_run_ids: list[str]


class RunActionError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


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
