from ..core.limits import (
    SUMMARY_OUTCOME_MAX,
    SUMMARY_PREVIEW_MAX,
    SUMMARY_RUN_MAX,
    SUMMARY_SINGLE_LINE_MAX,
)
from ..core.text_utils import build_preview
from .types.run_types import (
    AttemptRecord,
    CommandResult,
    RunRecord,
    SUMMARY_PREVIEW_LIMIT,
)


def preview_single_line(text: str, limit: int = SUMMARY_PREVIEW_LIMIT) -> str:
    return build_preview(text, limit=limit)

def build_run_chat_text(
    *,
    title: str,
    run_id: str,
    fields: list[tuple[str, str]],
    include_run_link: bool = True,
) -> str:
    lines = [title]
    lines.extend(
        field_text
        for label, value in fields
        if value and (field_text := _format_user_chat_field(label, value))
    )
    if include_run_link and run_id:
        lines.append("需要看细节时，可以打开任务详情查看结果、日志和产物。")
    return "\n".join(lines)

def _format_user_chat_field(label: str, value: str) -> str:
    normalized_label = str(label or "").strip()
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return ""
    if normalized_label == "状态":
        status_text = {
            "queued": "还在排队",
            "running": "正在执行",
            "done": "已经完成",
            "failed": "执行失败",
            "cancelled": "已经取消",
        }.get(normalized_value, normalized_value)
        return f"当前状态: {status_text}"
    return f"{normalized_label}: {normalized_value}"

def describe_generator(generator: str) -> str:
    generator_map = {
        "template": "本地模板",
        "llm": "LLM 生成",
        "llm_repair": "LLM 修复",
    }
    return generator_map.get(generator, generator)

def get_attempt_records(record: RunRecord) -> list[AttemptRecord]:
    attempts = [
        item
        for item in record.get("attempts", [])
        if isinstance(item, dict) and item.get("attempt_number") is not None
    ]
    attempts.sort(key=lambda item: int(item.get("attempt_number") or 0))
    return attempts

def build_attempt_summary(record: AttemptRecord) -> str:
    attempt_number = int(record.get("attempt_number") or 0)
    repair_round = int(record.get("repair_round") or 0)
    status = str(record.get("status") or "running")
    generator = describe_generator(str(record.get("generator") or "unknown"))
    prefix = f"第 {attempt_number} 次尝试"
    if repair_round > 0:
        prefix += f"（第 {repair_round} 轮自动修复后，{generator}）"
    else:
        prefix += f"（{generator}）"

    returncode = record.get("returncode")
    duration_ms = record.get("duration_ms")
    suffix_parts: list[str] = []
    if isinstance(returncode, int):
        suffix_parts.append(f"返回码 {returncode}")
    if isinstance(duration_ms, int):
        suffix_parts.append(f"耗时 {duration_ms} ms")
    suffix = f"；{'，'.join(suffix_parts)}" if suffix_parts else ""

    if status == "running":
        return f"{prefix}：正在执行。"

    if status == "done":
        stdout = str(record.get("stdout") or "").strip()
        if stdout:
            return f"{prefix}：执行成功{suffix}。输出摘要：{preview_single_line(stdout)}"
        return f"{prefix}：执行成功{suffix}。"

    if status == "cancelled":
        cancel_text = (
            str(record.get("error") or "").strip()
            or str(record.get("stderr") or "").strip()
            or "任务已取消"
        )
        return f"{prefix}：执行已取消{suffix}。说明：{preview_single_line(cancel_text)}"

    failure_text = (
        str(record.get("error") or "").strip()
        or str(record.get("stderr") or "").strip()
        or str(record.get("stdout") or "").strip()
        or "未提供更多错误信息"
    )
    return f"{prefix}：执行失败{suffix}。错误摘要：{preview_single_line(failure_text)}"

def build_attempt_record_snapshot(
    *,
    attempt_number: int,
    generator: str,
    repair_round: int,
    result: CommandResult,
) -> AttemptRecord:
    status = "running"
    if bool(result.get("cancelled")):
        status = "cancelled"
    elif bool(result.get("ok")):
        status = "done"
    else:
        status = "failed"

    return {
        "attempt_number": attempt_number,
        "generator": generator,
        "repair_round": repair_round,
        "status": status,
        "source_file_name": result.get("source_file_name"),
        "attempt_file_name": result.get("attempt_file_name"),
        "script_rel_path": result.get("script_rel_path"),
        "command": result.get("command"),
        "cwd": result.get("cwd"),
        "returncode": result.get("returncode"),
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "error": result.get("error"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
        "duration_ms": result.get("duration_ms"),
    }

def build_repair_retry_feedback_text(
    *,
    run_id: str,
    attempt_summary: str,
    analysis_note: str | None,
    next_repair_round: int,
) -> str:
    analysis_text = preview_single_line(
        str(analysis_note or "我已经拿到了这次失败的关键信息。"),
        limit=SUMMARY_SINGLE_LINE_MAX,
    )
    return build_run_chat_text(
        title="我先同步一下这次代码任务的进展。",
        run_id=run_id,
        fields=[
            ("当前结果", attempt_summary),
            ("分析", analysis_text),
            ("下一步", f"我会继续进行第 {next_repair_round} 轮自动修复，然后再次尝试执行。"),
        ],
    )

def build_retry_outcome_chat_text(
    *,
    run_id: str,
    attempt_summary: str,
    next_action: str,
    summary_text: str | None = None,
) -> str:
    outcome_text = preview_single_line(summary_text or attempt_summary, limit=SUMMARY_OUTCOME_MAX)
    return build_run_chat_text(
        title="我继续同步一下自动修复后的这轮结果。",
        run_id=run_id,
        fields=[
            ("本轮结果", outcome_text),
            ("下一步", next_action),
        ],
    )

def build_run_summary_text(record: RunRecord) -> str:
    status = str(record.get("status") or "queued")
    cancel_requested = bool(record.get("cancel_requested", False))
    generator = describe_generator(str(record.get("generator") or "unknown"))
    attempt_count = int(record.get("attempt_count") or 0)
    repair_count = int(record.get("repair_count") or 0)
    attempts = get_attempt_records(record)
    latest_attempt = attempts[-1] if attempts else None

    if status == "queued":
        return "任务已创建，等待后台执行。"
    if status == "running":
        if cancel_requested:
            if latest_attempt is not None:
                return f"任务已收到取消请求，正在结束执行。最近一次尝试：{build_attempt_summary(latest_attempt)}"
            return "任务已收到取消请求，正在结束执行。"
        if latest_attempt is not None:
            return f"任务正在执行中。最近一次尝试：{build_attempt_summary(latest_attempt)}"
        return "任务正在后台执行。"
    if status == "done":
        latest_attempt_summary = (
            build_attempt_summary(latest_attempt) if latest_attempt is not None else "任务执行成功。"
        )
        return (
            f"任务执行成功，使用 {generator}，共尝试 {attempt_count} 次，"
            f"自动修复 {repair_count} 次。{latest_attempt_summary}"
        )

    if status == "cancelled":
        cancel_preview = preview_single_line(str(record.get("error") or "任务已取消"))
        if attempt_count == 0:
            return f"任务已取消，尚未开始执行。说明：{cancel_preview}"
        return (
            f"任务已取消，使用 {generator}，共尝试 {attempt_count} 次，"
            f"自动修复 {repair_count} 次。说明：{cancel_preview}"
        )

    error_preview = preview_single_line(str(record.get("error") or "未提供更多错误信息"))
    return (
        f"任务执行失败，使用 {generator}，共尝试 {attempt_count} 次，"
        f"自动修复 {repair_count} 次。错误摘要：{error_preview}"
    )

def build_run_completion_chat_text(
    record: RunRecord,
    *,
    summary_text: str | None = None,
) -> str:
    run_id = str(record.get("run_id") or "").strip()
    status = str(record.get("status") or "queued")
    status_title = {
        "done": "代码任务已经完成。",
        "failed": "代码任务执行失败。",
        "cancelled": "代码任务已经取消。",
        "running": "代码任务仍在执行中。",
        "queued": "代码任务还在排队中。",
    }.get(status, "代码任务状态已更新。")

    summary = preview_single_line(summary_text or build_run_summary_text(record), limit=SUMMARY_RUN_MAX)
    return build_run_chat_text(
        title=status_title,
        run_id=run_id,
        fields=[
            ("状态", status),
            ("摘要", summary),
        ],
    )
