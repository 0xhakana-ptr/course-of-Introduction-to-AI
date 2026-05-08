from typing import TypedDict

from ..llm.client import call_llm_sync, llm_is_configured
from ..services.run_action.formatters import (
    build_retry_outcome_chat_text,
    preview_single_line,
)
from .summary_support import (
    SummaryResolution,
    build_prompt_text,
    build_summary_resolution_node,
    build_summary_roleplay_node,
    compile_summary_graph,
    run_summary_graph_workflow,
)
from .workflow_results import WorkflowSummaryResult


ATTEMPT_SUMMARY_SYSTEM_PROMPT = """你是本地 AI 桌宠后端中的尝试结果总结节点。

你会收到一次自动修复后的重试结果摘要，以及下一步动作提示。
请生成一条简洁、自然、面向用户的中文说明。

要求：
1. 只用 1 到 2 句中文。
2. 说明这轮自动修复后的尝试结果。
3. 简要带出接下来会发生什么。
4. 不要输出列表、标题、Markdown 或代码块。
"""


class AttemptSummaryState(TypedDict, total=False):
    run_id: str
    attempt_summary: str
    next_action: str
    node_name: str
    emit_chat_message: bool
    summary_text: str
    output: str
    summary_source: str
    llm_error: str | None


def build_attempt_summary_prompt(state: AttemptSummaryState) -> str:
    return build_prompt_text(
        [
            "请根据下面的信息，生成一条面向用户的简短中文说明。",
            f"run_id: {state.get('run_id') or '(none)'}",
            f"attempt_summary: {state.get('attempt_summary') or '(none)'}",
            f"next_action: {state.get('next_action') or '(none)'}",
        ]
    )


def _build_attempt_summary_output(
    state: AttemptSummaryState,
    resolution: SummaryResolution,
) -> str:
    return build_retry_outcome_chat_text(
        run_id=str(state.get("run_id") or ""),
        attempt_summary=str(state.get("attempt_summary") or "").strip(),
        next_action=str(state.get("next_action") or "").strip(),
        summary_text=preview_single_line(resolution.text, limit=220),
    )


summary_node = build_summary_resolution_node(
    fallback_text_builder=lambda state: str(state.get("attempt_summary") or "").strip(),
    prompt_builder=build_attempt_summary_prompt,
    output_builder=_build_attempt_summary_output,
    system_prompt=ATTEMPT_SUMMARY_SYSTEM_PROMPT,
    llm_is_configured_fn=lambda: llm_is_configured(),
    call_llm_sync_fn=lambda *args, **kwargs: call_llm_sync(*args, **kwargs),
)


roleplay_node = build_summary_roleplay_node(default_node_name="task_retry_done")


def create_attempt_summary_graph():
    return compile_summary_graph(
        AttemptSummaryState,
        summary_node=summary_node,
        roleplay_node=roleplay_node,
    )


attempt_summary_graph = create_attempt_summary_graph()


def summarize_retry_outcome(
    *,
    run_id: str,
    attempt_summary: str,
    next_action: str,
    node_name: str,
    emit_chat_message: bool = False,
) -> WorkflowSummaryResult:
    return run_summary_graph_workflow(
        attempt_summary_graph,
        run_id=run_id,
        attempt_summary=attempt_summary,
        next_action=next_action,
        node_name=node_name,
        emit_chat_message=emit_chat_message,
    )
