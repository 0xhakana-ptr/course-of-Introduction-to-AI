import asyncio

from backend.app.services.chat import ChatServiceResult
from backend.app.services.chat_interface import generate_chat_response
from backend.app.storage.conversation_store import ConversationStore, conversation_store


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


def test_chat_session_context_endpoint_returns_context_snapshot(monkeypatch, client):
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
    monkeypatch.setattr(
        "backend.app.core.config.settings.conversation_summary_max_chars",
        200,
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
    context_response = client.get(f"/chat/sessions/{session_id}/context")

    assert context_response.status_code == 200
    payload = context_response.json()
    assert payload["ok"] is True
    assert payload["exists"] is True
    assert payload["session_id"] == session_id
    assert payload["message_count"] == 6
    assert payload["recent_message_count"] == 2
    assert payload["compressed_message_count"] == 4
    assert payload["has_summary_cache"] is True
    assert payload["compressed_summary"]
    assert "Compressed earlier conversation summary:" in payload["context_text"]
    assert "Recent stored conversation history:" in payload["context_text"]
    assert len(payload["recent_messages"]) == 2
    assert payload["recent_messages"][0]["role"] == "user"
    assert payload["recent_messages"][0]["content"] == "third hello"
    assert payload["recent_messages"][1]["role"] == "assistant"
    assert payload["recent_messages"][1]["content"] == "reply to third hello"
    assert payload["context_char_count"] == len(payload["context_text"])


def test_chat_session_context_endpoint_returns_exists_false_for_unknown_session(client):
    response = client.get("/chat/sessions/not-found-session/context")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["exists"] is False
    assert payload["session_id"] == "not-found-session"
    assert payload["context_text"] is None
    assert payload["recent_messages"] == []


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


def test_generate_chat_response_marks_coding_schedule_failure(monkeypatch):
    async def fake_build_agent_reply(
        prompt: str,
        context: str | None,
        *,
        session_id: str | None = None,
        intent: str | None = None,
        emit_chat_message: bool = False,
    ):
        return ChatServiceResult(
            intent="coding",
            ok=True,
            output=(
                "我已经创建了代码任务，并交给后端执行。\n\n"
                "run_id: run-1"
            ),
            run_id="run-1",
            run_action="create",
        )

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_agent_reply",
        fake_build_agent_reply,
    )

    def broken_schedule(run_id: str) -> None:
        raise RuntimeError(f"schedule failed: {run_id}")

    result = asyncio.run(
        generate_chat_response(
            "write python code",
            None,
            schedule_run=broken_schedule,
        )
    )

    assert result.ok is False
    assert result.run_id == "run-1"
    assert result.session_id is not None
    assert "后台执行调度失败" in result.output
    assert "run_id:" not in result.output
    assert result.error == "schedule failed: run-1"

    stored_messages = conversation_store.get_messages(result.session_id)
    assert len(stored_messages) == 1
    assert stored_messages[0]["role"] == "user"
    assert stored_messages[0]["content"] == "write python code"


def test_generate_chat_response_does_not_force_chat_intent_hint(monkeypatch):
    seen_intents: list[str | None] = []

    async def fake_build_agent_reply(
        prompt: str,
        context: str | None,
        *,
        session_id: str | None = None,
        intent: str | None = None,
        emit_chat_message: bool = False,
    ):
        seen_intents.append(intent)
        return ChatServiceResult(intent="chat", ok=True, output=f"reply to {prompt}")

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_agent_reply",
        fake_build_agent_reply,
    )

    prompts = ["hello", "我是谁", "1+1=？", "FastAPI 是什么？"]
    for prompt in prompts:
        result = asyncio.run(generate_chat_response(prompt, None))
        assert result.ok is True
        assert result.intent == "chat"

    assert seen_intents == [None, None, None, None]


def test_generate_chat_response_keeps_operational_intent_hints(monkeypatch):
    seen_intents: list[str | None] = []

    async def fake_build_agent_reply(
        prompt: str,
        context: str | None,
        *,
        session_id: str | None = None,
        intent: str | None = None,
        emit_chat_message: bool = False,
    ):
        seen_intents.append(intent)
        return ChatServiceResult(
            intent="coding" if intent == "coding" else "unknown",
            ok=True,
            output="handled",
        )

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_agent_reply",
        fake_build_agent_reply,
    )

    coding_result = asyncio.run(generate_chat_response("请检查 main.py 的导入", None))
    unknown_result = asyncio.run(generate_chat_response("???", None))

    assert coding_result.intent == "coding"
    assert unknown_result.intent == "unknown"
    assert seen_intents == ["coding", "unknown"]


def test_generate_chat_response_schedules_retry_and_rerun_actions(monkeypatch):
    scheduled_run_ids: list[str] = []

    async def fake_build_agent_reply(
        prompt: str,
        context: str | None,
        *,
        session_id: str | None = None,
        intent: str | None = None,
        emit_chat_message: bool = False,
    ):
        if "retry" in prompt:
            return ChatServiceResult(
                intent="coding",
                ok=True,
                output=(
                    "我已为这个代码任务创建重试任务。\n\n"
                    "source_run_id: run-source-1\n"
                    "run_id: run-retry-1"
                ),
                run_id="run-retry-1",
                run_action="retry",
            )
        return ChatServiceResult(
            intent="coding",
            ok=True,
            output=(
                "我已为这个代码任务创建重新运行任务。\n\n"
                "source_run_id: run-source-2\n"
                "run_id: run-rerun-1"
            ),
            run_id="run-rerun-1",
            run_action="rerun",
        )

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_agent_reply",
        fake_build_agent_reply,
    )

    def remember_schedule(run_id: str) -> None:
        scheduled_run_ids.append(run_id)

    retry_result = asyncio.run(
        generate_chat_response(
            "请 retry run_id run-source-1",
            None,
            schedule_run=remember_schedule,
        )
    )
    rerun_result = asyncio.run(
        generate_chat_response(
            "请重新运行 run_id run-source-2",
            None,
            schedule_run=remember_schedule,
        )
    )

    assert scheduled_run_ids == ["run-retry-1", "run-rerun-1"]
    assert "并开始后台执行" in retry_result.output
    assert "并开始后台执行" in rerun_result.output
    assert "run_id:" not in retry_result.output
    assert "source_run_id:" not in retry_result.output
    assert "run_id:" not in rerun_result.output
    assert "source_run_id:" not in rerun_result.output


def test_generate_chat_response_does_not_schedule_run_snapshot_inspection(monkeypatch):
    scheduled_run_ids: list[str] = []

    async def fake_build_agent_reply(
        prompt: str,
        context: str | None,
        *,
        session_id: str | None = None,
        intent: str | None = None,
        emit_chat_message: bool = False,
    ):
        return ChatServiceResult(
            intent="coding",
            ok=True,
            output=(
                "我读取了这个代码任务的当前状态。\n\n"
                "run_id: run-1\n"
                "status: running\n"
                "当前快照: 任务正在执行中。\n"
                "下一步: 继续轮询任务状态。"
            ),
            run_id="run-1",
            run_action="inspect",
        )

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_agent_reply",
        fake_build_agent_reply,
    )

    def remember_schedule(run_id: str) -> None:
        scheduled_run_ids.append(run_id)

    result = asyncio.run(
        generate_chat_response(
            "请查看 run_id run-1 的状态",
            None,
            schedule_run=remember_schedule,
        )
    )

    assert result.ok is True
    assert result.run_id == "run-1"
    assert result.run_action == "inspect"
    assert scheduled_run_ids == []
    assert "run_id:" not in result.output
    assert "status:" not in result.output


def test_generate_chat_response_does_not_schedule_cancel_action(monkeypatch):
    scheduled_run_ids: list[str] = []

    async def fake_build_agent_reply(
        prompt: str,
        context: str | None,
        *,
        session_id: str | None = None,
        intent: str | None = None,
        emit_chat_message: bool = False,
    ):
        return ChatServiceResult(
            intent="coding",
            ok=True,
            output=(
                "我已处理这个代码任务的取消请求。\n\n"
                "run_id: run-1\n"
                "status: running\n"
                "当前快照: 任务已收到取消请求，正在结束执行。\n"
                "下一步: 等待当前执行结束并确认最终取消结果。"
            ),
            run_id="run-1",
            run_action="cancel",
        )

    monkeypatch.setattr(
        "backend.app.services.chat_interface.build_agent_reply",
        fake_build_agent_reply,
    )

    def remember_schedule(run_id: str) -> None:
        scheduled_run_ids.append(run_id)

    result = asyncio.run(
        generate_chat_response(
            "请取消 run_id run-1",
            None,
            schedule_run=remember_schedule,
        )
    )

    assert result.ok is True
    assert result.run_id == "run-1"
    assert result.run_action == "cancel"
    assert scheduled_run_ids == []
    assert "run_id:" not in result.output
    assert "status:" not in result.output
