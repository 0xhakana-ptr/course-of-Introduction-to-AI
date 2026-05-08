from typing import TypedDict

from langgraph.graph import END, StateGraph

from ..llm.client import call_llm_sync
from ..schemas import INTENT_TYPE
from ..services.chat_action.intent import detect_intent
from ..services.run_interface import create_run
from .agent_support import (
    build_chat_result_state,
    build_coding_requested_state,
    build_routed_state,
    build_run_creation_failure_state,
    build_run_creation_success_state,
    build_unknown_intent_state,
    emit_agent_roleplay_state,
    invoke_agent_graph,
    select_agent_next_node,
)
from .workflow_results import WorkflowAgentResult


class AgentState(TypedDict, total=False):
    user_input: str
    context: str | None
    session_id: str | None
    intent: INTENT_TYPE
    emit_chat_message: bool
    output: str
    error: str | None
    run_id: str | None
    run_status: str | None
    ui_status: str | None


def router_node(state: AgentState) -> AgentState:
    prompt = state.get("user_input", "")
    intent = state.get("intent") or detect_intent(prompt)
    return build_routed_state(state, intent=intent)


def route_by_intent(state: AgentState) -> str:
    return select_agent_next_node(state.get("intent"))


def chat_node(state: AgentState) -> AgentState:
    prompt = state.get("user_input", "")
    result = call_llm_sync(prompt, state.get("context"))
    return build_chat_result_state(
        state,
        output=result.output,
        error=result.error if not result.ok else None,
    )


def coding_node(state: AgentState) -> AgentState:
    return build_coding_requested_state(state)


def run_tool_node(state: AgentState) -> AgentState:
    try:
        run = create_run(
            prompt=state.get("user_input", ""),
            context=state.get("context"),
        )
    except Exception as exc:
        return build_run_creation_failure_state(state, error=str(exc))

    return build_run_creation_success_state(
        state,
        run_id=run.run_id,
        status=run.status,
    )


def unknown_node(state: AgentState) -> AgentState:
    prompt = state.get("user_input", "")
    return build_unknown_intent_state(state, prompt=prompt)


def roleplay_node(state: AgentState) -> AgentState:
    return emit_agent_roleplay_state(state)


def create_agent_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("router", router_node)
    workflow.add_node("chat_node", chat_node)
    workflow.add_node("coding_node", coding_node)
    workflow.add_node("run_tool_node", run_tool_node)
    workflow.add_node("unknown_node", unknown_node)
    workflow.add_node("roleplay_node", roleplay_node)

    workflow.set_entry_point("router")
    workflow.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "chat_node": "chat_node",
            "coding_node": "coding_node",
            "unknown_node": "unknown_node",
        },
    )
    workflow.add_edge("chat_node", "roleplay_node")
    workflow.add_edge("coding_node", "run_tool_node")
    workflow.add_edge("run_tool_node", "roleplay_node")
    workflow.add_edge("unknown_node", "roleplay_node")
    workflow.add_edge("roleplay_node", END)

    return workflow.compile()


agent_graph = create_agent_graph()


def run_agent(
    prompt: str,
    context: str | None = None,
    *,
    session_id: str | None = None,
    intent: INTENT_TYPE | None = None,
    emit_chat_message: bool = True,
) -> WorkflowAgentResult:
    return invoke_agent_graph(
        agent_graph,
        prompt=prompt,
        context=context,
        session_id=session_id,
        intent=intent,
        emit_chat_message=emit_chat_message,
    )
