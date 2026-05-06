from ..core.config import settings
from ..llm.client import llm_is_configured
from ..schemas import RunResponse
from ..storage.run_store import (
    append_run_log,
    create_run_record,
    load_run_record,
    update_run_record,
    utc_now_iso,
)
from .run_action.codegen import (
    choose_demo_script,
    generate_repaired_script_with_llm,
    generate_script_with_llm,
    preview_text,
)
from .run_action.execution import append_execution_logs, execute_script_attempt
from .run_action.formatters import build_failure_output, build_success_output, to_run_response
from .run_action.queries import (
    get_run,
    get_run_attempt,
    get_run_attempt_output_chunk,
    get_run_attempt_script,
    get_run_attempts,
    get_run_log,
    list_run_summaries,
    list_runs,
)
from .run_action.recovery import recover_interrupted_runs
from .run_action.types import CommandResult, ScriptGenerationResult, StartupRecoveryResult


def _missing_llm_result() -> ScriptGenerationResult:
    return ScriptGenerationResult(ok=False, error="未配置真实大模型。")


def _can_use_generated_script(result: ScriptGenerationResult) -> bool:
    return bool(result.ok and result.file_name and result.script_content and result.raw_output)


def _mark_run_started(run_id: str, log_path: str) -> None:
    append_run_log(run_id, "Background execution started.")
    update_run_record(
        run_id,
        status="running",
        output="任务开始后台执行。",
        started_at=utc_now_iso(),
        finished_at=None,
        error=None,
        generator=None,
        attempt_count=0,
        repair_attempted=False,
        repair_count=0,
        command=None,
        returncode=None,
        stdout=None,
        stderr=None,
        log_path=log_path,
        artifacts=[],
        attempts=[],
    )
    append_run_log(run_id, "Status updated to running.")


def _resolve_initial_script(run_id: str, prompt: str, context: str | None) -> tuple[str, str, str]:
    llm_result = generate_script_with_llm(prompt, context) if llm_is_configured() else _missing_llm_result()

    if _can_use_generated_script(llm_result):
        append_run_log(run_id, "Using LLM-generated Python script.")
        append_run_log(run_id, f"LLM raw response preview: {preview_text(str(llm_result.raw_output))}")
        return (
            str(llm_result.file_name),
            str(llm_result.script_content),
            "llm",
        )

    file_name, script_content = choose_demo_script(prompt)
    if llm_is_configured():
        failure_reason = llm_result.error or "大模型生成失败。"
        append_run_log(
            run_id,
            f"LLM generation failed. Falling back to local template script: {preview_text(failure_reason)}",
        )
        if llm_result.raw_output and llm_result.raw_output != failure_reason:
            append_run_log(
                run_id,
                f"LLM generation raw preview: {preview_text(llm_result.raw_output)}",
            )
    else:
        append_run_log(run_id, "LLM is not configured. Falling back to local template script.")
    return file_name, script_content, "template"


def _begin_attempt(
    run_id: str,
    *,
    current_generator: str,
    attempt_count: int,
    repair_attempted: bool,
    repair_count: int,
) -> None:
    update_run_record(
        run_id,
        generator=current_generator,
        attempt_count=attempt_count,
        repair_attempted=repair_attempted,
        repair_count=repair_count,
    )
    append_run_log(
        run_id,
        f"Starting attempt {attempt_count} with generator={current_generator}.",
    )


def _build_repair_note(run_id: str, repair_count: int) -> str:
    if not llm_is_configured():
        note = "未配置真实大模型，无法自动修复失败脚本。"
        append_run_log(run_id, note)
        return note

    if repair_count >= settings.run_repair_max_attempts:
        note = "已达到自动修复最大次数限制。"
        append_run_log(run_id, note)
        return note

    return "当前运行不满足自动修复条件。"


def _finalize_success(
    run_id: str,
    *,
    log_path: str,
    initial_generator: str,
    current_generator: str,
    attempt_count: int,
    repair_attempted: bool,
    repair_count: int,
    result: CommandResult,
    artifacts: list[str],
) -> RunResponse:
    append_run_log(run_id, "Run finished successfully.")
    final_record = update_run_record(
        run_id,
        status="done",
        output=build_success_output(
            initial_generator=initial_generator,
            final_generator=current_generator,
            attempt_count=attempt_count,
            repair_count=repair_count,
            result=result,
            artifacts=artifacts,
        ),
        generator=current_generator,
        attempt_count=attempt_count,
        repair_attempted=repair_attempted,
        repair_count=repair_count,
        finished_at=utc_now_iso(),
        error=None,
        command=str(result.get("command")) if result.get("command") is not None else None,
        returncode=result.get("returncode"),
        stdout=str(result.get("stdout") or "").strip() or None,
        stderr=str(result.get("stderr") or "").strip() or None,
        log_path=log_path,
        artifacts=artifacts,
    )
    return to_run_response(final_record)


def _finalize_failure(
    run_id: str,
    *,
    log_path: str,
    initial_generator: str,
    current_generator: str,
    attempt_count: int,
    repair_attempted: bool,
    repair_count: int,
    result: CommandResult,
    artifacts: list[str],
    repair_note: str | None,
) -> RunResponse:
    append_run_log(run_id, "Run failed.")
    final_record = update_run_record(
        run_id,
        status="failed",
        output=build_failure_output(
            initial_generator=initial_generator,
            final_generator=current_generator,
            attempt_count=attempt_count,
            repair_count=repair_count,
            result=result,
            artifacts=artifacts,
            repair_note=repair_note,
        ),
        generator=current_generator,
        attempt_count=attempt_count,
        repair_attempted=repair_attempted,
        repair_count=repair_count,
        finished_at=utc_now_iso(),
        error=(
            repair_note
            or str(result.get("error") or "").strip()
            or str(result.get("stderr") or "").strip()
            or "Command execution failed"
        ),
        command=str(result.get("command")) if result.get("command") is not None else None,
        returncode=result.get("returncode"),
        stdout=str(result.get("stdout") or "").strip() or None,
        stderr=str(result.get("stderr") or "").strip() or None,
        log_path=log_path,
        artifacts=artifacts,
    )
    return to_run_response(final_record)


def create_run(prompt: str, context: str | None) -> RunResponse:
    record = create_run_record(
        prompt=prompt,
        context=context,
        status="queued",
        output="任务已创建，等待后台执行。",
    )
    run_id = str(record["run_id"])
    log_path = f"runs/{run_id}/log.txt"
    record = update_run_record(run_id, log_path=log_path)
    append_run_log(run_id, "Run queued.")
    return to_run_response(record)


def execute_run(run_id: str) -> RunResponse | None:
    record = load_run_record(run_id)
    if record is None:
        return None

    prompt = str(record.get("prompt") or "")
    context = str(record.get("context")) if record.get("context") is not None else None
    generated_dir = f"runs/{run_id}/generated"
    log_path = f"runs/{run_id}/log.txt"

    _mark_run_started(run_id, log_path)
    current_file_name, current_script_content, initial_generator = _resolve_initial_script(
        run_id,
        prompt,
        context,
    )

    current_generator = initial_generator
    attempt_count = 0
    repair_count = 0
    repair_attempted = False
    repair_note: str | None = None
    artifacts: list[str] = []
    last_result: CommandResult | None = None

    try:
        while True:
            attempt_count += 1
            _begin_attempt(
                run_id,
                current_generator=current_generator,
                attempt_count=attempt_count,
                repair_attempted=repair_attempted,
                repair_count=repair_count,
            )
            result = execute_script_attempt(
                run_id=run_id,
                generated_dir=generated_dir,
                file_name=current_file_name,
                script_content=current_script_content,
                attempt_number=attempt_count,
                generator=current_generator,
                repair_round=repair_count,
            )
            artifacts.append(str(result["script_rel_path"]))
            update_run_record(run_id, artifacts=artifacts)
            append_execution_logs(run_id, attempt_count, result)
            last_result = result

            if bool(result.get("ok")):
                return _finalize_success(
                    run_id,
                    log_path=log_path,
                    initial_generator=initial_generator,
                    current_generator=current_generator,
                    attempt_count=attempt_count,
                    repair_attempted=repair_attempted,
                    repair_count=repair_count,
                    result=result,
                    artifacts=artifacts,
                )

            if not (llm_is_configured() and repair_count < settings.run_repair_max_attempts):
                repair_note = _build_repair_note(run_id, repair_count)
                break

            repair_attempted = True
            repair_count += 1
            update_run_record(
                run_id,
                repair_attempted=repair_attempted,
                repair_count=repair_count,
            )
            append_run_log(
                run_id,
                (
                    f"Attempt {attempt_count} failed. Requesting LLM repair "
                    f"{repair_count}/{settings.run_repair_max_attempts}."
                ),
            )
            repaired_result = generate_repaired_script_with_llm(
                prompt=prompt,
                context=context,
                file_name=current_file_name,
                script_content=current_script_content,
                failure_result=result,
            )
            if not _can_use_generated_script(repaired_result):
                repair_note = (
                    repaired_result.error
                    or "自动修复已触发，但没有生成可解析的 Python 代码。"
                )
                append_run_log(run_id, repair_note)
                if repaired_result.raw_output and repaired_result.raw_output != repair_note:
                    append_run_log(
                        run_id,
                        f"LLM repair raw preview: {preview_text(repaired_result.raw_output)}",
                    )
                break

            current_file_name = str(repaired_result.file_name)
            current_script_content = str(repaired_result.script_content)
            current_generator = "llm_repair"
            append_run_log(run_id, "Using LLM-repaired Python script for the next attempt.")
            append_run_log(
                run_id,
                f"LLM repair response preview: {preview_text(str(repaired_result.raw_output))}",
            )

        if last_result is None:
            raise RuntimeError("任务未产生任何执行结果")

        return _finalize_failure(
            run_id,
            log_path=log_path,
            initial_generator=initial_generator,
            current_generator=current_generator,
            attempt_count=attempt_count,
            repair_attempted=repair_attempted,
            repair_count=repair_count,
            result=last_result,
            artifacts=artifacts,
            repair_note=repair_note,
        )
    except Exception as exc:
        append_run_log(run_id, f"Unhandled exception: {exc}")
        return to_run_response(
            update_run_record(
                run_id,
                status="failed",
                generator=current_generator,
                attempt_count=attempt_count,
                repair_attempted=repair_attempted,
                repair_count=repair_count,
                finished_at=utc_now_iso(),
                output=f"任务执行过程中发生未处理异常：{exc}",
                error=str(exc),
                log_path=log_path,
                artifacts=artifacts,
            )
        )


__all__ = [
    "StartupRecoveryResult",
    "create_run",
    "execute_run",
    "get_run",
    "get_run_attempt",
    "get_run_attempt_output_chunk",
    "get_run_attempt_script",
    "get_run_attempts",
    "get_run_log",
    "list_run_summaries",
    "list_runs",
    "recover_interrupted_runs",
]
