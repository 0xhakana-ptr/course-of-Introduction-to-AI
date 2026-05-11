import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.main import app
from backend.app.message_queue import message_queue
from backend.app.storage.conversation_store import conversation_store


@pytest.fixture(autouse=True)
def isolate_backend_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "")
    monkeypatch.setattr(settings, "llm_fallback_base_url", "")
    monkeypatch.setattr(settings, "llm_fallback_api_key", "")
    monkeypatch.setattr(settings, "llm_fallback_model", "")
    monkeypatch.setattr(settings, "llm_fallback_timeout_seconds", settings.llm_timeout_seconds)
    monkeypatch.setattr(settings, "conversation_history_max_messages", 20)
    monkeypatch.setattr(settings, "conversation_context_recent_messages", 8)
    monkeypatch.setattr(settings, "conversation_summary_max_chars", 1200)
    monkeypatch.setattr(settings, "chat_context_max_chars", 6000)
    monkeypatch.setattr(settings, "chat_external_context_max_chars", 2000)
    monkeypatch.setattr(settings, "conversation_recent_message_max_chars", 800)
    monkeypatch.setattr(settings, "desktop_export_enabled", False)
    monkeypatch.setattr(settings, "desktop_export_dir", None)
    monkeypatch.setattr(settings, "conversation_cleanup_interval_seconds", 0)
    monkeypatch.setattr(settings, "conversation_session_ttl_seconds", 3600)
    monkeypatch.setattr(settings, "conversation_max_persisted_sessions", 200)
    workspace_dir = tmp_path / "workspace"
    runs_dir = workspace_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "workspace_dir", workspace_dir)
    monkeypatch.setattr(settings, "runs_dir", runs_dir)
    message_queue.clear()
    conversation_store.clear_all()
    yield
    message_queue.clear()
    conversation_store.clear_all()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
