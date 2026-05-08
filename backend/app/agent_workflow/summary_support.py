from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from langgraph.graph import END, StateGraph

from ..llm.client import call_llm_sync, llm_is_configured
from .roleplay import emit_roleplay_chat
from .workflow_results import WorkflowSummaryResult


@dataclass(slots=True)
class SummaryResolution:
    text: str
    source: str = "fallback"
    llm_error: str | None = None


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


def build_prompt_text(lines: Iterable[object]) -> str:
    return "\n".join(str(line) for line in lines)


def apply_text_resolution(
    state: Mapping[str, object],
    *,
    resolution: SummaryResolution,
    text_key: str,
    source_key: str | None = None,
    error_key: str | None = None,
) -> dict[str, object]:
    next_state = {
        **state,
        text_key: resolution.text,
    }
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
    resolution = resolve_summary_text(
        fallback_text=fallback_text,
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        llm_is_configured_fn=llm_is_configured_fn,
        call_llm_sync_fn=call_llm_sync_fn,
    )
    return apply_summary_resolution(
        state,
        resolution=resolution,
        output=output_builder(resolution),
    )


def build_summary_initial_state(**state: object) -> dict[str, object]:
    return {
        "summary_text": "",
        "output": "",
        "summary_source": "fallback",
        "llm_error": None,
        **state,
    }


def emit_summary_roleplay(
    state: Mapping[str, object],
    *,
    default_node_name: str,
) -> dict[str, object]:
    emit_roleplay_chat(
        str(state.get("output") or ""),
        node_name=str(state.get("node_name") or default_node_name),
        emit_chat_message=bool(state.get("emit_chat_message", True)),
    )
    return dict(state)


def run_summary_graph_workflow(graph: object, **state: object) -> WorkflowSummaryResult:
    initial_state = build_summary_initial_state(**state)
    result = graph.invoke(initial_state)
    return build_summary_graph_result(result)


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
