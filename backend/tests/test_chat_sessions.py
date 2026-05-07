from backend.app.llm.client import LLMCallResult


def test_chat_response_returns_session_id_when_missing_llm(client):
    response = client.post("/chat", json={"prompt": "hello", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["intent"] == "chat"


def test_chat_session_passes_stored_history_to_next_reply(monkeypatch, client):
    seen_contexts: list[str | None] = []

    async def fake_build_chat_reply(prompt: str, context: str | None):
        seen_contexts.append(context)
        return LLMCallResult(ok=True, output=f"reply to {prompt}")

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_chat_reply",
        fake_build_chat_reply,
    )

    first_response = client.post("/chat", json={"prompt": "first hello", "context": None})
    assert first_response.status_code == 200
    session_id = first_response.json()["session_id"]

    second_response = client.post(
        "/chat",
        json={"prompt": "second hello", "context": None, "session_id": session_id},
    )

    assert second_response.status_code == 200
    assert second_response.json()["session_id"] == session_id
    assert seen_contexts[0] is None
    assert seen_contexts[1] is not None
    assert "User: first hello" in seen_contexts[1]
    assert "Assistant: reply to first hello" in seen_contexts[1]


def test_clear_chat_session_endpoint_removes_history(monkeypatch, client):
    seen_contexts: list[str | None] = []

    async def fake_build_chat_reply(prompt: str, context: str | None):
        seen_contexts.append(context)
        return LLMCallResult(ok=True, output=f"reply to {prompt}")

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_chat_reply",
        fake_build_chat_reply,
    )

    first_response = client.post("/chat", json={"prompt": "remember this", "context": None})
    session_id = first_response.json()["session_id"]

    clear_response = client.delete(f"/chat/sessions/{session_id}")
    assert clear_response.status_code == 200
    clear_payload = clear_response.json()
    assert clear_payload["ok"] is True
    assert clear_payload["session_id"] == session_id
    assert clear_payload["cleared"] is True

    second_response = client.post(
        "/chat",
        json={"prompt": "after clear", "context": None, "session_id": session_id},
    )

    assert second_response.status_code == 200
    assert seen_contexts[-1] is None
