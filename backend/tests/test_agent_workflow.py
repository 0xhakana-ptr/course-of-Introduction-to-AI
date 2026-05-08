from backend.app.agent_workflow.agent_graph import run_agent
from backend.app.agent_workflow.agent_support import (
    build_agent_initial_state,
    build_chat_result_state,
    build_run_creation_failure_state,
    build_run_creation_success_state,
    build_unknown_intent_output,
    build_unknown_intent_state,
    emit_agent_roleplay_state,
    merge_agent_state,
    select_agent_next_node,
)
from backend.app.message_queue import message_queue
from backend.app.services.run_interface import get_run


def test_agent_graph_routes_coding_intent_to_run_tool():
    result = run_agent("write python code", None, intent="coding")

    assert result.ok is True
    assert result.intent == "coding"
    assert result.run_id
    assert result.run_status == "queued"
    assert result.as_dict()["intent"] == "coding"

    run = get_run(str(result.run_id))
    assert run is not None
    assert run.status == "queued"


def test_agent_graph_routes_chat_intent_to_llm(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.agent_graph.call_llm_sync",
        lambda prompt, context: type(
            "FakeLLMResult",
            (),
            {
                "ok": True,
                "output": f"reply to {prompt}",
                "error": None,
            },
        )(),
    )

    result = run_agent("hello", "ctx", intent="chat", emit_chat_message=False)

    assert result.ok is True
    assert result.intent == "chat"
    assert result.output == "reply to hello"
    assert result.run_id is None
    assert result.as_dict()["output"] == "reply to hello"


def test_agent_support_builds_initial_state_with_optional_intent():
    state = build_agent_initial_state(
        prompt="hello",
        context="ctx",
        session_id="session-1",
        emit_chat_message=False,
        intent="chat",
    )

    assert state["user_input"] == "hello"
    assert state["context"] == "ctx"
    assert state["session_id"] == "session-1"
    assert state["emit_chat_message"] is False
    assert state["intent"] == "chat"
    assert state["run_id"] is None
    assert state["ui_status"] is None


def test_agent_support_selects_route_and_builds_unknown_output():
    assert select_agent_next_node("chat") == "chat_node"
    assert select_agent_next_node("coding") == "coding_node"
    assert select_agent_next_node("something-else") == "unknown_node"

    output = build_unknown_intent_output("???")

    assert "你输入的内容是：???" in output
    assert "聊天还是想让我帮你处理代码任务" in output


def test_agent_support_merges_state_and_builds_node_results():
    base_state = build_agent_initial_state(
        prompt="hello",
        context=None,
        session_id=None,
        emit_chat_message=False,
    )

    merged_state = merge_agent_state(base_state, ui_status="demo", output="x")
    chat_state = build_chat_result_state(base_state, output="reply", error=None)
    failed_run_state = build_run_creation_failure_state(base_state, error="boom")
    queued_run_state = build_run_creation_success_state(
        base_state,
        run_id="run-1",
        status="queued",
    )
    unknown_state = build_unknown_intent_state(base_state, prompt="???")

    assert merged_state["ui_status"] == "demo"
    assert merged_state["output"] == "x"
    assert chat_state["ui_status"] == "chat_done"
    assert chat_state["output"] == "reply"
    assert failed_run_state["ui_status"] == "run_create_failed"
    assert "代码任务创建失败" in failed_run_state["output"]
    assert queued_run_state["ui_status"] == "run_queued"
    assert queued_run_state["run_id"] == "run-1"
    assert unknown_state["ui_status"] == "unknown_done"


def test_agent_support_roleplay_helper_emits_message():
    state = build_agent_initial_state(
        prompt="hello",
        context=None,
        session_id=None,
        emit_chat_message=True,
    )
    state["output"] = "roleplay content"

    result_state = emit_agent_roleplay_state(state, node_name="agent_roleplay")
    messages = message_queue.get_messages()

    assert result_state["output"] == "roleplay content"
    assert len(messages) == 1
    assert messages[0]["type"] == "chat"
    assert messages[0]["node_name"] == "agent_roleplay"
    assert messages[0]["content"] == "roleplay content"
