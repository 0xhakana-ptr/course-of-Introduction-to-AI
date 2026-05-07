import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env")


DEFAULT_LLM_SYSTEM_PROMPT = """
你是一个运行在 Live2D 桌宠中的 AI 伙伴。
请优先使用自然、清楚、友好的中文回答。
你可以有轻松的语气，但专业问题要认真、准确、分步骤说明。
不要假装已经执行了你没有执行的操作。
如果用户提出代码或工具任务，可以说明将通过后端任务流程处理。
""".strip()


class Settings:
    def __init__(self) -> None:
        backend_root = BACKEND_ROOT
        project_root = backend_root.parent

        self.app_version = os.getenv("APP_VERSION", "0.2.0").strip()
        self.log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
        self.project_root = project_root
        self.backend_root = backend_root
        self.workspace_dir = backend_root / "workspace"
        self.runs_dir = self.workspace_dir / "runs"
        self.conversation_dir_name = (
            os.getenv("CONVERSATION_DIR_NAME", "conversations").strip() or "conversations"
        )

        self.llm_base_url = os.getenv("LLM_BASE_URL", "").strip()
        self.llm_api_key = os.getenv("LLM_API_KEY", "").strip()
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
        self.llm_system_prompt = os.getenv(
            "LLM_SYSTEM_PROMPT",
            DEFAULT_LLM_SYSTEM_PROMPT,
        ).strip()

        llm_timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", "30").strip()
        self.llm_timeout_seconds = int(llm_timeout_raw) if llm_timeout_raw.isdigit() else 30

        self.llm_fallback_base_url = os.getenv("LLM_FALLBACK_BASE_URL", "").strip()
        self.llm_fallback_api_key = os.getenv("LLM_FALLBACK_API_KEY", "").strip()
        self.llm_fallback_model = os.getenv("LLM_FALLBACK_MODEL", "").strip()

        llm_fallback_timeout_raw = os.getenv("LLM_FALLBACK_TIMEOUT_SECONDS", "").strip()
        if llm_fallback_timeout_raw.isdigit():
            self.llm_fallback_timeout_seconds = int(llm_fallback_timeout_raw)
        else:
            self.llm_fallback_timeout_seconds = self.llm_timeout_seconds

        timeout_raw = os.getenv("COMMAND_TIMEOUT_SECONDS", "15").strip()
        self.command_timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 15

        repair_attempts_raw = os.getenv("RUN_REPAIR_MAX_ATTEMPTS", "1").strip()
        self.run_repair_max_attempts = (
            int(repair_attempts_raw) if repair_attempts_raw.isdigit() else 1
        )

        history_max_raw = os.getenv("CONVERSATION_HISTORY_MAX_MESSAGES", "20").strip()
        self.conversation_history_max_messages = (
            int(history_max_raw) if history_max_raw.isdigit() else 20
        )

        chat_context_max_raw = os.getenv("CHAT_CONTEXT_MAX_CHARS", "6000").strip()
        self.chat_context_max_chars = (
            int(chat_context_max_raw) if chat_context_max_raw.isdigit() else 6000
        )

        cleanup_interval_raw = os.getenv("CONVERSATION_CLEANUP_INTERVAL_SECONDS", "60").strip()
        self.conversation_cleanup_interval_seconds = (
            int(cleanup_interval_raw) if cleanup_interval_raw.isdigit() else 60
        )

        session_ttl_raw = os.getenv("CONVERSATION_SESSION_TTL_SECONDS", "604800").strip()
        self.conversation_session_ttl_seconds = (
            int(session_ttl_raw) if session_ttl_raw.isdigit() else 604800
        )

        max_persisted_raw = os.getenv("CONVERSATION_MAX_PERSISTED_SESSIONS", "200").strip()
        self.conversation_max_persisted_sessions = (
            int(max_persisted_raw) if max_persisted_raw.isdigit() else 200
        )

    @property
    def conversation_dir(self) -> Path:
        return self.workspace_dir / self.conversation_dir_name


settings = Settings()
