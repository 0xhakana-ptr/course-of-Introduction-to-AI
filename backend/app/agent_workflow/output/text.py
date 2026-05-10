def describe_run_action(action: str) -> str:
    return {
        "create": "创建",
        "inspect": "查看",
        "retry": "重试",
        "rerun": "重新运行",
        "cancel": "取消",
    }.get(action, "处理")


def build_run_creation_output(*, run_id: str, status: str) -> str:
    return build_run_creation_output_with_snapshot(run_id=run_id, status=status)


def build_run_tracking_hint(
    *,
    terminal: bool = False,
    include_attempts: bool = False,
) -> str:
    if terminal:
        return "我会保留这个任务编号；需要看详情时，可以在任务详情里查看最终结果、日志和产物。"
    if include_attempts:
        return "我会继续同步进展；需要排查时，可以在任务详情里查看快照、尝试记录和日志。"
    return "我会继续通过桌宠状态同步进展；需要排查时，可以在任务详情里用这个任务编号查看快照和日志。"


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
        f"run_id: {run_id}",
        f"status: {status}",
    ]
    if snapshot_summary:
        lines.append(f"当前快照: {snapshot_summary}")
    if next_action:
        lines.append(f"下一步: {next_action}")
    lines.extend(["", build_run_tracking_hint()])
    return "\n".join(lines)


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
    return "\n".join(
        [
            "我读取了这个代码任务的当前状态。",
            "",
            f"run_id: {run_id}",
            f"status: {status}",
            f"当前快照: {snapshot_summary}",
            f"下一步: {next_action}",
            "",
            build_run_tracking_hint(include_attempts=True),
        ]
    )


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

    lines = [
        title,
        "",
        f"run_id: {run_id}",
        f"status: {status}",
        f"当前快照: {snapshot_summary}",
    ]
    if latest_attempt_summary:
        lines.append(f"最近一次尝试: {latest_attempt_summary}")
    lines.extend(
        [
            f"下一步: {next_action}",
            "",
            build_run_tracking_hint(include_attempts=True),
        ]
    )
    return "\n".join(lines)


def build_run_terminal_output(
    *,
    run_id: str,
    status: str,
    summary_text: str,
    next_action: str,
) -> str:
    return "\n".join(
        [
            "我读取了这个代码任务的最终结果。",
            "",
            f"run_id: {run_id}",
            f"status: {status}",
            f"最终总结: {summary_text}",
            f"下一步: {next_action}",
            "",
            build_run_tracking_hint(terminal=True),
        ]
    )


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
        lines.append(f"source_run_id: {source_run_id}")
    lines.extend(
        [
            f"run_id: {run_id}",
            f"status: {status}",
            f"当前快照: {snapshot_summary}",
            f"下一步: {next_action}",
            "",
            build_run_tracking_hint(include_attempts=True),
        ]
    )
    return "\n".join(lines)


def build_run_control_failure_output(
    *,
    action: str,
    run_id: str | None,
    error: str,
) -> str:
    lines = [f"我暂时没能完成这个代码任务的{describe_run_action(action)}操作。"]
    if run_id:
        lines.extend(["", f"run_id: {run_id}"])
    lines.extend(["", f"原因: {error}"])
    return "\n".join(lines)
