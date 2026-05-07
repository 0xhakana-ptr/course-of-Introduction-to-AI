import importlib

from backend.app.message_queue import MessageQueue, message_queue
from backend.app.messaging.message_sender import MessageSender
from backend.app.schemas import MessageEnvelope


def test_message_envelope_accepts_motion_message():
    envelope = MessageEnvelope.model_validate(
        {
            "_id": "msg_1",
            "_timestamp": "2026-05-07T00:00:00Z",
            "_channel": "agent:motion",
            "type": "motion",
            "motion": "motion/@group/Idle/0",
            "node_name": "idle",
            "metadata": {"loop": False},
        }
    )

    assert envelope.channel == "agent:motion"
    assert envelope.type == "motion"
    assert envelope.motion == "motion/@group/Idle/0"


def test_message_sender_queues_motion_message(monkeypatch):
    queue = MessageQueue()
    message_sender_module = importlib.import_module("backend.app.messaging.message_sender")
    monkeypatch.setattr(message_sender_module, "message_queue", queue)
    sender = MessageSender()

    ok = sender.send_motion("motion/@group/Idle/0", node_name="idle", loop=False)

    assert ok is True
    messages = queue.get_messages()
    assert len(messages) == 1
    assert messages[0]["_channel"] == "agent:motion"
    assert messages[0]["type"] == "motion"
    assert messages[0]["motion"] == "motion/@group/Idle/0"
    assert messages[0]["metadata"]["loop"] is False


def test_message_sender_queues_chat_message_with_top_level_node_name(monkeypatch):
    queue = MessageQueue()
    message_sender_module = importlib.import_module("backend.app.messaging.message_sender")
    monkeypatch.setattr(message_sender_module, "message_queue", queue)
    sender = MessageSender()

    ok = sender.send_chat_message("hello", node_name="agent_roleplay")

    assert ok is True
    messages = queue.get_messages()
    assert len(messages) == 1
    assert messages[0]["_channel"] == "agent:chat"
    assert messages[0]["type"] == "chat"
    assert messages[0]["node_name"] == "agent_roleplay"
    assert messages[0]["metadata"]["node_name"] == "agent_roleplay"


def test_messages_route_exposes_motion_protocol(client):
    message_queue.add_message(
        {
            "_channel": "agent:motion",
            "type": "motion",
            "motion": "motion/@group/Idle/0",
            "node_name": "idle",
            "metadata": {"loop": False},
        }
    )

    response = client.get("/messages")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["messages"][0]["_channel"] == "agent:motion"
    assert payload["messages"][0]["type"] == "motion"
    assert payload["messages"][0]["motion"] == "motion/@group/Idle/0"
