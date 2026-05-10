from collections.abc import Callable, Mapping

from .run_state import WorkflowRunStateSnapshot


def resolve_target_run_id(state: Mapping[str, object]) -> str:
    return WorkflowRunStateSnapshot.from_state(state).resolved_target_run_id()


def resolve_run_snapshot_fields(
    *,
    get_snapshot: Callable[[str], object | None],
    run_id: str,
    fallback_status: str,
    fallback_summary: str,
    fallback_next_action: str,
) -> tuple[str, str, str]:
    snapshot = get_snapshot(run_id)
    if snapshot is None:
        return fallback_status, fallback_summary, fallback_next_action
    return snapshot.status, snapshot.summary, snapshot.next_action


def resolve_terminal_run_summary(
    *,
    run_id: str,
    snapshot_summary: str,
    load_run: Callable[[str], object | None],
    summarize_run: Callable[..., object],
) -> tuple[str, str | None]:
    summary_text = snapshot_summary
    output: str | None = None
    run = load_run(run_id)
    if run is None:
        return summary_text, output

    summary_result = summarize_run(
        run.model_dump(),
        emit_chat_message=False,
    )
    result_output = str(getattr(summary_result, "output", "") or "").strip()
    result_summary = str(getattr(summary_result, "summary_text", "") or "").strip()
    if getattr(summary_result, "ok", False) and result_output:
        output = result_output
    if result_summary:
        summary_text = result_summary
    return summary_text, output


def execute_run_control_action(
    *,
    action: str,
    target_run_id: str,
    retry_action: Callable[[str], object],
    rerun_action: Callable[[str], object],
    cancel_action: Callable[[str], object],
) -> object:
    if action == "retry":
        return retry_action(target_run_id)
    if action == "rerun":
        return rerun_action(target_run_id)
    if action == "cancel":
        return cancel_action(target_run_id)
    raise ValueError("当前请求不属于支持的 run 控制动作。")


def build_run_control_fallback_next_action(action: str) -> str:
    if action in {"retry", "rerun"}:
        return "等待后台开始执行，然后继续查询任务状态。"
    return "任务状态已更新，可继续查询任务快照确认最终结果。"
