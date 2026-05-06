from dataclasses import dataclass
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
