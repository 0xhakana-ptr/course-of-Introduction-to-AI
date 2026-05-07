import os
import time

from backend.app.core.config import settings
from backend.app.storage.conversation_store import ConversationStore


def test_conversation_store_builds_context_with_external_context():
    store = ConversationStore()
    session_id = store.get_or_create_session_id()
    store.append_exchange(
        session_id,
        user_prompt="hello",
        assistant_output="hi there",
    )

    context = store.build_context(session_id, "client side history")

    assert context is not None
    assert "Client provided context:" in context
    assert "client side history" in context
    assert "Stored conversation history:" in context
    assert "User: hello" in context
    assert "Assistant: hi there" in context


def test_conversation_store_clear_session_returns_state():
    store = ConversationStore()
    session_id = store.get_or_create_session_id()
    store.append_message(session_id, "user", "hello")

    assert store.clear_session(session_id) is True
    assert store.clear_session(session_id) is False
    assert store.get_messages(session_id) == []


def test_conversation_store_persists_messages_to_workspace():
    store = ConversationStore()
    session_id = store.get_or_create_session_id("session-persist-demo")
    store.append_exchange(
        session_id,
        user_prompt="hello from disk",
        assistant_output="hi from disk",
    )

    reloaded_store = ConversationStore()
    messages = reloaded_store.get_messages(session_id)

    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello from disk"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "hi from disk"
    assert settings.conversation_dir.exists() is True
    assert any(settings.conversation_dir.glob("*.json"))


def test_conversation_store_prunes_expired_sessions(monkeypatch):
    store = ConversationStore()
    session_id = store.get_or_create_session_id("session-expired-demo")
    store.append_message(session_id, "user", "hello")
    session_path = store._get_session_path(session_id)

    old_timestamp = time.time() - 120
    os.utime(session_path, (old_timestamp, old_timestamp))
    monkeypatch.setattr(settings, "conversation_session_ttl_seconds", 1)

    removed_count = store.prune_storage(force=True)

    assert removed_count == 1
    assert session_path.exists() is False
    assert store.get_messages(session_id) == []


def test_conversation_store_limits_persisted_session_count(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(settings, "conversation_max_persisted_sessions", 2)

    session_ids = ["session-limit-1", "session-limit-2", "session-limit-3"]
    session_paths = []
    for index, session_id in enumerate(session_ids, start=1):
        store.append_message(session_id, "user", f"hello {index}")
        session_path = store._get_session_path(session_id)
        session_paths.append(session_path)
        adjusted_time = time.time() - (10 - index)
        os.utime(session_path, (adjusted_time, adjusted_time))

    removed_count = store.prune_storage(force=True)

    assert removed_count == 1
    assert session_paths[0].exists() is False
    assert session_paths[1].exists() is True
    assert session_paths[2].exists() is True
