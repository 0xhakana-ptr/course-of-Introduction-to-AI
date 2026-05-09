from backend.app.message_queue import MessageQueue


def test_message_ids_are_unique_and_timestamp_is_normalized():
    queue = MessageQueue()

    first_id = queue.add_message({"type": "chat", "content": "hello"})
    second_id = queue.add_message({"type": "chat", "content": "world"})
    messages = queue.get_messages()

    assert first_id != second_id
    assert len(messages) == 2
    assert messages[0]["_timestamp"].endswith("Z")
    assert messages[1]["_timestamp"].endswith("Z")
    assert messages[0]["_channel"] == "agent:chat"
    assert messages[1]["_channel"] == "agent:chat"


def test_get_messages_since_id_returns_incremental_items_only():
    queue = MessageQueue()

    first_id = queue.add_message({"type": "status", "status": "running"})
    queue.add_message({"type": "chat", "content": "step 2"})
    queue.add_message({"type": "chat", "content": "step 3"})

    messages = queue.get_messages(first_id)

    assert len(messages) == 2
    assert [message["content"] for message in messages] == ["step 2", "step 3"]


def test_get_messages_with_unknown_since_id_returns_empty_list():
    queue = MessageQueue()

    queue.add_message({"type": "chat", "content": "hello"})

    assert queue.get_messages("missing-message-id") == []


def test_add_message_normalizes_runtime_event_fields():
    queue = MessageQueue()

    queue.add_message(
        {
            "type": "status",
            "status": "running",
            "event_type": "run.started",
            "event_source": "run",
            "event_stage": "run",
            "frontend_visible": True,
        }
    )

    messages = queue.get_messages()

    assert messages[0]["_channel"] == "agent:status"
    assert messages[0]["event_type"] == "run.started"
    assert messages[0]["event_source"] == "run"
    assert messages[0]["event_stage"] == "run"
    assert messages[0]["frontend_visible"] is True
