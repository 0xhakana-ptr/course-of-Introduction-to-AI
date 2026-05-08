from collections.abc import Mapping

from .roleplay import emit_roleplay_chat
from ..schemas import INTENT_TYPE
from .workflow_results import WorkflowAgentResult, invoke_graph_with_result


AGENT_ROUTE_BY_INTENT: dict[str, str] = {
    "coding": "coding_node",
    "chat": "chat_node",
    "unknown": "unknown_node",
}


def select_agent_next_node(intent: str | None) -> str:
    return AGENT_ROUTE_BY_INTENT.get(str(intent or "").strip(), "unknown_node")


def build_run_creation_output(*, run_id: str, status: str) -> str:
    return (
        "已通过 LangGraph 创建代码任务，并交给 `/runs` 链路处理。\n\n"
        f"run_id: {run_id}\n"
        f"status: {status}\n\n"
        f"你可以通过 `GET /runs/{run_id}` 查询任务状态，"
        "也可以通过 `/messages` 接收桌宠状态反馈。"
    )


def build_unknown_intent_output(prompt: str) -> str:
    return (
        "抱歉，我暂时还不能很好地判断你的意图。\n\n"
        f"你输入的内容是：{prompt}\n\n"
        "你可以继续补充信息，或者明确说明你是想聊天还是想让我帮你处理代码任务。"
    )


def merge_agent_state(
    state: Mapping[str, object],
    *,
    ui_status: str | None = None,
    **updates: object,
) -> dict[str, object]:
    next_state = {
        **state,
        **updates,
    }
    if ui_status is not None:
        next_state["ui_status"] = ui_status
    return next_state


def build_routed_state(
    state: Mapping[str, object],
    *,
    intent: str,
) -> dict[str, object]:
    return merge_agent_state(
        state,
        intent=intent,
        ui_status="routed",
    )


def build_chat_result_state(
    state: Mapping[str, object],
    *,
    output: str,
    error: str | None,
) -> dict[str, object]:
    return merge_agent_state(
        state,
        output=output,
        error=error,
        ui_status="chat_failed" if error else "chat_done",
    )


def build_coding_requested_state(state: Mapping[str, object]) -> dict[str, object]:
    return merge_agent_state(
        state,
        ui_status="coding_requested",
    )


def build_run_creation_failure_state(
    state: Mapping[str, object],
    *,
    error: str,
) -> dict[str, object]:
    return merge_agent_state(
        state,
        output=f"代码任务创建失败：{error}",
        error=error,
        ui_status="run_create_failed",
    )


def build_run_creation_success_state(
    state: Mapping[str, object],
    *,
    run_id: str,
    status: str,
) -> dict[str, object]:
    return merge_agent_state(
        state,
        output=build_run_creation_output(run_id=run_id, status=status),
        run_id=run_id,
        run_status=status,
        error=None,
        ui_status="run_queued",
    )


def build_unknown_intent_state(
    state: Mapping[str, object],
    *,
    prompt: str,
) -> dict[str, object]:
    return merge_agent_state(
        state,
        output=build_unknown_intent_output(prompt),
        error=None,
        ui_status="unknown_done",
    )


def emit_agent_roleplay_state(
    state: Mapping[str, object],
    *,
    node_name: str = "agent_roleplay",
) -> dict[str, object]:
    emit_roleplay_chat(
        str(state.get("output") or ""),
        node_name=node_name,
        emit_chat_message=bool(state.get("emit_chat_message", True)),
    )
    return dict(state)


def build_agent_initial_state(
    *,
    prompt: str,
    context: str | None,
    session_id: str | None,
    emit_chat_message: bool,
    intent: INTENT_TYPE | None = None,
) -> dict[str, object]:
    state: dict[str, object] = {
        "user_input": prompt,
        "context": context,
        "session_id": session_id,
        "emit_chat_message": emit_chat_message,
        "output": "",
        "error": None,
        "run_id": None,
        "run_status": None,
        "ui_status": None,
    }
    if intent is not None:
        state["intent"] = intent
    return state


def invoke_agent_graph(
    graph: object,
    *,
    prompt: str,
    context: str | None,
    session_id: str | None,
    intent: INTENT_TYPE | None,
    emit_chat_message: bool,
) -> WorkflowAgentResult:
    initial_state = build_agent_initial_state(
        prompt=prompt,
        context=context,
        session_id=session_id,
        emit_chat_message=emit_chat_message,
        intent=intent,
    )
    return invoke_graph_with_result(
        graph,
        initial_state=initial_state,
        on_success=lambda result: WorkflowAgentResult.from_state(
            result,
            default_intent=intent or "unknown",
        ),
        on_error=lambda exc, state: WorkflowAgentResult.from_error(
            exc,
            state,
            default_intent=intent or "unknown",
        ),
    )
