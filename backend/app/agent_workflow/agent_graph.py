from typing import TypedDict

from langgraph.graph import END, StateGraph

from ..llm.client import call_llm_sync
from ..messaging.message_sender import message_sender
from ..schemas import INTENT_TYPE
from ..services.chat_action.intent import detect_intent
from ..services.run_interface import create_run


class AgentState(TypedDict, total=False):
    user_input: str
    context: str | None
    session_id: str | None
    intent: INTENT_TYPE
    output: str
    error: str | None
    run_id: str | None
    run_status: str | None
    ui_status: str | None


def router_node(state: AgentState) -> AgentState:
    prompt = state.get("user_input", "")
    intent = state.get("intent") or detect_intent(prompt)
    return {
        **state,
        "intent": intent,
        "ui_status": "routed",
    }


def route_by_intent(state: AgentState) -> str:
    intent = state.get("intent")
    if intent == "coding":
        return "coding_node"
    if intent == "chat":
        return "chat_node"
    return "unknown_node"


def chat_node(state: AgentState) -> AgentState:
    prompt = state.get("user_input", "")
    result = call_llm_sync(prompt, state.get("context"))
    return {
        **state,
        "output": result.output,
        "error": result.error if not result.ok else None,
        "ui_status": "chat_done" if result.ok else "chat_failed",
    }


def coding_node(state: AgentState) -> AgentState:
    return {
        **state,
        "ui_status": "coding_requested",
    }


def run_tool_node(state: AgentState) -> AgentState:
    try:
        run = create_run(
            prompt=state.get("user_input", ""),
            context=state.get("context"),
        )
    except Exception as exc:
        return {
            **state,
            "output": f"代码任务创建失败：{exc}",
            "error": str(exc),
            "ui_status": "run_create_failed",
        }

    output = (
        "已通过 LangGraph 创建代码任务，并交给 `/runs` 链路处理。\n\n"
        f"run_id: {run.run_id}\n"
        f"status: {run.status}\n\n"
        f"你可以通过 `GET /runs/{run.run_id}` 查询任务状态，"
        "也可以通过 `/messages` 接收桌宠状态反馈。"
    )
    return {
        **state,
        "output": output,
        "run_id": run.run_id,
        "run_status": run.status,
        "error": None,
        "ui_status": "run_queued",
    }


def unknown_node(state: AgentState) -> AgentState:
    prompt = state.get("user_input", "")
    return {
        **state,
        "output": (
            "抱歉，我暂时还不能很好地判断你的意图。\n\n"
            f"你输入的内容是：{prompt}\n\n"
            "你可以继续补充信息，或者明确说明你是想聊天还是想让我帮你处理代码任务。"
        ),
        "error": None,
        "ui_status": "unknown_done",
    }


def roleplay_node(state: AgentState) -> AgentState:
    output = (state.get("output") or "").strip()
    if output:
        message_sender.send_chat_message(
            content=output,
            is_partial=False,
            node_name="agent_roleplay",
        )
    return state


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
) -> dict[str, object]:
    initial_state: AgentState = {
        "user_input": prompt,
        "context": context,
        "session_id": session_id,
        "output": "",
        "error": None,
        "run_id": None,
        "run_status": None,
        "ui_status": None,
    }
    if intent is not None:
        initial_state["intent"] = intent

    try:
        result = agent_graph.invoke(initial_state)
    except Exception as exc:
        return {
            "ok": False,
            "intent": intent or "unknown",
            "output": f"Agent 工作流执行失败：{exc}",
            "error": str(exc),
            "run_id": None,
            "state": initial_state,
        }

    error = result.get("error")
    return {
        "ok": error is None,
        "intent": result.get("intent", intent or "unknown"),
        "output": result.get("output", ""),
        "error": error,
        "run_id": result.get("run_id"),
        "run_status": result.get("run_status"),
        "ui_status": result.get("ui_status"),
        "state": result,
    }
