from backend.app.message_queue import message_queue


def test_message_websocket_sends_initial_snapshot(client):
    message_queue.add_message(
        {
            "type": "chat",
            "content": "hello",
            "_channel": "agent:chat",
        }
    )

    with client.websocket_connect("/messages/ws") as websocket:
        payload = websocket.receive_json()

    assert payload["ok"] is True
    assert payload["count"] == 1
    assert payload["messages"][0]["content"] == "hello"
    assert payload["messages"][0]["_channel"] == "agent:chat"
    assert payload["messages"][0]["bridge_event_type"] == "Roleplay_Dialogue"
    assert payload["messages"][0]["bridge_payload"]["content"] == "hello"


def test_message_websocket_respects_since_id_and_streams_incremental_messages(client):
    first_id = message_queue.add_message(
        {
            "type": "chat",
            "content": "before",
            "_channel": "agent:chat",
        }
    )
    message_queue.add_message(
        {
            "type": "status",
            "status": "running",
            "_channel": "agent:status",
        }
    )

    with client.websocket_connect(f"/messages/ws?since_id={first_id}") as websocket:
        initial_payload = websocket.receive_json()

        new_id = message_queue.add_message(
            {
                "type": "chat",
                "content": "after",
                "_channel": "agent:chat",
            }
        )
        incremental_payload = websocket.receive_json()

    assert initial_payload["ok"] is True
    assert initial_payload["count"] == 1
    assert initial_payload["messages"][0]["type"] == "status"
    assert initial_payload["messages"][0]["status"] == "running"

    assert incremental_payload["ok"] is True
    assert incremental_payload["count"] == 1
    assert incremental_payload["messages"][0]["_id"] == new_id
    assert incremental_payload["messages"][0]["content"] == "after"
    assert incremental_payload["messages"][0]["bridge_event_type"] == "Roleplay_Dialogue"


def test_message_websocket_returns_empty_snapshot_when_queue_is_empty(client):
    with client.websocket_connect("/messages/ws") as websocket:
        payload = websocket.receive_json()

    assert payload == {
        "ok": True,
        "messages": [],
        "count": 0,
    }
