from backend.app.agent_workflow.agent_graph import run_agent
from backend.app.services.run_interface import get_run


def test_agent_graph_routes_coding_intent_to_run_tool():
    result = run_agent("write python code", None, intent="coding")

    assert result["ok"] is True
    assert result["intent"] == "coding"
    assert result["run_id"]
    assert result["run_status"] == "queued"

    run = get_run(str(result["run_id"]))
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

    assert result["ok"] is True
    assert result["intent"] == "chat"
    assert result["output"] == "reply to hello"
    assert result["run_id"] is None
