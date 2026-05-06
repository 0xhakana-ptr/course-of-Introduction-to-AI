import subprocess
import sys

from ...storage.run_store import (
    append_run_attempt,
    append_run_log,
    update_run_attempt,
    utc_now_iso,
)
from ...tools.safe_execute_command import safe_execute_command
from ...tools.safe_fs import safe_write_file
from .codegen import build_attempt_filename, sanitize_filename, validate_python_script
from .control import clear_run_process, is_run_cancel_requested, register_run_process
from .types import AttemptRecord, CommandResult


def build_attempt_record(
    generated_dir: str,
    file_name: str,
    attempt_number: int,
    generator: str,
    repair_round: int,
) -> AttemptRecord:
    source_file_name = sanitize_filename(file_name)
    attempt_file_name = build_attempt_filename(source_file_name, attempt_number)
    command_args = [sys.executable, attempt_file_name]
    command = subprocess.list2cmdline(command_args)
    return {
        "attempt_number": attempt_number,
        "generator": generator,
        "repair_round": repair_round,
        "status": "running",
        "source_file_name": source_file_name,
        "attempt_file_name": attempt_file_name,
        "script_rel_path": f"{generated_dir}/{attempt_file_name}",
        "command": command,
        "cwd": generated_dir,
        "returncode": None,
        "stdout": None,
        "stderr": None,
        "error": None,
        "started_at": utc_now_iso(),
        "finished_at": None,
        "duration_ms": None,
    }


def _build_validation_failure_result(
    attempt_record: AttemptRecord,
    *,
    generated_dir: str,
    generator: str,
    repair_round: int,
    syntax_error: str,
) -> CommandResult:
    finished_at = utc_now_iso()
    return {
        "ok": False,
        "returncode": None,
        "stdout": "",
        "stderr": syntax_error,
        "cwd": generated_dir,
        "error": "Python syntax validation failed",
        "command": str(attempt_record["command"]),
        "script_rel_path": str(attempt_record["script_rel_path"]),
        "attempt_file_name": str(attempt_record["attempt_file_name"]),
        "source_file_name": str(attempt_record["source_file_name"]),
        "generator": generator,
        "repair_round": repair_round,
        "started_at": attempt_record["started_at"],
        "finished_at": finished_at,
    }


def execute_script_attempt(
    run_id: str,
    generated_dir: str,
    file_name: str,
    script_content: str,
    attempt_number: int,
    generator: str,
    repair_round: int,
) -> CommandResult:
    attempt_record = build_attempt_record(
        generated_dir=generated_dir,
        file_name=file_name,
        attempt_number=attempt_number,
        generator=generator,
        repair_round=repair_round,
    )
    append_run_attempt(run_id, attempt_record)

    attempt_file_name = str(attempt_record["attempt_file_name"])
    script_rel_path = str(attempt_record["script_rel_path"])
    safe_write_file(script_rel_path, script_content)
    append_run_log(run_id, f"Generated file for attempt {attempt_number}: {script_rel_path}")

    command_args = [sys.executable, attempt_file_name]
    syntax_error = validate_python_script(attempt_file_name, script_content)
    if syntax_error:
        append_run_log(run_id, f"Python validation failed on attempt {attempt_number}.")
        result = _build_validation_failure_result(
            attempt_record,
            generated_dir=generated_dir,
            generator=generator,
            repair_round=repair_round,
            syntax_error=syntax_error,
        )
        update_run_attempt(
            run_id,
            attempt_number,
            status="failed",
            cwd=generated_dir,
            returncode=None,
            stdout="",
            stderr=syntax_error,
            error="Python syntax validation failed",
            finished_at=result["finished_at"],
        )
        return result

    command = str(attempt_record["command"])
    append_run_log(run_id, f"Executing attempt {attempt_number}: {command}")
    result = safe_execute_command(
        command_args,
        cwd=generated_dir,
        cancel_requested=lambda: is_run_cancel_requested(run_id),
        on_process_start=lambda process: register_run_process(run_id, process),
        on_process_end=lambda process: clear_run_process(run_id, process),
    )
    finished_at = utc_now_iso()
    result["command"] = command
    result["script_rel_path"] = script_rel_path
    result["attempt_file_name"] = attempt_file_name
    result["source_file_name"] = str(attempt_record["source_file_name"])
    result["generator"] = generator
    result["repair_round"] = repair_round
    result["started_at"] = attempt_record["started_at"]
    result["finished_at"] = finished_at
    update_run_attempt(
        run_id,
        attempt_number,
        status=(
            "cancelled"
            if bool(result.get("cancelled"))
            else "done" if bool(result.get("ok")) else "failed"
        ),
        cwd=str(result.get("cwd") or generated_dir),
        returncode=result.get("returncode"),
        stdout=str(result.get("stdout") or ""),
        stderr=str(result.get("stderr") or ""),
        error=str(result.get("error") or "") or None,
        finished_at=finished_at,
    )
    return result


def append_execution_logs(run_id: str, attempt_number: int, result: CommandResult) -> None:
    stdout = str(result.get("stdout") or "").strip()
    stderr = str(result.get("stderr") or "").strip()
    error = str(result.get("error") or "").strip()

    if stdout:
        append_run_log(run_id, f"Attempt {attempt_number} stdout: {stdout}")
    if stderr:
        append_run_log(run_id, f"Attempt {attempt_number} stderr: {stderr}")
    if error:
        append_run_log(run_id, f"Attempt {attempt_number} error: {error}")
