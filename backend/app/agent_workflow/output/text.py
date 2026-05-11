import re


RUN_METADATA_LINE_PATTERN = re.compile(
    r"^\s*(?:source_)?run_id\s*:|^\s*status\s*:|^\s*状态\s*:\s*(?:queued|running|done|failed|cancelled)\s*$",
    re.IGNORECASE,
)


def describe_run_action(action: str) -> str:
    return {
        "create": "创建",
        "inspect": "查看",
        "retry": "重试",
        "rerun": "重新运行",
        "cancel": "取消",
    }.get(action, "处理")


def sanitize_user_visible_run_output(output: str) -> str:
    lines: list[str] = []
    previous_blank = False
    for raw_line in str(output or "").splitlines():
        line = raw_line.rstrip()
        if RUN_METADATA_LINE_PATTERN.search(line):
            continue
        if "可以在任务详情中使用这个 run_id 查看结果、日志和产物" in line:
            line = "需要看细节时，可以打开任务详情查看结果、日志和产物。"

        is_blank = not line.strip()
        if is_blank and (previous_blank or not lines):
            continue
        lines.append(line)
        previous_blank = is_blank

    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _compact_lines(lines: list[str]) -> str:
    compacted: list[str] = []
    previous_blank = False
    for line in lines:
        normalized = str(line or "").rstrip()
        is_blank = not normalized
        if is_blank and (previous_blank or not compacted):
            continue
        compacted.append(normalized)
        previous_blank = is_blank
    while compacted and not compacted[-1]:
        compacted.pop()
    return "\n".join(compacted)


def _status_phrase(status: str) -> str:
    return {
        "queued": "现在还在排队，后台会接着执行。",
        "running": "现在正在后台执行。",
        "done": "现在已经完成。",
        "failed": "现在执行失败了。",
        "cancelled": "现在已经取消。",
    }.get(str(status or "").strip(), "当前状态已经更新。")


def _append_progress_lines(
    lines: list[str],
    *,
    status: str | None = None,
    snapshot_summary: str | None = None,
    next_action: str | None = None,
    latest_attempt_summary: str | None = None,
) -> None:
    if status:
        lines.append(_status_phrase(status))
    if snapshot_summary:
        lines.append(f"目前我看到：{snapshot_summary}")
    if latest_attempt_summary:
        lines.append(f"最近一次尝试：{latest_attempt_summary}")
    if next_action:
        lines.append(f"接下来：{next_action}")


def build_run_creation_output(*, run_id: str, status: str) -> str:
    return build_run_creation_output_with_snapshot(run_id=run_id, status=status)


def build_run_tracking_hint(
    *,
    terminal: bool = False,
    include_attempts: bool = False,
) -> str:
    if terminal:
        return "我已经把这个任务记录到任务详情里；需要看细节时，可以查看最终结果、日志和产物。"
    if include_attempts:
        return "我会继续同步进展；需要排查时，可以在任务详情里查看尝试记录和日志。"
    return "我会继续通过桌宠状态同步进展；需要排查时，可以打开任务详情查看日志和产物。"


def build_run_creation_output_with_snapshot(
    *,
    run_id: str,
    status: str,
    snapshot_summary: str | None = None,
    next_action: str | None = None,
) -> str:
    lines = [
        "我已经创建了代码任务，并交给后端执行。",
        "",
    ]
    _append_progress_lines(
        lines,
        status=status,
        snapshot_summary=snapshot_summary,
        next_action=next_action,
    )
    lines.extend(["", build_run_tracking_hint()])
    return _compact_lines(lines)


def build_unknown_intent_output(prompt: str) -> str:
    return (
        "我这次没有完全听懂你的意思。\n\n"
        f"你输入的内容是：{prompt}\n\n"
        "如果你只是想聊天，可以直接继续说；如果你想让我处理代码任务，可以补充目标、文件、报错或 run_id。"
    )


def build_run_snapshot_output(
    *,
    run_id: str,
    status: str,
    snapshot_summary: str,
    next_action: str,
) -> str:
    lines = ["我读取了这个代码任务的当前状态。", ""]
    _append_progress_lines(
        lines,
        status=status,
        snapshot_summary=snapshot_summary,
        next_action=next_action,
    )
    lines.extend(["", build_run_tracking_hint(include_attempts=True)])
    return _compact_lines(lines)


def build_run_snapshot_progress_output(
    *,
    run_id: str,
    status: str,
    snapshot_summary: str,
    next_action: str,
    latest_attempt_summary: str | None = None,
    cancel_requested: bool = False,
) -> str:
    if status == "queued":
        title = "我读取了这个代码任务的中间状态，当前还在排队。"
    elif cancel_requested:
        title = "我读取了这个代码任务的中间状态，当前已经收到取消请求。"
    else:
        title = "我读取了这个代码任务的中间状态，当前正在执行。"

    lines = [title, ""]
    _append_progress_lines(
        lines,
        status=None,
        snapshot_summary=snapshot_summary,
        latest_attempt_summary=latest_attempt_summary,
        next_action=next_action,
    )
    lines.extend(["", build_run_tracking_hint(include_attempts=True)])
    return _compact_lines(lines)


def build_run_terminal_output(
    *,
    run_id: str,
    status: str,
    summary_text: str,
    next_action: str,
) -> str:
    lines = ["我读取了这个代码任务的最终结果。", ""]
    _append_progress_lines(
        lines,
        status=status,
        snapshot_summary=f"最终总结：{summary_text}",
        next_action=next_action,
    )
    lines.extend(["", build_run_tracking_hint(terminal=True)])
    return _compact_lines(lines)


def build_run_control_output(
    *,
    action: str,
    run_id: str,
    status: str,
    snapshot_summary: str,
    next_action: str,
    source_run_id: str | None = None,
) -> str:
    title = {
        "retry": "我已为这个代码任务创建重试任务。",
        "rerun": "我已为这个代码任务创建重新运行任务。",
        "cancel": "我已处理这个代码任务的取消请求。",
    }.get(action, "我已处理这个代码任务的控制请求。")
    lines = [title, ""]
    if source_run_id:
        lines.append("原任务已经记录在任务详情里。")
    _append_progress_lines(
        lines,
        status=status,
        snapshot_summary=snapshot_summary,
        next_action=next_action,
    )
    lines.extend(["", build_run_tracking_hint(include_attempts=True)])
    return _compact_lines(lines)


def build_run_control_failure_output(
    *,
    action: str,
    run_id: str | None,
    error: str,
) -> str:
    lines = [f"我暂时没能完成这个代码任务的{describe_run_action(action)}操作。"]
    lines.extend(["", f"原因: {error}"])
    if run_id:
        lines.extend(["", "相关任务仍保留在任务详情里，可以稍后继续查看。"])
    return _compact_lines(lines)
