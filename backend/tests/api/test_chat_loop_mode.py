import importlib

from backend.app.tools.workspace_tools import read_workspace_text


def _fake_llm_result(*, ok: bool = True, output: str = "loop chat reply", error: str | None = None):
    return type(
        "FakeLLMResult",
        (),
        {
            "ok": ok,
            "output": output,
            "error": error,
        },
    )()


def test_chat_route_uses_loop_runtime_for_chat(monkeypatch, client):
    loop_module = importlib.import_module("backend.app.agent_workflow.loop.agent_loop_graph")
    monkeypatch.setattr(
        loop_module,
        "call_llm_sync",
        lambda prompt, context: _fake_llm_result(output=f"loop reply to {prompt}"),
    )

    response = client.post("/chat", json={"prompt": "hello loop", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "chat"
    assert payload["output"] == "loop reply to hello loop"
    assert payload["session_id"]
    assert payload["run_id"] is None
    assert payload["runtime_mode"] == "loop"
    assert payload["route_scope"] == "primary_loop"
    assert payload["runtime_warning"] is None
    assert payload["content_type"] == "markdown"
    assert payload["render_mode"] == "rich_text"

    messages = client.get("/messages").json()["messages"]
    status_messages = [message for message in messages if message["type"] == "status"]
    action_messages = [
        message
        for message in status_messages
        if str(message.get("event_type") or "").startswith("workflow.action_")
    ]
    node_names = [message["node_name"] for message in messages]

    assert "plan_node" in node_names
    assert "plan_node" in node_names
    assert "finalize_node" in node_names
    assert [message["event_type"] for message in action_messages] == [
        "workflow.action_started",
        "workflow.action_completed",
    ]
    assert {message["metadata"]["action_name"] for message in action_messages} == {"chat.reply"}
    assert status_messages[-1]["status"] == "done"


def test_chat_route_uses_loop_runtime_for_workspace_write(client):
    response = client.post(
        "/chat",
        json={"prompt": "请创建 notes/chat-loop.txt，内容是chat loop ok", "context": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["intent"] == "coding"
    assert payload["run_id"] is None
    assert "已在 workspace 中创建文本文件" in payload["output"]
    assert read_workspace_text("notes/chat-loop.txt")["content"] == "chat loop ok"

    messages = client.get("/messages").json()["messages"]
    status_messages = [message for message in messages if message["type"] == "status"]
    action_messages = [
        message
        for message in status_messages
        if str(message.get("event_type") or "").startswith("workflow.action_")
    ]
    node_names = [message["node_name"] for message in messages]

    assert "plan_node" in node_names
    assert "act_node" in node_names
    assert "finalize_node" in node_names
    assert [message["event_type"] for message in action_messages] == [
        "workflow.action_started",
        "workflow.action_completed",
    ]
    assert {message["metadata"]["action_name"] for message in action_messages} == {
        "workspace.write",
    }
    assert action_messages[-1]["metadata"]["action_label"] == "写入工作区文本"
    assert status_messages[-1]["status"] == "done"


def test_chat_route_reports_loop_runtime_failure(monkeypatch, client):
    loop_module = importlib.import_module("backend.app.agent_workflow.loop.agent_loop_graph")
    monkeypatch.setattr(
        loop_module,
        "call_llm_sync",
        lambda prompt, context: _fake_llm_result(
            ok=False,
            output="调用大模型接口失败。",
            error="llm failed",
        ),
    )

    response = client.post("/chat", json={"prompt": "hello loop", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["intent"] == "chat"
    assert payload["error"] == "llm failed"
    assert "调用大模型接口失败" in payload["output"]

    messages = client.get("/messages").json()["messages"]
    status_messages = [message for message in messages if message["type"] == "status"]
    action_messages = [
        message
        for message in status_messages
        if str(message.get("event_type") or "").startswith("workflow.action_")
    ]
    node_names = [message["node_name"] for message in messages]

    assert "failure_node" in node_names
    assert [message["event_type"] for message in action_messages] == [
        "workflow.action_started",
        "workflow.action_failed",
    ]
    assert action_messages[-1]["metadata"]["action_name"] == "chat.reply"
    assert action_messages[-1]["metadata"]["ok"] is False
    assert status_messages[-1]["status"] == "error"
