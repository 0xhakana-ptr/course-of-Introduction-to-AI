from ..contracts.workflow_nodes import (
    TASK_RETRY_CANCELLED_NODE,
    TASK_RETRY_CANCELLED_REQUESTED_NODE,
    TASK_RETRY_DONE_NODE,
    TASK_RETRY_FAILED_NODE,
    TASK_RETRY_REPAIRING_NODE,
)
from ..types.run_types import RetryGuidance
from ..contracts.workflow_results import WorkflowRepairResult


RETRY_GUIDANCE_BY_NODE: dict[str, str] = {
    TASK_RETRY_DONE_NODE: "这轮自动修复后的尝试已经成功，我会整理最终结果。",
    TASK_RETRY_CANCELLED_NODE: "这轮自动修复后的尝试已取消，我会停止后续执行并整理当前状态。",
    TASK_RETRY_CANCELLED_REQUESTED_NODE: "系统已收到取消请求，我会停止后续修复并整理当前状态。",
    TASK_RETRY_FAILED_NODE: "这轮自动修复后的尝试仍未成功，我会结束当前任务并整理失败原因。",
    TASK_RETRY_REPAIRING_NODE: "我会继续分析这次失败，并决定是否进入下一轮自动修复。",
}


def build_retry_guidance(node_name: str) -> RetryGuidance:
    next_action = RETRY_GUIDANCE_BY_NODE.get(node_name)
    if next_action is None:
        raise KeyError(f"unknown retry guidance node: {node_name}")
    return RetryGuidance(
        node_name=node_name,
        next_action=next_action,
    )


def build_terminal_retry_guidance(
    *,
    current_generator: str,
    cancelled: bool = False,
    ok: bool = False,
    cancel_requested: bool = False,
) -> RetryGuidance | None:
    if current_generator != "llm_repair":
        return None
    if cancelled:
        return build_retry_guidance(TASK_RETRY_CANCELLED_NODE)
    if ok:
        return build_retry_guidance(TASK_RETRY_DONE_NODE)
    if cancel_requested:
        return build_retry_guidance(TASK_RETRY_CANCELLED_REQUESTED_NODE)
    return None


def maybe_build_retry_guidance_for_repair_decision(
    *,
    current_generator: str,
    should_attempt_repair: bool,
) -> RetryGuidance | None:
    if current_generator != "llm_repair":
        return None

    return build_retry_guidance(
        TASK_RETRY_REPAIRING_NODE if should_attempt_repair else TASK_RETRY_FAILED_NODE
    )


def resolve_retry_guidance_from_repair_result(
    repair_workflow: WorkflowRepairResult | object,
) -> RetryGuidance:
    normalized_result = WorkflowRepairResult.from_value(repair_workflow)
    retry_guidance = normalized_result.retry_guidance
    if isinstance(retry_guidance, RetryGuidance):
        return retry_guidance

    retry_node_name = normalized_result.retry_node_name
    if isinstance(retry_node_name, str) and retry_node_name:
        return build_retry_guidance(retry_node_name)

    return build_retry_guidance(
        TASK_RETRY_REPAIRING_NODE
        if normalized_result.should_attempt_repair
        else TASK_RETRY_FAILED_NODE
    )
