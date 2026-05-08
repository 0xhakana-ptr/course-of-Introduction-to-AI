from backend.app.services.chat_action.types import ChatServiceResult
from backend.app.storage.conversation_store import ConversationStore


def test_chat_response_returns_session_id_when_missing_llm(client):
    response = client.post("/chat", json={"prompt": "hello", "context": None})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["intent"] == "chat"


def test_chat_session_passes_stored_history_to_next_reply(monkeypatch, client):
    seen_contexts: list[str | None] = []

    async def fake_build_agent_reply(
        prompt: str,
        context: str | None,
        *,
        session_id: str | None = None,
        intent: str | None = None,
        emit_chat_message: bool = False,
    ):
        seen_contexts.append(context)
        return ChatServiceResult(intent="chat", ok=True, output=f"reply to {prompt}")

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_agent_reply",
        fake_build_agent_reply,
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

    async def fake_build_agent_reply(
        prompt: str,
        context: str | None,
        *,
        session_id: str | None = None,
        intent: str | None = None,
        emit_chat_message: bool = False,
    ):
        seen_contexts.append(context)
        return ChatServiceResult(intent="chat", ok=True, output=f"reply to {prompt}")

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_agent_reply",
        fake_build_agent_reply,
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


def test_chat_session_metadata_endpoint_returns_session_state(monkeypatch, client):
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
    monkeypatch.setattr(
        "backend.app.core.config.settings.conversation_context_recent_messages",
        2,
    )

    session_id: str | None = None
    for prompt in ["first hello", "second hello", "third hello"]:
        response = client.post(
            "/chat",
            json={"prompt": prompt, "context": None, "session_id": session_id},
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

    assert session_id is not None
    metadata_response = client.get(f"/chat/sessions/{session_id}")
    assert metadata_response.status_code == 200
    payload = metadata_response.json()
    assert payload["ok"] is True
    assert payload["exists"] is True
    assert payload["session_id"] == session_id
    assert payload["message_count"] == 6
    assert payload["recent_message_count"] == 2
    assert payload["compressed_message_count"] == 4
    assert payload["has_compressed_context"] is True
    assert payload["has_summary_cache"] is True
    assert payload["summary_preview"]
    assert payload["context_strategy_version"] == 1
    assert payload["updated_at"]


def test_chat_session_metadata_endpoint_returns_exists_false_for_unknown_session(client):
    response = client.get("/chat/sessions/not-found-session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["exists"] is False
    assert payload["session_id"] == "not-found-session"
    assert payload["message_count"] == 0
    assert payload["has_summary_cache"] is False


def test_chat_session_list_endpoint_returns_recent_sessions(monkeypatch, client):
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
    monkeypatch.setattr(
        "backend.app.core.config.settings.conversation_context_recent_messages",
        2,
    )

    first_response = client.post("/chat", json={"prompt": "first hello", "context": None})
    assert first_response.status_code == 200
    first_session_id = first_response.json()["session_id"]

    second_response = client.post("/chat", json={"prompt": "second hello", "context": None})
    assert second_response.status_code == 200
    second_session_id = second_response.json()["session_id"]

    third_response = client.post(
        "/chat",
        json={"prompt": "second hello again", "context": None, "session_id": second_session_id},
    )
    assert third_response.status_code == 200

    sessions_response = client.get("/chat/sessions?offset=0&limit=10")
    assert sessions_response.status_code == 200
    payload = sessions_response.json()

    assert payload["ok"] is True
    assert payload["total"] == 2
    assert payload["offset"] == 0
    assert payload["limit"] == 10
    assert len(payload["items"]) == 2
    assert payload["items"][0]["session_id"] == second_session_id
    assert payload["items"][0]["message_count"] == 4
    assert payload["items"][0]["has_summary_cache"] is True
    assert payload["items"][0]["context_strategy_version"] == 1
    assert payload["items"][1]["session_id"] == first_session_id
    assert payload["items"][1]["message_count"] == 2
    assert payload["items"][1]["has_summary_cache"] is False


def test_chat_session_history_is_persisted_to_workspace(monkeypatch, client):
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

    response = client.post("/chat", json={"prompt": "persist this", "context": None})
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    reloaded_store = ConversationStore()
    context = reloaded_store.build_context(session_id)

    assert context is not None
    assert "User: persist this" in context
    assert "Assistant: reply to persist this" in context


def test_chat_session_uses_compressed_context_for_long_history(monkeypatch, client):
    seen_contexts: list[str | None] = []

    async def fake_build_agent_reply(
        prompt: str,
        context: str | None,
        *,
        session_id: str | None = None,
        intent: str | None = None,
        emit_chat_message: bool = False,
    ):
        seen_contexts.append(context)
        return ChatServiceResult(intent="chat", ok=True, output=f"reply to {prompt}")

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_agent_reply",
        fake_build_agent_reply,
    )
    monkeypatch.setattr(
        "backend.app.core.config.settings.conversation_context_recent_messages",
        2,
    )
    monkeypatch.setattr(
        "backend.app.core.config.settings.conversation_summary_max_chars",
        200,
    )

    session_id: str | None = None
    prompts = [
        "first hello with extra words",
        "second hello with extra words",
        "third hello with extra words",
    ]

    for prompt in prompts:
        response = client.post(
            "/chat",
            json={"prompt": prompt, "context": None, "session_id": session_id},
        )
        assert response.status_code == 200
        session_id = response.json()["session_id"]

    assert session_id is not None
    assert seen_contexts[-1] is not None
    assert "Compressed earlier conversation summary:" in seen_contexts[-1]
    assert "Recent stored conversation history:" in seen_contexts[-1]
    assert "User: third hello with extra words" not in seen_contexts[-1]

    fourth_response = client.post(
        "/chat",
        json={"prompt": "fourth hello", "context": None, "session_id": session_id},
    )
    assert fourth_response.status_code == 200

    assert seen_contexts[-1] is not None
    assert "Compressed earlier conversation summary:" in seen_contexts[-1]
    assert "Recent stored conversation history:" in seen_contexts[-1]
    assert "User: fourth hello" not in seen_contexts[-1]
    assert "Assistant: reply to third hello with extra words" in seen_contexts[-1]
