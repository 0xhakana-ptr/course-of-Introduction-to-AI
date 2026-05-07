from backend.app.message_queue import message_queue
from backend.app.services.character_interface import (
    send_chat_started,
    send_task_done,
)
from backend.app.services.chat_action.types import ChatServiceResult
from backend.app.services.run_interface import create_run, execute_run


def test_send_chat_started_emits_character_messages():
    assert send_chat_started() is True

    messages = message_queue.get_messages()

    assert [message["type"] for message in messages] == ["quip", "expression", "status"]
    assert [message["_channel"] for message in messages] == [
        "agent:quip",
        "agent:expression",
        "agent:status",
    ]
    assert messages[0]["content"] == "我想一下。"
    assert messages[1]["expression"] == "thinking"
    assert messages[2]["status"] == "running"
    assert messages[2]["progress"] == 5


def test_send_task_done_emits_done_status_and_happy_expression():
    assert send_task_done() is True

    messages = message_queue.get_messages()

    assert messages[0]["type"] == "quip"
    assert messages[0]["content"] == "任务完成了。"
    assert messages[1]["type"] == "expression"
    assert messages[1]["expression"] == "happy"
    assert messages[2]["type"] == "status"
    assert messages[2]["status"] == "done"
    assert messages[2]["progress"] == 100


def test_chat_route_emits_character_events_on_failed_reply(client):
    response = client.post("/chat", json={"prompt": "hello", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False

    messages_response = client.get("/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    status_messages = [message for message in messages if message["type"] == "status"]

    assert status_messages[0]["node_name"] == "chat"
    assert status_messages[0]["status"] == "running"
    assert status_messages[-1]["node_name"] == "chat_error"
    assert status_messages[-1]["status"] == "error"


def test_run_success_emits_task_lifecycle_events(client):
    run = create_run("build a calculator demo", None)
    executed = execute_run(run.run_id)

    assert executed is not None
    assert executed.status == "done"

    response = client.get("/messages")
    assert response.status_code == 200
    messages = response.json()["messages"]
    status_messages = [message for message in messages if message["type"] == "status"]
    chat_messages = [message for message in messages if message["type"] == "chat"]
    node_names = [message["node_name"] for message in status_messages]
    statuses = [message["status"] for message in status_messages]

    assert "task_queued" in node_names
    assert "task_started" in node_names
    assert "task_done" in node_names
    assert statuses[-1] == "done"
    assert len(chat_messages) == 1
    assert chat_messages[0]["node_name"] == "task_done"
    assert run.run_id in chat_messages[0]["content"]
    assert f"GET /runs/{run.run_id}" in chat_messages[0]["content"]


def test_chat_route_success_uses_status_events_without_queueing_duplicate_chat(
    monkeypatch,
    client,
):
    async def fake_build_agent_reply(
        prompt: str,
        context: str | None,
        *,
        session_id: str | None = None,
        intent: str | None = None,
        emit_chat_message: bool = False,
    ):
        return ChatServiceResult(intent="chat", ok=True, output=f"reply to {prompt}")

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_agent_reply",
        fake_build_agent_reply,
    )

    response = client.post("/chat", json={"prompt": "hello", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True

    messages_response = client.get("/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    status_messages = [message for message in messages if message["type"] == "status"]
    chat_messages = [message for message in messages if message["type"] == "chat"]

    assert status_messages[0]["node_name"] == "chat"
    assert status_messages[-1]["node_name"] == "chat_done"
    assert status_messages[-1]["status"] == "done"
    assert chat_messages == []


def test_chat_coding_route_does_not_queue_duplicate_chat_message(client):
    response = client.post("/chat", json={"prompt": "write python code", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "coding"
    assert payload["run_id"]

    messages_response = client.get("/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()["messages"]
    chat_messages = [message for message in messages if message["type"] == "chat"]
    status_messages = [message for message in messages if message["type"] == "status"]

    assert all(message["content"] != payload["output"] for message in chat_messages)
    assert all(message["node_name"] != "agent_roleplay" for message in chat_messages)
    assert any(
        message["node_name"] in {"task_done", "task_failed", "task_cancelled"}
        for message in chat_messages
    )
    assert any(message["node_name"] == "task_queued" for message in status_messages)
