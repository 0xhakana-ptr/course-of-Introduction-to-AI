import logging

from ...core.config import settings
from ...agent_workflow.roleplay import emit_roleplay_chat
from ...llm.client import llm_is_configured
from ...messaging.message_sender import message_sender
from ...schemas import RunResponse
from ..character_interface import (
    send_task_cancelled,
    send_task_done,
    send_task_failed,
    send_task_repairing,
    send_task_started,
)
from ...storage.run_store import append_run_log, update_run_record, utc_now_iso
from .codegen import choose_demo_script, generate_script_with_llm, preview_text
from .control import is_run_cancel_requested
from .execution import append_execution_logs
from .formatters import (
    build_attempt_record_snapshot,
    build_attempt_summary,
    build_cancelled_output,
    build_run_completion_chat_text,
    build_retry_outcome_chat_text,
    build_failure_output,
    build_success_output,
    to_run_response,
)
from .types import (
    CommandResult,
    RunRecord,
    RunExecutionState,
    RetryGuidance,
    ScriptGenerationResult,
)


logger = logging.getLogger(__name__)


def emit_final_run_chat_message(record: RunRecord, *, node_name: str) -> None:
    try:
        from ...agent_workflow.run_summary_graph import summarize_run_record

        summarize_run_record(
            record,
            node_name=node_name,
            emit_chat_message=True,
        )
    except Exception:
        logger.exception(
            "Run summary graph failed; falling back to direct summary message: run_id=%s",
            record.get("run_id"),
        )
        message_sender.send_chat_message(
            content=build_run_completion_chat_text(record),
            is_partial=False,
            node_name=node_name,
        )


def missing_llm_result() -> ScriptGenerationResult:
    return ScriptGenerationResult(ok=False, error="未配置真实大模型。")


def can_use_generated_script(result: ScriptGenerationResult) -> bool:
    return bool(result.ok and result.file_name and result.script_content and result.raw_output)


def mark_run_started(run_id: str, log_path: str) -> None:
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
    logger.info("Run started: run_id=%s", run_id)
    append_run_log(run_id, "Status updated to running.")
    send_task_started()


def resolve_initial_script(run_id: str, prompt: str, context: str | None) -> tuple[str, str, str]:
    llm_result = generate_script_with_llm(prompt, context) if llm_is_configured() else missing_llm_result()

    if can_use_generated_script(llm_result):
        append_run_log(run_id, "Using LLM-generated Python script.")
        append_run_log(run_id, f"LLM raw response preview: {preview_text(str(llm_result.raw_output))}")
        logger.info("Initial script resolved from LLM: run_id=%s", run_id)
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
        logger.warning("LLM generation failed; using template fallback: run_id=%s", run_id)
    else:
        append_run_log(run_id, "LLM is not configured. Falling back to local template script.")
        logger.info("LLM not configured; using template fallback: run_id=%s", run_id)
    return file_name, script_content, "template"


def initialize_run_execution(run_id: str, prompt: str, context: str | None) -> RunExecutionState:
    generated_dir = f"runs/{run_id}/generated"
    log_path = f"runs/{run_id}/log.txt"
    mark_run_started(run_id, log_path)
    current_file_name, current_script_content, initial_generator = resolve_initial_script(
        run_id,
        prompt,
        context,
    )
    return RunExecutionState(
        prompt=prompt,
        context=context,
        generated_dir=generated_dir,
        log_path=log_path,
        current_file_name=current_file_name,
        current_script_content=current_script_content,
        initial_generator=initial_generator,
        current_generator=initial_generator,
    )


def begin_attempt(run_id: str, state: RunExecutionState) -> None:
    state.attempt_count += 1
    update_run_record(
        run_id,
        generator=state.current_generator,
        attempt_count=state.attempt_count,
        repair_attempted=state.repair_attempted,
        repair_count=state.repair_count,
    )
    append_run_log(
        run_id,
        f"Starting attempt {state.attempt_count} with generator={state.current_generator}.",
    )
    logger.info(
        "Run attempt started: run_id=%s attempt=%s generator=%s",
        run_id,
        state.attempt_count,
        state.current_generator,
    )


def run_cancel_requested(run_id: str) -> bool:
    return is_run_cancel_requested(run_id)


def record_attempt_result(run_id: str, state: RunExecutionState, result: CommandResult) -> None:
    state.artifacts.append(str(result["script_rel_path"]))
    update_run_record(run_id, artifacts=state.artifacts)
    append_execution_logs(run_id, state.attempt_count, result)
    state.last_result = result


def append_repair_analysis_log(
    run_id: str,
    analysis_note: str | None,
    *,
    analysis_source: str | None = None,
) -> None:
    if not analysis_note:
        return
    source = analysis_source or "fallback"
    append_run_log(run_id, f"Repair analysis ({source}): {preview_text(analysis_note)}")


def emit_repair_feedback_message(content: str | None, *, node_name: str = "task_repairing") -> None:
    emit_roleplay_chat(
        content or "",
        node_name=node_name,
        emit_chat_message=True,
    )


def is_repair_attempt(state: RunExecutionState) -> bool:
    return state.current_generator == "llm_repair"


def build_retry_attempt_summary(
    *,
    state: RunExecutionState,
    result: CommandResult,
) -> str:
    attempt_record = build_attempt_record_snapshot(
        attempt_number=state.attempt_count,
        generator=state.current_generator,
        repair_round=state.repair_count,
        result=result,
    )
    return build_attempt_summary(attempt_record)


def maybe_emit_retry_outcome_for_repair_attempt(
    *,
    run_id: str,
    state: RunExecutionState,
    result: CommandResult,
    guidance: RetryGuidance,
) -> None:
    if not is_repair_attempt(state):
        return

    emit_retry_outcome_message(
        run_id=run_id,
        attempt_summary=build_retry_attempt_summary(state=state, result=result),
        next_action=guidance.next_action,
        node_name=guidance.node_name,
    )


def emit_retry_outcome_message(
    *,
    run_id: str,
    attempt_summary: str,
    next_action: str,
    node_name: str,
) -> None:
    try:
        from ...agent_workflow.attempt_summary_graph import summarize_retry_outcome

        summarize_retry_outcome(
            run_id=run_id,
            attempt_summary=attempt_summary,
            next_action=next_action,
            node_name=node_name,
            emit_chat_message=True,
        )
    except Exception:
        logger.exception(
            "Attempt summary graph failed; falling back to direct retry outcome message: run_id=%s",
            run_id,
        )
        emit_roleplay_chat(
            build_retry_outcome_chat_text(
                run_id=run_id,
                attempt_summary=attempt_summary,
                next_action=next_action,
            ),
            node_name=node_name,
            emit_chat_message=True,
        )


def repair_llm_is_available() -> bool:
    return llm_is_configured()


def mark_repair_requested(
    run_id: str,
    state: RunExecutionState,
    *,
    analysis_note: str | None = None,
    analysis_source: str | None = None,
) -> None:
    state.repair_attempted = True
    state.repair_count += 1
    update_run_record(
        run_id,
        repair_attempted=state.repair_attempted,
        repair_count=state.repair_count,
    )
    append_repair_analysis_log(
        run_id,
        analysis_note,
        analysis_source=analysis_source,
    )
    append_run_log(
        run_id,
        (
            f"Attempt {state.attempt_count} failed. Requesting LLM repair "
            f"{state.repair_count}/{settings.run_repair_max_attempts}."
        ),
    )
    logger.info(
        "Run repair requested: run_id=%s attempt=%s repair_round=%s",
        run_id,
        state.attempt_count,
        state.repair_count,
    )
    send_task_repairing()


def block_repair(
    run_id: str,
    state: RunExecutionState,
    *,
    note: str | None = None,
    analysis_note: str | None = None,
    analysis_source: str | None = None,
) -> str:
    resolved_note = note
    if resolved_note is None:
        if not llm_is_configured():
            resolved_note = "未配置真实大模型，无法自动修复失败脚本。"
        elif state.repair_count >= settings.run_repair_max_attempts:
            resolved_note = "已达到自动修复最大次数限制。"
        else:
            resolved_note = "当前运行不满足自动修复条件。"

    state.repair_note = resolved_note
    append_repair_analysis_log(
        run_id,
        analysis_note,
        analysis_source=analysis_source,
    )
    append_run_log(run_id, resolved_note)
    logger.warning("Run repair blocked: run_id=%s reason=%s", run_id, resolved_note)
    return resolved_note


def apply_repaired_script(
    run_id: str,
    state: RunExecutionState,
    repaired_result: ScriptGenerationResult,
) -> bool:
    if not can_use_generated_script(repaired_result):
        state.repair_note = (
            repaired_result.error
            or "自动修复已触发，但没有生成可解析的 Python 代码。"
        )
        append_run_log(run_id, state.repair_note)
        if repaired_result.raw_output and repaired_result.raw_output != state.repair_note:
            append_run_log(
                run_id,
                f"LLM repair raw preview: {preview_text(repaired_result.raw_output)}",
            )
        logger.warning("Run repair failed to produce usable script: run_id=%s", run_id)
        return False

    state.current_file_name = str(repaired_result.file_name)
    state.current_script_content = str(repaired_result.script_content)
    state.current_generator = "llm_repair"
    append_run_log(run_id, "Using LLM-repaired Python script for the next attempt.")
    append_run_log(
        run_id,
        f"LLM repair response preview: {preview_text(str(repaired_result.raw_output))}",
    )
    logger.info("Run repair applied successfully: run_id=%s", run_id)
    return True


def finalize_success(run_id: str, state: RunExecutionState, result: CommandResult) -> RunResponse:
    append_run_log(run_id, "Run finished successfully.")
    send_task_done()
    logger.info(
        "Run finished successfully: run_id=%s attempts=%s repairs=%s",
        run_id,
        state.attempt_count,
        state.repair_count,
    )
    final_record = update_run_record(
        run_id,
        status="done",
        output=build_success_output(
            initial_generator=state.initial_generator,
            final_generator=state.current_generator,
            attempt_count=state.attempt_count,
            repair_count=state.repair_count,
            result=result,
            artifacts=state.artifacts,
        ),
        generator=state.current_generator,
        attempt_count=state.attempt_count,
        repair_attempted=state.repair_attempted,
        repair_count=state.repair_count,
        finished_at=utc_now_iso(),
        error=None,
        command=str(result.get("command")) if result.get("command") is not None else None,
        returncode=result.get("returncode"),
        stdout=str(result.get("stdout") or "").strip() or None,
        stderr=str(result.get("stderr") or "").strip() or None,
        log_path=state.log_path,
        artifacts=state.artifacts,
    )
    emit_final_run_chat_message(final_record, node_name="task_done")
    return to_run_response(final_record)


def finalize_failure(run_id: str, state: RunExecutionState, result: CommandResult) -> RunResponse:
    append_run_log(run_id, "Run failed.")
    send_task_failed()
    logger.warning(
        "Run finished with failure: run_id=%s attempts=%s repairs=%s",
        run_id,
        state.attempt_count,
        state.repair_count,
    )
    final_record = update_run_record(
        run_id,
        status="failed",
        output=build_failure_output(
            initial_generator=state.initial_generator,
            final_generator=state.current_generator,
            attempt_count=state.attempt_count,
            repair_count=state.repair_count,
            result=result,
            artifacts=state.artifacts,
            repair_note=state.repair_note,
        ),
        generator=state.current_generator,
        attempt_count=state.attempt_count,
        repair_attempted=state.repair_attempted,
        repair_count=state.repair_count,
        finished_at=utc_now_iso(),
        error=(
            state.repair_note
            or str(result.get("error") or "").strip()
            or str(result.get("stderr") or "").strip()
            or "Command execution failed"
        ),
        command=str(result.get("command")) if result.get("command") is not None else None,
        returncode=result.get("returncode"),
        stdout=str(result.get("stdout") or "").strip() or None,
        stderr=str(result.get("stderr") or "").strip() or None,
        log_path=state.log_path,
        artifacts=state.artifacts,
    )
    emit_final_run_chat_message(final_record, node_name="task_failed")
    return to_run_response(final_record)


def finalize_cancelled(
    run_id: str,
    state: RunExecutionState,
    *,
    result: CommandResult | None = None,
    reason: str = "用户取消了当前任务。",
) -> RunResponse:
    append_run_log(run_id, f"Run cancelled. reason={reason}")
    send_task_cancelled()
    logger.warning(
        "Run cancelled: run_id=%s attempts=%s repairs=%s reason=%s",
        run_id,
        state.attempt_count,
        state.repair_count,
        reason,
    )
    final_record = update_run_record(
        run_id,
        status="cancelled",
        output=build_cancelled_output(
            initial_generator=state.initial_generator,
            final_generator=state.current_generator,
            attempt_count=state.attempt_count,
            repair_count=state.repair_count,
            artifacts=state.artifacts,
            cancel_reason=reason,
            result=result,
        ),
        cancel_requested=True,
        generator=state.current_generator,
        attempt_count=state.attempt_count,
        repair_attempted=state.repair_attempted,
        repair_count=state.repair_count,
        finished_at=utc_now_iso(),
        error=reason,
        command=str(result.get("command")) if result and result.get("command") is not None else None,
        returncode=result.get("returncode") if result is not None else None,
        stdout=(
            str(result.get("stdout") or "").strip() or None
            if result is not None
            else None
        ),
        stderr=(
            str(result.get("stderr") or "").strip() or None
            if result is not None
            else None
        ),
        log_path=state.log_path,
        artifacts=state.artifacts,
    )
    emit_final_run_chat_message(final_record, node_name="task_cancelled")
    return to_run_response(final_record)


def finalize_exception(run_id: str, state: RunExecutionState, exc: Exception) -> RunResponse:
    append_run_log(run_id, f"Unhandled exception: {exc}")
    send_task_failed()
    logger.exception("Unhandled run exception: run_id=%s", run_id)
    final_record = update_run_record(
        run_id,
        status="failed",
        generator=state.current_generator,
        attempt_count=state.attempt_count,
        repair_attempted=state.repair_attempted,
        repair_count=state.repair_count,
        finished_at=utc_now_iso(),
        output=f"任务执行过程中发生未处理异常：{exc}",
        error=str(exc),
        log_path=state.log_path,
        artifacts=state.artifacts,
    )
    emit_final_run_chat_message(final_record, node_name="task_failed")
    return to_run_response(final_record)
