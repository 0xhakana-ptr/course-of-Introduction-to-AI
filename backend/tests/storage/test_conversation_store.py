import os
import time
import json

from backend.app.core.config import settings
from backend.app.storage.conversation_store import CONTEXT_TRUNCATED_MARKER, ConversationStore


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


def test_conversation_store_limits_external_context_before_combining(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(settings, "chat_external_context_max_chars", 48)
    monkeypatch.setattr(settings, "chat_context_max_chars", 1000)
    session_id = store.get_or_create_session_id("session-external-context-limit-demo")

    context = store.build_context(
        session_id,
        "external-prefix-" + ("x" * 120),
    )

    assert context is not None
    assert "Client provided context:" in context
    assert "external-prefix-" in context
    assert CONTEXT_TRUNCATED_MARKER in context
    assert "x" * 80 not in context


def test_conversation_store_limits_recent_message_context(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(settings, "conversation_recent_message_max_chars", 32)
    session_id = store.get_or_create_session_id("session-recent-message-limit-demo")
    store.append_exchange(
        session_id,
        user_prompt="short question",
        assistant_output="answer-" + ("y" * 120),
    )

    context = store.build_context(session_id)

    assert context is not None
    assert "Stored conversation history:" in context
    assert "Assistant: answer-" in context
    assert "..." in context
    assert "y" * 80 not in context


def test_conversation_store_limits_combined_context(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(settings, "chat_external_context_max_chars", 1000)
    monkeypatch.setattr(settings, "chat_context_max_chars", 96)
    session_id = store.get_or_create_session_id("session-combined-context-limit-demo")
    store.append_exchange(
        session_id,
        user_prompt="question-" + ("a" * 120),
        assistant_output="answer-" + ("b" * 120),
    )

    context = store.build_context(
        session_id,
        "external-" + ("c" * 120),
    )

    assert context is not None
    assert len(context) <= 96
    assert CONTEXT_TRUNCATED_MARKER in context


def test_conversation_store_compresses_older_history_in_context(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(settings, "conversation_context_recent_messages", 2)
    monkeypatch.setattr(settings, "conversation_summary_max_chars", 300)
    session_id = store.get_or_create_session_id("session-compress-demo")

    store.append_exchange(
        session_id,
        user_prompt="first question with some extra words",
        assistant_output="first answer with some extra words",
    )
    store.append_exchange(
        session_id,
        user_prompt="second question with some extra words",
        assistant_output="second answer with some extra words",
    )
    store.append_exchange(
        session_id,
        user_prompt="third question should stay recent",
        assistant_output="third answer should stay recent",
    )

    context = store.build_context(session_id)

    assert context is not None
    assert "Compressed earlier conversation summary:" in context
    assert "(covering 4 earlier messages)" in context
    assert "Recent stored conversation history:" in context
    assert "User: third question should stay recent" in context
    assert "Assistant: third answer should stay recent" in context
    assert "User: first question with some extra words" in context
    assert "Assistant: first answer with some extra words" in context


def test_conversation_store_limits_summary_length_for_older_history(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(settings, "conversation_context_recent_messages", 2)
    monkeypatch.setattr(settings, "conversation_summary_max_chars", 80)
    session_id = store.get_or_create_session_id("session-summary-limit-demo")

    for index in range(1, 6):
        store.append_exchange(
            session_id,
            user_prompt=f"user message {index} " + ("x" * 40),
            assistant_output=f"assistant reply {index} " + ("y" * 40),
        )

    context = store.build_context(session_id)

    assert context is not None
    assert "Compressed earlier conversation summary:" in context
    assert "earlier messages omitted" in context
    assert "Recent stored conversation history:" in context


def test_conversation_store_persists_session_metadata(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(settings, "conversation_context_recent_messages", 2)
    session_id = store.get_or_create_session_id("session-metadata-demo")
    store.append_exchange(
        session_id,
        user_prompt="first question with extra words",
        assistant_output="first answer with extra words",
    )
    store.append_exchange(
        session_id,
        user_prompt="second question with extra words",
        assistant_output="second answer with extra words",
    )

    metadata = store.get_session_metadata(session_id)
    session_payload = json.loads(store._get_session_path(session_id).read_text(encoding="utf-8"))

    assert metadata is not None
    assert metadata["message_count"] == 4
    assert metadata["recent_message_count"] == 2
    assert metadata["compressed_message_count"] == 2
    assert metadata["has_compressed_context"] is True
    assert metadata["compressed_summary"] is not None
    assert metadata["context_strategy_version"] == 1
    assert session_payload["metadata"]["message_count"] == 4
    assert session_payload["metadata"]["compressed_message_count"] == 2
    assert session_payload["metadata"]["compressed_summary"] is not None
    assert session_payload["metadata"]["context_strategy_version"] == 1
    assert session_payload["metadata"]["updated_at"] is not None


def test_conversation_store_reuses_persisted_summary_cache_on_reload(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(settings, "conversation_context_recent_messages", 2)
    session_id = store.get_or_create_session_id("session-summary-cache-demo")
    store.append_exchange(
        session_id,
        user_prompt="first question with extra words",
        assistant_output="first answer with extra words",
    )
    store.append_exchange(
        session_id,
        user_prompt="second question with extra words",
        assistant_output="second answer with extra words",
    )
    store.append_exchange(
        session_id,
        user_prompt="third question with extra words",
        assistant_output="third answer with extra words",
    )

    reloaded_store = ConversationStore()
    monkeypatch.setattr(
        reloaded_store,
        "_build_history_summary",
        lambda messages: (_ for _ in ()).throw(RuntimeError("summary should be reused from cache")),
    )

    context = reloaded_store.build_context(session_id)

    assert context is not None
    assert "Compressed earlier conversation summary:" in context
    assert "Recent stored conversation history:" in context


def test_conversation_store_rebuilds_summary_cache_when_context_config_changes(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(settings, "conversation_context_recent_messages", 2)
    session_id = store.get_or_create_session_id("session-summary-rebuild-demo")
    store.append_exchange(
        session_id,
        user_prompt="first question with extra words",
        assistant_output="first answer with extra words",
    )
    store.append_exchange(
        session_id,
        user_prompt="second question with extra words",
        assistant_output="second answer with extra words",
    )
    store.append_exchange(
        session_id,
        user_prompt="third question with extra words",
        assistant_output="third answer with extra words",
    )

    reloaded_store = ConversationStore()
    monkeypatch.setattr(settings, "conversation_context_recent_messages", 3)
    original_build_history_summary = reloaded_store._build_history_summary
    call_counter = {"count": 0}

    def tracked_build_history_summary(messages):
        call_counter["count"] += 1
        return original_build_history_summary(messages)

    monkeypatch.setattr(
        reloaded_store,
        "_build_history_summary",
        tracked_build_history_summary,
    )

    context = reloaded_store.build_context(session_id)
    metadata = reloaded_store.get_session_metadata(session_id)

    assert context is not None
    assert call_counter["count"] >= 1
    assert metadata is not None
    assert metadata["context_recent_messages_limit"] == 3


def test_conversation_store_lists_sessions_with_metadata(monkeypatch):
    store = ConversationStore()
    monkeypatch.setattr(settings, "conversation_context_recent_messages", 2)

    store.append_exchange(
        "session-list-1",
        user_prompt="first prompt",
        assistant_output="first reply",
    )
    store.append_exchange(
        "session-list-2",
        user_prompt="second prompt",
        assistant_output="second reply",
    )
    store.append_exchange(
        "session-list-2",
        user_prompt="second prompt again",
        assistant_output="second reply again",
    )

    total, items = store.list_sessions(offset=0, limit=10)
    page_total, page_items = store.list_sessions(offset=1, limit=1)

    assert total == 2
    assert len(items) == 2
    assert items[0]["session_id"] == "session-list-2"
    assert items[0]["message_count"] == 4
    assert items[0]["has_summary_cache"] is True
    assert items[0]["context_strategy_version"] == 1
    assert items[1]["session_id"] == "session-list-1"
    assert items[1]["has_summary_cache"] is False
    assert page_total == 2
    assert len(page_items) == 1
    assert page_items[0]["session_id"] == "session-list-1"


def test_conversation_store_clear_session_returns_state():
    store = ConversationStore()
    session_id = store.get_or_create_session_id()
    store.append_message(session_id, "user", "hello")

    assert store.clear_session(session_id) is True
    assert store.clear_session(session_id) is False
    assert store.get_messages(session_id) == []
    assert store.get_session_metadata(session_id) is None


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
