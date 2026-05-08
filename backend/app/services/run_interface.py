from ..agent_workflow.repair_decision_graph import run_repair_workflow
from ..core.config import settings
from ..schemas import RunResponse
from ..storage.run_store import (
    append_run_log,
    create_run_record,
    load_run_record,
    update_run_record,
    utc_now_iso,
)
from .character_interface import send_task_cancelled, send_task_queued
from .run_action.control import clear_run_control, ensure_run_control, request_run_cancel
from .run_action.execution import execute_script_attempt
from .run_action.formatters import to_run_response
from .run_action.lifecycle import (
    advance_repair_phase,
    apply_repaired_script,
    begin_attempt,
    emit_final_run_chat_message,
    finalize_attempt_terminal_result,
    finalize_exception,
    finalize_cancelled,
    finalize_failure,
    initialize_run_execution,
    record_attempt_result,
    repair_llm_is_available,
    run_cancel_requested,
)
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
from .run_action.types import RunActionError, StartupRecoveryResult


def _finalize_queued_run(
    record: dict[str, object],
    *,
    queue_log_message: str,
    source_run_id: str | None = None,
    source_log_message: str | None = None,
) -> RunResponse:
    run_id = str(record["run_id"])
    log_path = f"runs/{run_id}/log.txt"
    record = update_run_record(run_id, log_path=log_path)
    append_run_log(run_id, queue_log_message)
    if source_run_id and source_log_message:
        append_run_log(source_run_id, source_log_message)
    send_task_queued()
    return to_run_response(record)


def create_run(prompt: str, context: str | None) -> RunResponse:
    record = create_run_record(
        prompt=prompt,
        context=context,
        status="queued",
        output="任务已创建，等待后台执行。",
        trigger_mode="create",
    )
    return _finalize_queued_run(
        record,
        queue_log_message="Run queued.",
    )


def _create_follow_up_run(
    source_run_id: str,
    *,
    trigger_mode: str,
    output: str,
    allowed_statuses: set[str],
) -> RunResponse:
    source_record = load_run_record(source_run_id, allow_invalid=True)
    if source_record is None:
        raise RunActionError(
            "source run not found",
            status_code=404,
            code="source_run_not_found",
        )

    source_status = str(source_record.get("status") or "")
    if source_status not in allowed_statuses:
        raise RunActionError(
            f"run with status '{source_status}' does not support {trigger_mode}",
            status_code=409,
            code=f"run_cannot_{trigger_mode}",
        )

    prompt = str(source_record.get("prompt") or "").strip()
    if not prompt:
        raise RunActionError(
            "source run prompt is empty",
            status_code=400,
            code="source_run_prompt_empty",
        )

    context = str(source_record.get("context")) if source_record.get("context") is not None else None
    record = create_run_record(
        prompt=prompt,
        context=context,
        status="queued",
        output=output,
        source_run_id=source_run_id,
        trigger_mode=trigger_mode,
    )
    run_id = str(record["run_id"])
    return _finalize_queued_run(
        record,
        queue_log_message=f"Run queued via {trigger_mode}. Source run: {source_run_id}",
        source_run_id=source_run_id,
        source_log_message=f"{trigger_mode} requested. Created follow-up run: {run_id}",
    )


def retry_run(source_run_id: str) -> RunResponse:
    return _create_follow_up_run(
        source_run_id,
        trigger_mode="retry",
        output="重试任务已创建，等待后台执行。",
        allowed_statuses={"failed"},
    )


def rerun_run(source_run_id: str) -> RunResponse:
    return _create_follow_up_run(
        source_run_id,
        trigger_mode="rerun",
        output="重新运行任务已创建，等待后台执行。",
        allowed_statuses={"done", "failed"},
    )


def cancel_run(run_id: str) -> RunResponse:
    record = load_run_record(run_id)
    if record is None:
        raise RunActionError("run not found", status_code=404, code="run_not_found")

    status = str(record.get("status") or "")
    if status in {"done", "failed", "cancelled"}:
        raise RunActionError(
            f"run with status '{status}' does not support cancel",
            status_code=409,
            code="run_cannot_cancel",
        )

    if status == "queued":
        request_run_cancel(run_id)
        append_run_log(run_id, "Cancellation requested before execution started.")
        cancelled_record = update_run_record(
            run_id,
            status="cancelled",
            cancel_requested=True,
            output="任务已取消，尚未开始执行。",
            error="用户在任务开始前取消了该任务。",
            finished_at=utc_now_iso(),
        )
        clear_run_control(run_id)
        send_task_cancelled()
        emit_final_run_chat_message(cancelled_record, node_name="task_cancelled")
        return to_run_response(cancelled_record)

    request_run_cancel(run_id)
    append_run_log(run_id, "Cancellation requested during execution.")
    updated_record = update_run_record(
        run_id,
        cancel_requested=True,
        output="已收到取消请求，正在尝试终止当前执行。",
        error="已收到取消请求，等待后台执行结束。",
    )
    ensure_run_control(run_id)
    return to_run_response(updated_record)


def execute_run(run_id: str) -> RunResponse | None:
    record = load_run_record(run_id)
    if record is None:
        return None
    if str(record.get("status") or "") == "cancelled":
        clear_run_control(run_id)
        return to_run_response(record)

    ensure_run_control(run_id)
    prompt = str(record.get("prompt") or "")
    context = str(record.get("context")) if record.get("context") is not None else None
    state = initialize_run_execution(run_id, prompt, context)

    try:
        if run_cancel_requested(run_id):
            return finalize_cancelled(run_id, state, reason="用户在任务启动后立即取消了该任务。")

        while True:
            if run_cancel_requested(run_id):
                return finalize_cancelled(run_id, state)

            begin_attempt(run_id, state)
            result = execute_script_attempt(
                run_id=run_id,
                generated_dir=state.generated_dir,
                file_name=state.current_file_name,
                script_content=state.current_script_content,
                attempt_number=state.attempt_count,
                generator=state.current_generator,
                repair_round=state.repair_count,
            )
            record_attempt_result(run_id, state, result)

            terminal_response = finalize_attempt_terminal_result(
                run_id,
                state,
                result,
                cancel_requested=run_cancel_requested(run_id),
            )
            if terminal_response is not None:
                return terminal_response

            repair_workflow = run_repair_workflow(
                run_id=run_id,
                prompt=state.prompt,
                context=state.context,
                file_name=state.current_file_name,
                script_content=state.current_script_content,
                failure_result=result,
                attempt_number=state.attempt_count,
                current_generator=state.current_generator,
                repair_count=state.repair_count,
                max_repair_attempts=settings.run_repair_max_attempts,
                llm_configured=repair_llm_is_available(),
            )

            repair_phase = advance_repair_phase(
                run_id=run_id,
                state=state,
                result=result,
                repair_workflow=repair_workflow,
            )

            if repair_phase.outcome == "cancel":
                return finalize_cancelled(
                    run_id,
                    state,
                    result=result,
                    reason=repair_phase.cancel_reason or "用户在自动修复阶段取消了当前任务。",
                )

            if repair_phase.outcome == "stop":
                break

            if not apply_repaired_script(
                run_id,
                state,
                repair_phase.require_repaired_result(),
            ):
                break

        if state.last_result is None:
            raise RuntimeError("任务未产生任何执行结果")

        return finalize_failure(run_id, state, state.last_result)
    except Exception as exc:
        return finalize_exception(run_id, state, exc)
    finally:
        clear_run_control(run_id)


__all__ = [
    "RunActionError",
    "StartupRecoveryResult",
    "create_run",
    "cancel_run",
    "execute_run",
    "get_run",
    "get_run_attempt",
    "get_run_attempt_output_chunk",
    "get_run_attempt_script",
    "get_run_attempts",
    "get_run_log",
    "list_run_summaries",
    "list_runs",
    "rerun_run",
    "recover_interrupted_runs",
    "retry_run",
]
