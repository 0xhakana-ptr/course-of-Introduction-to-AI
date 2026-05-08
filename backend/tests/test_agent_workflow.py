from backend.app.agent_workflow.agent_graph import run_agent
from backend.app.agent_workflow.agent_support import (
    build_agent_initial_state,
    build_chat_result_state,
    build_coding_requested_state,
    build_run_creation_failure_state,
    build_run_creation_success_state,
    build_unknown_intent_output,
    build_unknown_intent_state,
    emit_agent_roleplay_state,
    merge_context_sections,
    merge_agent_state,
    select_agent_next_node,
)
from backend.app.agent_workflow.roleplay import emit_roleplay_message, emit_roleplay_state
from backend.app.agent_workflow.workflow_results import WorkflowAgentResult
from backend.app.message_queue import message_queue
from backend.app.services.chat_action.types import ChatServiceResult
from backend.app.services.run_action.types import WorkflowChatMessage
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


def test_agent_graph_routes_coding_intent_with_workspace_tool_context(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "backend.app.agent_workflow.agent_support.build_workspace_overview",
        lambda: "Workspace top-level entries:\n- [file] README.md",
    )

    def fake_create_run(prompt: str, context: str | None):
        captured["prompt"] = prompt
        captured["context"] = context
        return type("FakeRun", (), {"run_id": "run-tool-1", "status": "queued"})()

    monkeypatch.setattr(
        "backend.app.agent_workflow.agent_graph.create_run",
        fake_create_run,
    )

    result = run_agent("write python code", "client ctx", intent="coding")

    assert result.ok is True
    assert result.intent == "coding"
    assert result.run_id == "run-tool-1"
    assert captured["prompt"] == "write python code"
    assert captured["context"] == (
        "client ctx\n\n"
        "Workspace overview for the coding task:\n"
        "Workspace top-level entries:\n"
        "- [file] README.md"
    )


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


def test_agent_support_merges_context_sections_and_coding_tool_context(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agent_workflow.agent_support.build_workspace_overview",
        lambda: "Workspace top-level entries:\n- [file] README.md",
    )

    merged_context = merge_context_sections("client ctx", None, "tool ctx")
    state = build_coding_requested_state(
        build_agent_initial_state(
            prompt="write code",
            context="client ctx",
            session_id=None,
            emit_chat_message=False,
        )
    )

    assert merged_context == "client ctx\n\ntool ctx"
    assert "Workspace overview for the coding task:" in str(state["context"])
    assert "client ctx" in str(state["context"])
    assert state["ui_status"] == "coding_requested"


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


def test_roleplay_helpers_emit_message_from_message_and_state():
    message_queue.clear()

    emit_roleplay_message(
        WorkflowChatMessage(
            node_name="task_repairing",
            content="repair feedback",
        ),
        default_node_name="agent_roleplay",
    )
    state = emit_roleplay_state(
        {
            "output": "state content",
            "node_name": "summary_demo",
            "emit_chat_message": True,
        },
        default_node_name="agent_roleplay",
    )
    messages = message_queue.get_messages()

    assert state["output"] == "state content"
    assert len(messages) == 2
    assert messages[0]["node_name"] == "task_repairing"
    assert messages[0]["content"] == "repair feedback"
    assert messages[1]["node_name"] == "summary_demo"
    assert messages[1]["content"] == "state content"


def test_chat_service_result_can_normalize_agent_result_and_apply_updates():
    fake_agent_result = type(
        "FakeAgentResult",
        (),
        {
            "intent": "other",
            "ok": True,
            "output": "   ",
            "error": None,
            "run_id": " run-1 ",
        },
    )()

    result = ChatServiceResult.from_agent_result(
        fake_agent_result,
        intent_hint="coding",
        fallback_output_builder=lambda intent: f"fallback::{intent}",
    )
    updated = result.with_updates(session_id="session-1", error="boom")

    assert result.intent == "unknown"
    assert result.is_intent("unknown") is True
    assert result.output == "fallback::unknown"
    assert result.run_id == "run-1"
    assert updated.session_id == "session-1"
    assert updated.error == "boom"
    assert result.session_id is None


def test_workflow_agent_result_can_normalize_generic_object_fields():
    fake_agent_result = type(
        "FakeAgentWorkflowResult",
        (),
        {
            "ok": True,
            "output": "agent output",
            "intent": "coding",
            "error": None,
            "run_id": " run-2 ",
            "run_status": " queued ",
            "ui_status": " run_queued ",
        },
    )()

    result = WorkflowAgentResult.from_value(
        fake_agent_result,
        default_intent="unknown",
    )

    assert result.ok is True
    assert result.output == "agent output"
    assert result.intent == "coding"
    assert result.run_id == "run-2"
    assert result.run_status == "queued"
    assert result.ui_status == "run_queued"


def test_workflow_agent_result_exposes_consumption_helpers():
    result = WorkflowAgentResult.from_value(
        {
            "ok": True,
            "output": "   ",
            "intent": "other",
            "run_id": "run-3",
            "run_status": "queued",
        }
    )

    assert result.resolved_intent(valid_intents={"chat", "coding", "unknown"}) == "unknown"
    assert result.resolved_output(
        intent="unknown",
        fallback_output_builder=lambda intent: f"fallback::{intent}",
    ) == "fallback::unknown"
    assert result.run_payload() == ("run-3", "queued")
