from ..services.run_action.types import RetryGuidance


RETRY_GUIDANCE_BY_NODE: dict[str, str] = {
    "task_retry_done": "这轮自动修复后的尝试已经成功，我会整理最终结果。",
    "task_retry_cancelled": "这轮自动修复后的尝试已取消，我会停止后续执行并整理当前状态。",
    "task_retry_cancelled_requested": "系统已收到取消请求，我会停止后续修复并整理当前状态。",
    "task_retry_failed": "这轮自动修复后的尝试仍未成功，我会结束当前任务并整理失败原因。",
    "task_retry_repairing": "我会继续分析这次失败，并决定是否进入下一轮自动修复。",
}


def build_retry_guidance(node_name: str) -> RetryGuidance:
    next_action = RETRY_GUIDANCE_BY_NODE.get(node_name)
    if next_action is None:
        raise KeyError(f"unknown retry guidance node: {node_name}")
    return RetryGuidance(
        node_name=node_name,
        next_action=next_action,
    )


def maybe_build_retry_guidance_for_repair_decision(
    *,
    current_generator: str,
    should_attempt_repair: bool,
) -> RetryGuidance | None:
    if current_generator != "llm_repair":
        return None

    return build_retry_guidance(
        "task_retry_repairing" if should_attempt_repair else "task_retry_failed"
    )
