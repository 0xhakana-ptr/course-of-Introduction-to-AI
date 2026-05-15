from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from langgraph.graph import END, StateGraph

from ...llm.client import call_llm_sync, llm_is_configured
from ..output.roleplay_agent import emit_roleplay_message, emit_roleplay_state
from ..contracts.workflow_results import WorkflowSummaryResult, invoke_graph_with_result


@dataclass(slots=True)
class SummaryResolution:
    text: str
    source: str = "fallback"
    llm_error: str | None = None


def merge_summary_state(
    state: Mapping[str, object],
    **updates: object,
) -> dict[str, object]:
    return {
        **state,
        **updates,
    }


def resolve_summary_text(
    *,
    fallback_text: str,
    prompt: str,
    system_prompt: str,
    temperature: float = 0.2,
    llm_is_configured_fn: Callable[[], bool] = llm_is_configured,
    call_llm_sync_fn: Callable[..., object] = call_llm_sync,
) -> SummaryResolution:
    summary_text = fallback_text
    summary_source = "fallback"
    llm_error: str | None = None

    if llm_is_configured_fn():
        result = call_llm_sync_fn(
            prompt,
            None,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        candidate = result.output.strip()
        if result.ok and candidate:
            summary_text = candidate
            summary_source = "llm"
        else:
            llm_error = result.error or result.output

    return SummaryResolution(
        text=summary_text,
        source=summary_source,
        llm_error=llm_error,
    )


def build_summary_graph_result(result: Mapping[str, object]) -> WorkflowSummaryResult:
    return WorkflowSummaryResult.from_state(result)


def emit_summary_workflow_with_fallback(
    *,
    invoke_workflow: Callable[[], object],
    log_failed_result: Callable[[WorkflowSummaryResult], None],
    log_exception: Callable[[], None],
    fallback_output: str,
    fallback_node_name: str,
    emit_chat_message: bool = True,
) -> None:
    try:
        result = WorkflowSummaryResult.from_value(invoke_workflow())
        if result.ok:
            return
        log_failed_result(result)
    except Exception:
        log_exception()

    emit_roleplay_message(
        fallback_output,
        default_node_name=fallback_node_name,
        emit_chat_message=emit_chat_message,
    )


def build_prompt_text(lines: Iterable[object]) -> str:
    return "\n".join(str(line) for line in lines)


def build_state_text_resolution(
    state: Mapping[str, object],
    *,
    fallback_text: str,
    prompt: str,
    system_prompt: str,
    text_key: str,
    source_key: str | None = None,
    error_key: str | None = None,
    temperature: float = 0.2,
    llm_is_configured_fn: Callable[[], bool] = llm_is_configured,
    call_llm_sync_fn: Callable[..., object] = call_llm_sync,
) -> dict[str, object]:
    resolution = resolve_summary_text(
        fallback_text=fallback_text,
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        llm_is_configured_fn=llm_is_configured_fn,
        call_llm_sync_fn=call_llm_sync_fn,
    )
    return apply_text_resolution(
        state,
        resolution=resolution,
        text_key=text_key,
        source_key=source_key,
        error_key=error_key,
    )


def build_text_resolution_node(
    *,
    fallback_text_builder: Callable[[Mapping[str, object]], str],
    prompt_builder: Callable[[Mapping[str, object]], str],
    system_prompt: str,
    text_key: str,
    source_key: str | None = None,
    error_key: str | None = None,
    temperature: float = 0.2,
    llm_is_configured_fn: Callable[[], bool] = llm_is_configured,
    call_llm_sync_fn: Callable[..., object] = call_llm_sync,
) -> Callable[[Mapping[str, object]], dict[str, object]]:
    def text_node(state: Mapping[str, object]) -> dict[str, object]:
        return build_state_text_resolution(
            state,
            fallback_text=fallback_text_builder(state),
            prompt=prompt_builder(state),
            system_prompt=system_prompt,
            text_key=text_key,
            source_key=source_key,
            error_key=error_key,
            temperature=temperature,
            llm_is_configured_fn=llm_is_configured_fn,
            call_llm_sync_fn=call_llm_sync_fn,
        )

    return text_node


def apply_text_resolution(
    state: Mapping[str, object],
    *,
    resolution: SummaryResolution,
    text_key: str,
    source_key: str | None = None,
    error_key: str | None = None,
) -> dict[str, object]:
    next_state = merge_summary_state(
        state,
        **{text_key: resolution.text},
    )
    if source_key is not None:
        next_state[source_key] = resolution.source
    if error_key is not None:
        next_state[error_key] = resolution.llm_error
    return next_state


def apply_summary_resolution(
    state: Mapping[str, object],
    *,
    resolution: SummaryResolution,
    output: str,
) -> dict[str, object]:
    next_state = apply_text_resolution(
        state,
        resolution=resolution,
        text_key="summary_text",
        source_key="summary_source",
        error_key="llm_error",
    )
    next_state["output"] = output
    return next_state


def resolve_summary_node_state(
    state: Mapping[str, object],
    *,
    fallback_text: str,
    prompt: str,
    system_prompt: str,
    output_builder: Callable[[SummaryResolution], str],
    temperature: float = 0.2,
    llm_is_configured_fn: Callable[[], bool] = llm_is_configured,
    call_llm_sync_fn: Callable[..., object] = call_llm_sync,
) -> dict[str, object]:
    next_state = build_state_text_resolution(
        state,
        fallback_text=fallback_text,
        prompt=prompt,
        system_prompt=system_prompt,
        text_key="summary_text",
        source_key="summary_source",
        error_key="llm_error",
        temperature=temperature,
        llm_is_configured_fn=llm_is_configured_fn,
        call_llm_sync_fn=call_llm_sync_fn,
    )
    resolution = SummaryResolution(
        text=str(next_state.get("summary_text") or ""),
        source=str(next_state.get("summary_source") or "fallback"),
        llm_error=(
            str(next_state.get("llm_error"))
            if next_state.get("llm_error") is not None
            else None
        ),
    )
    return apply_summary_resolution(
        next_state,
        resolution=resolution,
        output=output_builder(resolution),
    )


def build_summary_initial_state(**state: object) -> dict[str, object]:
    return merge_summary_state(
        {},
        summary_text="",
        output="",
        summary_source="fallback",
        llm_error=None,
        **state,
    )


def emit_summary_roleplay(
    state: Mapping[str, object],
    *,
    default_node_name: str,
) -> dict[str, object]:
    return emit_roleplay_state(
        state,
        default_node_name=default_node_name,
    )


def build_summary_resolution_node(
    *,
    fallback_text_builder: Callable[[Mapping[str, object]], str],
    prompt_builder: Callable[[Mapping[str, object]], str],
    output_builder: Callable[[Mapping[str, object], SummaryResolution], str],
    system_prompt: str,
    temperature: float = 0.2,
    llm_is_configured_fn: Callable[[], bool] = llm_is_configured,
    call_llm_sync_fn: Callable[..., object] = call_llm_sync,
) -> Callable[[Mapping[str, object]], dict[str, object]]:
    def summary_node(state: Mapping[str, object]) -> dict[str, object]:
        return resolve_summary_node_state(
            state,
            fallback_text=fallback_text_builder(state),
            prompt=prompt_builder(state),
            system_prompt=system_prompt,
            output_builder=lambda resolution: output_builder(state, resolution),
            temperature=temperature,
            llm_is_configured_fn=llm_is_configured_fn,
            call_llm_sync_fn=call_llm_sync_fn,
        )

    return summary_node


def build_summary_roleplay_node(
    *,
    default_node_name: str,
) -> Callable[[Mapping[str, object]], dict[str, object]]:
    def roleplay_node(state: Mapping[str, object]) -> dict[str, object]:
        return emit_summary_roleplay(
            state,
            default_node_name=default_node_name,
        )

    return roleplay_node


def run_summary_graph_workflow(graph: object, **state: object) -> WorkflowSummaryResult:
    initial_state = build_summary_initial_state(**state)
    return invoke_graph_with_result(
        graph,
        initial_state=initial_state,
        on_success=build_summary_graph_result,
        on_error=WorkflowSummaryResult.from_error,
    )


def compile_summary_graph(
    state_schema: type[object],
    *,
    summary_node: Callable[[object], object],
    roleplay_node: Callable[[object], object],
):
    workflow = StateGraph(state_schema)
    workflow.add_node("summary_node", summary_node)
    workflow.add_node("roleplay_node", roleplay_node)
    workflow.set_entry_point("summary_node")
    workflow.add_edge("summary_node", "roleplay_node")
    workflow.add_edge("roleplay_node", END)
    return workflow.compile()
