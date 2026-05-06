from ...storage.run_store import (
    append_run_log,
    list_run_records,
    update_run_attempt,
    update_run_record,
    utc_now_iso,
)
from .formatters import get_attempt_records
from .types import STARTUP_RECOVERY_PREVIEW_LIMIT, StartupRecoveryResult


def build_startup_recovery_message(previous_status: str) -> str:
    if previous_status == "queued":
        return "服务重启前任务仍处于排队状态，已在启动时标记为失败。"
    return "服务重启导致运行中的任务中断，已在启动时标记为失败。"


def recover_interrupted_runs() -> StartupRecoveryResult:
    checked_at = utc_now_iso()
    records = list_run_records()
    recovered_run_ids: list[str] = []

    for record in records:
        status = str(record.get("status") or "")
        if status not in {"queued", "running"}:
            continue

        run_id = str(record["run_id"])
        finished_at = utc_now_iso()
        recovery_message = build_startup_recovery_message(status)

        for attempt in get_attempt_records(record):
            if str(attempt.get("status") or "") != "running":
                continue
            attempt_number = int(attempt.get("attempt_number") or 0)
            update_run_attempt(
                run_id,
                attempt_number,
                status="failed",
                error=recovery_message,
                finished_at=finished_at,
            )

        append_run_log(
            run_id,
            (
                "Startup recovery marked the run as failed after restart. "
                f"Previous status: {status}."
            ),
        )
        update_run_record(
            run_id,
            status="failed",
            output=recovery_message,
            error=recovery_message,
            finished_at=finished_at,
        )
        recovered_run_ids.append(run_id)

    return StartupRecoveryResult(
        checked_at=checked_at,
        scanned_count=len(records),
        recovered_count=len(recovered_run_ids),
        recovered_run_ids=recovered_run_ids[:STARTUP_RECOVERY_PREVIEW_LIMIT],
    )
