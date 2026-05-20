from ...core.text_utils import build_preview, clip_text
from ...schemas import (
    RunDetailSection,
    RunAttemptResponse,
    RunResponse,
    RunStateSnapshotResponse,
    RunSummaryResponse,
)
from .types import (
    ATTEMPT_OUTPUT_PREVIEW_LIMIT,
    AttemptRecord,
    CommandResult,
    RunRecord,
    SUMMARY_PREVIEW_LIMIT,
)
from ...agent_workflow.formatters import (
    build_attempt_record_snapshot,
    build_attempt_summary,
    build_repair_retry_feedback_text,
    build_retry_outcome_chat_text,
    build_run_chat_text,
    build_run_completion_chat_text,
    build_run_summary_text,
    describe_generator,
    get_attempt_records,
    preview_single_line,
)


def find_attempt_record(record: RunRecord, attempt_number: int) -> AttemptRecord | None:
    return next(
        (
            item
            for item in get_attempt_records(record)
            if int(item.get("attempt_number") or 0) == attempt_number
        ),
        None,
    )


def to_run_attempt_response(record: AttemptRecord) -> RunAttemptResponse:
    stdout_value, stdout_length, stdout_truncated = clip_text(
        str(record.get("stdout")) if record.get("stdout") is not None else None,
        limit=ATTEMPT_OUTPUT_PREVIEW_LIMIT,
    )
    stderr_value, stderr_length, stderr_truncated = clip_text(
        str(record.get("stderr")) if record.get("stderr") is not None else None,
        limit=ATTEMPT_OUTPUT_PREVIEW_LIMIT,
    )
    error_value, error_length, error_truncated = clip_text(
        str(record.get("error")) if record.get("error") is not None else None,
        limit=ATTEMPT_OUTPUT_PREVIEW_LIMIT,
    )
    script_rel_path = str(record["script_rel_path"]) if record.get("script_rel_path") is not None else None
    return RunAttemptResponse(
        attempt_number=int(record["attempt_number"]),
        generator=str(record["generator"]),
        repair_round=int(record["repair_round"]) if record.get("repair_round") is not None else 0,
        status=str(record["status"]),
        summary=build_attempt_summary(record),
        source_file_name=(
            str(record["source_file_name"]) if record.get("source_file_name") is not None else None
        ),
        attempt_file_name=(
            str(record["attempt_file_name"]) if record.get("attempt_file_name") is not None else None
        ),
        script_rel_path=script_rel_path,
        command=str(record["command"]) if record.get("command") is not None else None,
        cwd=str(record["cwd"]) if record.get("cwd") is not None else None,
        returncode=int(record["returncode"]) if record.get("returncode") is not None else None,
        stdout=stdout_value,
        stdout_length=stdout_length,
        stdout_truncated=stdout_truncated,
        stderr=stderr_value,
        stderr_length=stderr_length,
        stderr_truncated=stderr_truncated,
        error=error_value,
        error_length=error_length,
        error_truncated=error_truncated,
        script_available=script_rel_path is not None,
        started_at=str(record["started_at"]) if record.get("started_at") is not None else None,
        finished_at=str(record["finished_at"]) if record.get("finished_at") is not None else None,
        duration_ms=int(record["duration_ms"]) if record.get("duration_ms") is not None else None,
    )


def _item(label: str, value: object) -> dict[str, object]:
    return {"label": label, "value": value}


def _has_display_value(value: object) -> bool:
    return value is not None and value != ""


def _format_duration_ms(value: object) -> str | None:
    if not isinstance(value, int):
        return None
    if value < 1000:
        return f"{value} ms"
    return f"{value / 1000:.2f} s"

def _build_overview_section(record: RunRecord) -> RunDetailSection:
    generator = (
        describe_generator(str(record.get("generator") or "unknown"))
        if record.get("generator") is not None
        else None
    )
    duration = _format_duration_ms(record.get("duration_ms"))
    items = [
        _item("状态", str(record.get("status") or "")),
        _item("生成方式", generator),
        _item("尝试次数", int(record.get("attempt_count") or 0)),
        _item("自动修复次数", int(record.get("repair_count") or 0)),
        _item("耗时", duration),
    ]
    return RunDetailSection(
        key="overview",
        title="任务概览",
        summary=build_run_summary_text(record),
        items=[item for item in items if _has_display_value(item["value"])],
        technical=False,
    )


def _build_result_section(record: RunRecord) -> RunDetailSection:
    output = str(record.get("output") or "").strip()
    error = str(record.get("error") or "").strip()
    artifacts = [
        {"path": str(artifact)}
        for artifact in record.get("artifacts", [])
        if isinstance(artifact, str) and artifact.strip()
    ]
    summary_source = output or error or "任务还没有可展示的最终结果。"
    return RunDetailSection(
        key="result",
        title="最终结果",
        summary=preview_single_line(summary_source, limit=300),
        items=artifacts,
        technical=False,
    )


def _build_attempts_section(attempts: list[AttemptRecord]) -> RunDetailSection:
    return RunDetailSection(
        key="attempts",
        title="尝试记录",
        summary=(
            f"共记录 {len(attempts)} 次执行尝试。"
            if attempts
            else "这个任务还没有开始执行尝试。"
        ),
        items=[
            {
                "attempt_number": int(attempt.get("attempt_number") or 0),
                "status": str(attempt.get("status") or ""),
                "generator": describe_generator(str(attempt.get("generator") or "unknown")),
                "repair_round": int(attempt.get("repair_round") or 0),
                "returncode": attempt.get("returncode"),
                "duration_ms": attempt.get("duration_ms"),
                "script_available": attempt.get("script_rel_path") is not None,
                "summary": build_attempt_summary(attempt),
            }
            for attempt in attempts
        ],
        technical=False,
    )


def _build_diagnostics_section(record: RunRecord, attempts: list[AttemptRecord]) -> RunDetailSection:
    latest_attempt = attempts[-1] if attempts else {}
    latest_stdout = str(latest_attempt.get("stdout") or record.get("stdout") or "")
    latest_stderr = str(latest_attempt.get("stderr") or record.get("stderr") or "")
    latest_error = str(latest_attempt.get("error") or record.get("error") or "")
    items = [
        _item("命令", latest_attempt.get("command") or record.get("command")),
        _item("工作目录", latest_attempt.get("cwd")),
        _item("返回码", latest_attempt.get("returncode") or record.get("returncode")),
        _item("日志路径", record.get("log_path")),
        _item("stdout 长度", len(latest_stdout) if latest_stdout else 0),
        _item("stderr 长度", len(latest_stderr) if latest_stderr else 0),
        _item("error 长度", len(latest_error) if latest_error else 0),
    ]
    content_parts: list[str] = []
    if latest_stdout.strip():
        content_parts.append(f"stdout preview:\n{preview_single_line(latest_stdout, limit=600)}")
    if latest_stderr.strip():
        content_parts.append(f"stderr preview:\n{preview_single_line(latest_stderr, limit=600)}")
    if latest_error.strip():
        content_parts.append(f"error preview:\n{preview_single_line(latest_error, limit=600)}")
    return RunDetailSection(
        key="diagnostics",
        title="调试信息",
        summary="这里保留命令、日志路径和输出长度，完整内容请按需读取日志或分块输出。",
        content="\n\n".join(content_parts) or None,
        items=[item for item in items if _has_display_value(item["value"])],
        technical=True,
    )


def build_run_detail_sections(record: RunRecord) -> list[RunDetailSection]:
    attempts = get_attempt_records(record)
    return [
        _build_overview_section(record),
        _build_result_section(record),
        _build_attempts_section(attempts),
        _build_diagnostics_section(record, attempts),
    ]


def to_run_response(record: RunRecord) -> RunResponse:
    attempts = get_attempt_records(record)
    return RunResponse(
        run_id=str(record["run_id"]),
        status=str(record["status"]),
        output=str(record["output"]),
        created_at=str(record["created_at"]),
        updated_at=str(record["updated_at"]),
        source_run_id=str(record["source_run_id"]) if record.get("source_run_id") is not None else None,
        trigger_mode=str(record["trigger_mode"]) if record.get("trigger_mode") is not None else None,
        cancel_requested=bool(record.get("cancel_requested", False)),
        generator=str(record["generator"]) if record.get("generator") is not None else None,
        attempt_count=int(record["attempt_count"]) if record.get("attempt_count") is not None else 0,
        repair_attempted=bool(record.get("repair_attempted", False)),
        repair_count=int(record["repair_count"]) if record.get("repair_count") is not None else 0,
        started_at=str(record["started_at"]) if record.get("started_at") is not None else None,
        finished_at=str(record["finished_at"]) if record.get("finished_at") is not None else None,
        duration_ms=int(record["duration_ms"]) if record.get("duration_ms") is not None else None,
        error=str(record["error"]) if record.get("error") is not None else None,
        prompt=str(record["prompt"]) if record.get("prompt") is not None else None,
        context=str(record["context"]) if record.get("context") is not None else None,
        command=str(record["command"]) if record.get("command") is not None else None,
        returncode=int(record["returncode"]) if record.get("returncode") is not None else None,
        stdout=str(record["stdout"]) if record.get("stdout") is not None else None,
        stderr=str(record["stderr"]) if record.get("stderr") is not None else None,
        log_path=str(record["log_path"]) if record.get("log_path") is not None else None,
        artifacts=[str(item) for item in record.get("artifacts", []) if isinstance(item, str)],
        attempts=[to_run_attempt_response(item) for item in attempts],
        detail_sections=build_run_detail_sections(record),
    )


def build_run_snapshot_next_action(record: RunRecord) -> str:
    status = str(record.get("status") or "queued")
    cancel_requested = bool(record.get("cancel_requested", False))
    attempt_count = int(record.get("attempt_count") or 0)

    if status == "queued":
        return "等待后台开始执行，然后继续查询任务状态。"

    if status == "running":
        if cancel_requested:
            return "等待当前执行结束并确认最终取消结果。"
        if attempt_count > 0:
            return "继续轮询任务状态；如需定位问题，可查看最近一次尝试的输出或日志。"
        return "继续轮询任务状态，等待首次执行尝试开始。"

    if status == "done":
        return "任务已完成，可查看最终结果、产物或执行日志。"

    if status == "cancelled":
        return "任务已取消；如需继续，可重新创建任务或执行 rerun。"

    return "任务已失败；可查看日志和尝试输出，或决定是否 retry / rerun。"


def to_run_state_snapshot_response(record: RunRecord) -> RunStateSnapshotResponse:
    attempts = get_attempt_records(record)
    latest_attempt = attempts[-1] if attempts else None
    status = str(record.get("status") or "queued")
    return RunStateSnapshotResponse(
        run_id=str(record["run_id"]),
        status=status,
        summary=build_run_summary_text(record),
        next_action=build_run_snapshot_next_action(record),
        terminal=status in {"done", "failed", "cancelled"},
        in_progress=status in {"queued", "running"},
        cancel_requested=bool(record.get("cancel_requested", False)),
        attempt_count=int(record.get("attempt_count") or 0),
        repair_count=int(record.get("repair_count") or 0),
        latest_attempt_number=(
            int(latest_attempt["attempt_number"])
            if latest_attempt is not None and latest_attempt.get("attempt_number") is not None
            else None
        ),
        latest_attempt_status=(
            str(latest_attempt["status"])
            if latest_attempt is not None and latest_attempt.get("status") is not None
            else None
        ),
        latest_attempt_summary=(
            build_attempt_summary(latest_attempt) if latest_attempt is not None else None
        ),
        updated_at=str(record["updated_at"]) if record.get("updated_at") is not None else None,
    )


def to_run_summary_response(record: RunRecord) -> RunSummaryResponse:
    attempts = get_attempt_records(record)
    latest_attempt = attempts[-1] if attempts else None
    prompt_preview = preview_single_line(str(record.get("prompt") or ""), limit=160)
    output_preview = preview_single_line(str(record.get("output") or ""), limit=160)
    error_text = str(record.get("error") or "").strip()
    return RunSummaryResponse(
        run_id=str(record["run_id"]),
        status=str(record["status"]),
        summary=build_run_summary_text(record),
        prompt_preview=prompt_preview or None,
        output_preview=output_preview or None,
        created_at=str(record["created_at"]),
        updated_at=str(record["updated_at"]),
        source_run_id=str(record["source_run_id"]) if record.get("source_run_id") is not None else None,
        trigger_mode=str(record["trigger_mode"]) if record.get("trigger_mode") is not None else None,
        cancel_requested=bool(record.get("cancel_requested", False)),
        generator=str(record["generator"]) if record.get("generator") is not None else None,
        attempt_count=int(record["attempt_count"]) if record.get("attempt_count") is not None else 0,
        repair_attempted=bool(record.get("repair_attempted", False)),
        repair_count=int(record["repair_count"]) if record.get("repair_count") is not None else 0,
        started_at=str(record["started_at"]) if record.get("started_at") is not None else None,
        finished_at=str(record["finished_at"]) if record.get("finished_at") is not None else None,
        duration_ms=int(record["duration_ms"]) if record.get("duration_ms") is not None else None,
        error_preview=preview_single_line(error_text, limit=160) if error_text else None,
        latest_attempt_summary=build_attempt_summary(latest_attempt) if latest_attempt is not None else None,
    )


def format_artifacts(artifacts: list[str]) -> str:
    if not artifacts:
        return "(none)"
    return "\n".join(f"- {artifact}" for artifact in artifacts)

def build_success_output(
    initial_generator: str,
    final_generator: str,
    attempt_count: int,
    repair_count: int,
    result: CommandResult,
    artifacts: list[str],
) -> str:
    stdout = str(result.get("stdout") or "").strip() or "(empty)"
    stderr = str(result.get("stderr") or "").strip()
    returncode = result.get("returncode")
    repair_summary = "未触发自动修复。"
    if repair_count > 0:
        repair_summary = "首次执行失败，自动修复后重试成功。"

    output = (
        "任务执行成功。\n\n"
        f"初始生成方式：{initial_generator}\n"
        f"最终生成方式：{final_generator}\n"
        f"执行尝试次数：{attempt_count}\n"
        f"自动修复次数：{repair_count}\n"
        f"{repair_summary}\n"
        f"最终执行命令：{result.get('command')}\n"
        f"最终返回码：{returncode}\n"
        f"产物：\n{format_artifacts(artifacts)}\n\n"
        f"stdout:\n{stdout}"
    )
    if stderr:
        output += f"\n\nstderr:\n{stderr}"
    return output


def build_failure_output(
    initial_generator: str,
    final_generator: str,
    attempt_count: int,
    repair_count: int,
    result: CommandResult,
    artifacts: list[str],
    repair_note: str | None,
) -> str:
    stdout = str(result.get("stdout") or "").strip() or "(empty)"
    stderr = str(result.get("stderr") or "").strip() or "(empty)"
    error = str(result.get("error") or "").strip()
    returncode = result.get("returncode")

    output = (
        "任务执行失败。\n\n"
        f"初始生成方式：{initial_generator}\n"
        f"最终生成方式：{final_generator}\n"
        f"执行尝试次数：{attempt_count}\n"
        f"自动修复次数：{repair_count}\n"
        f"最终执行命令：{result.get('command') or '(not executed)'}\n"
        f"最终返回码：{returncode}\n"
        f"产物：\n{format_artifacts(artifacts)}\n\n"
        f"stdout:\n{stdout}\n\n"
        f"stderr:\n{stderr}"
    )
    if error:
        output += f"\n\nerror:\n{error}"
    if repair_note:
        output += f"\n\nrepair:\n{repair_note}"
    return output


def build_cancelled_output(
    initial_generator: str,
    final_generator: str,
    attempt_count: int,
    repair_count: int,
    artifacts: list[str],
    cancel_reason: str,
    result: CommandResult | None = None,
) -> str:
    command = str(result.get("command") or "").strip() if result else ""
    stdout = str(result.get("stdout") or "").strip() if result else ""
    stderr = str(result.get("stderr") or "").strip() if result else ""
    returncode = result.get("returncode") if result else None

    output = (
        "任务已取消。\n\n"
        f"初始生成方式：{initial_generator}\n"
        f"最终生成方式：{final_generator}\n"
        f"执行尝试次数：{attempt_count}\n"
        f"自动修复次数：{repair_count}\n"
        f"取消原因：{cancel_reason}\n"
        f"最后执行命令：{command or '(not executed)'}\n"
        f"最后返回码：{returncode}\n"
        f"产物：\n{format_artifacts(artifacts)}"
    )
