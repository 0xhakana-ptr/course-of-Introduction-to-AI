import importlib

import pytest

from backend.app.message_queue import MessageQueue, message_queue
from backend.app.messaging.runtime_events import CHANNEL_BY_MESSAGE_TYPE
from backend.app.messaging.message_sender import MessageSender
from backend.app.schemas import MessageEnvelope


def test_message_type_channel_mapping_covers_public_protocol():
    assert CHANNEL_BY_MESSAGE_TYPE == {
        "quip": "agent:quip",
        "expression": "agent:expression",
        "motion": "agent:motion",
        "chat": "agent:chat",
        "error": "agent:error",
        "status": "agent:status",
    }


def test_message_envelope_accepts_motion_message():
    envelope = MessageEnvelope.model_validate(
        {
            "_id": "msg_1",
            "_timestamp": "2026-05-07T00:00:00Z",
            "_channel": "agent:motion",
            "type": "motion",
            "event_type": "character.motion",
            "event_source": "character",
            "event_stage": "roleplay",
            "frontend_visible": True,
            "motion": "motion/@group/Idle/0",
            "node_name": "idle",
            "metadata": {"loop": False},
        }
    )

    assert envelope.channel == "agent:motion"
    assert envelope.type == "motion"
    assert envelope.event_type == "character.motion"
    assert envelope.event_source == "character"
    assert envelope.event_stage == "roleplay"
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
    assert messages[0]["event_type"] == "character.motion"
    assert messages[0]["event_source"] == "character"
    assert messages[0]["event_stage"] == "roleplay"
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
    assert messages[0]["event_type"] == "chat.message"
    assert messages[0]["event_source"] == "roleplay"
    assert messages[0]["event_stage"] == "roleplay"
    assert messages[0]["node_name"] == "agent_roleplay"
    assert messages[0]["metadata"]["node_name"] == "agent_roleplay"


def test_message_envelope_accepts_workflow_action_event():
    envelope = MessageEnvelope.model_validate(
        {
            "_id": "msg_action_1",
            "_timestamp": "2026-05-11T00:00:00Z",
            "_channel": "agent:status",
            "type": "status",
            "event_type": "workflow.action_started",
            "event_source": "workflow",
            "event_stage": "tools",
            "frontend_visible": True,
            "status": "running",
            "progress": 42,
            "node_name": "act_node",
            "metadata": {
                "runtime_event": "action_started",
                "action_name": "workspace.write",
                "action_label": "写入工作区文本",
                "action_status": "started",
            },
        }
    )

    assert envelope.channel == "agent:status"
    assert envelope.event_type == "workflow.action_started"
    assert envelope.event_stage == "tools"
    assert envelope.metadata["action_name"] == "workspace.write"


@pytest.mark.parametrize(
    ("sender_call", "message_type", "channel", "event_type", "event_source", "event_stage"),
    [
        (
            lambda sender: sender.send_quip("thinking", node_name="chat"),
            "quip",
            "agent:quip",
            "character.quip",
            "character",
            "roleplay",
        ),
        (
            lambda sender: sender.send_expression("thinking", node_name="chat"),
            "expression",
            "agent:expression",
            "character.expression",
            "character",
            "roleplay",
        ),
        (
            lambda sender: sender.send_motion("motion/@group/Idle/0", node_name="idle"),
            "motion",
            "agent:motion",
            "character.motion",
            "character",
            "roleplay",
        ),
        (
            lambda sender: sender.send_chat_message("hello", node_name="agent_roleplay"),
            "chat",
            "agent:chat",
            "chat.message",
            "roleplay",
            "roleplay",
        ),
        (
            lambda sender: sender.send_error("demo_error", "boom", node_name="agent_error"),
            "error",
            "agent:error",
            "system.error",
            "system",
            "system",
        ),
        (
            lambda sender: sender.send_status("running", progress=30, node_name="run"),
            "status",
            "agent:status",
            "status.updated",
            "system",
            "system",
        ),
    ],
)
def test_message_sender_outputs_valid_public_protocol(
    monkeypatch,
    sender_call,
    message_type,
    channel,
    event_type,
    event_source,
    event_stage,
):
    queue = MessageQueue()
    message_sender_module = importlib.import_module("backend.app.messaging.message_sender")
    monkeypatch.setattr(message_sender_module, "message_queue", queue)
    sender = MessageSender()

    assert sender_call(sender) is True

    messages = queue.get_messages()
    assert len(messages) == 1
    envelope = MessageEnvelope.model_validate(messages[0])
    assert envelope.type == message_type
    assert envelope.channel == channel
    assert envelope.event_type == event_type
    assert envelope.event_source == event_source
    assert envelope.event_stage == event_stage
    assert envelope.frontend_visible is True


def test_messages_route_exposes_motion_protocol(client):
    message_queue.add_message(
        {
            "_channel": "agent:motion",
            "type": "motion",
            "event_type": "character.motion",
            "event_source": "character",
            "event_stage": "roleplay",
            "frontend_visible": True,
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
    assert payload["messages"][0]["event_type"] == "character.motion"
    assert payload["messages"][0]["event_source"] == "character"
    assert payload["messages"][0]["event_stage"] == "roleplay"
    assert payload["messages"][0]["frontend_visible"] is True
    assert payload["messages"][0]["motion"] == "motion/@group/Idle/0"
