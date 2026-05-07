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
