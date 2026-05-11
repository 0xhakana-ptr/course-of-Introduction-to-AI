from typing import TypedDict

from ...llm.client import call_llm_sync, llm_is_configured
from ...services.run_action.formatters import (
    build_attempt_summary,
    build_run_completion_chat_text,
    build_run_summary_text,
    get_attempt_records,
    preview_single_line,
)
from ...services.run_action.types import RunRecord
from .support import (
    SummaryResolution,
    build_prompt_text,
    build_summary_resolution_node,
    build_summary_roleplay_node,
    compile_summary_graph,
    run_summary_graph_workflow,
)
from ..contracts.workflow_nodes import AGENT_ROLEPLAY_NODE, TASK_DONE_NODE
from ..contracts.workflow_results import WorkflowSummaryResult


RUN_SUMMARY_SYSTEM_PROMPT = """你是本地 AI 桌宠后端中的总结节点。

你的任务不是重新执行代码，而是根据已经完成的 run 记录，写一句简洁、自然、面向用户的中文总结。

要求：
1. 明确任务是成功、失败还是取消。
2. 如果有自动修复，尽量简要提到。
3. 如果有明显输出结果或错误原因，可以用一句短语概括。
4. 不要输出 Markdown 列表，不要输出代码块。
5. 不要输出 run_id、status、接口路径、日志路径等工程字段。
6. 尽量控制在 1 到 2 句内。
"""


class RunSummaryState(TypedDict, total=False):
    run_record: RunRecord
    node_name: str
    emit_chat_message: bool
    summary_text: str
    output: str
    summary_source: str
    llm_error: str | None


def build_run_summary_prompt(record: RunRecord) -> str:
    status = str(record.get("status") or "unknown")
    run_id = str(record.get("run_id") or "").strip()
    prompt_preview = preview_single_line(str(record.get("prompt") or ""), limit=160) or "(empty)"
    output_preview = preview_single_line(str(record.get("output") or ""), limit=200) or "(empty)"
    error_preview = preview_single_line(str(record.get("error") or ""), limit=200) or "(none)"
    attempts = get_attempt_records(record)
    latest_attempt = attempts[-1] if attempts else None
    latest_attempt_summary = (
        build_attempt_summary(latest_attempt) if latest_attempt is not None else "(none)"
    )

    return build_prompt_text(
        [
            "请根据下面的 run 信息，生成一条面向用户的简短中文总结。",
            f"run_id: {run_id or '(none)'}",
            f"status: {status}",
            f"attempt_count: {int(record.get('attempt_count') or 0)}",
            f"repair_count: {int(record.get('repair_count') or 0)}",
            f"generator: {str(record.get('generator') or 'unknown')}",
            f"prompt_preview: {prompt_preview}",
            f"summary: {build_run_summary_text(record)}",
            f"latest_attempt_summary: {latest_attempt_summary}",
            f"output_preview: {output_preview}",
            f"error_preview: {error_preview}",
        ]
    )


def _build_run_summary_output(
    state: RunSummaryState,
    resolution: SummaryResolution,
) -> str:
    return build_run_completion_chat_text(
        state["run_record"],
        summary_text=resolution.text,
    )


summary_node = build_summary_resolution_node(
    fallback_text_builder=lambda state: build_run_summary_text(state["run_record"]),
    prompt_builder=lambda state: build_run_summary_prompt(state["run_record"]),
    output_builder=_build_run_summary_output,
    system_prompt=RUN_SUMMARY_SYSTEM_PROMPT,
    llm_is_configured_fn=lambda: llm_is_configured(),
    call_llm_sync_fn=lambda *args, **kwargs: call_llm_sync(*args, **kwargs),
)


roleplay_node = build_summary_roleplay_node(default_node_name=AGENT_ROLEPLAY_NODE)


def create_run_summary_graph():
    return compile_summary_graph(
        RunSummaryState,
        summary_node=summary_node,
        roleplay_node=roleplay_node,
    )


run_summary_graph = create_run_summary_graph()


def summarize_run_record(
    record: RunRecord,
    *,
    node_name: str = TASK_DONE_NODE,
    emit_chat_message: bool = False,
) -> WorkflowSummaryResult:
    return run_summary_graph_workflow(
        run_summary_graph,
        run_record=record,
        node_name=node_name,
        emit_chat_message=emit_chat_message,
    )
