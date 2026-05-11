import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env")


DEFAULT_LLM_SYSTEM_PROMPT = """
你是一个运行在 Live2D 桌宠中的 AI 伙伴。
你也是前台看板娘，回复应自然、清楚、偏口语化，并保留轻微角色感。
普通聊天时先直接回应用户，不要把自己说成通用客服或文档机器人。
专业问题要认真、准确、分步骤说明，但不要故意堆术语。
除非用户明确要求查看详细日志，否则不要把冗长的原始报错、堆栈或工程噪声直接倾倒给用户，优先给出简短总结和下一步建议。
不要假装已经执行了你没有执行的操作。
如果用户提出代码或工具任务，可以说明将通过后端任务流程处理。
""".strip()

DEFAULT_CONVERSATION_CONTEXT_RECENT_MESSAGES = 8
DEFAULT_CONVERSATION_SUMMARY_MAX_CHARS = 1200


def _read_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        normalized = value.strip()
        if normalized:
            return normalized
    return default.strip()


def _read_bool_env(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
        self.desktop_export_enabled = _read_bool_env("DESKTOP_EXPORT_ENABLED", default=False)
        desktop_export_dir = _read_env("DESKTOP_EXPORT_DIR")
        self.desktop_export_dir = (
            Path(desktop_export_dir).expanduser().resolve()
            if desktop_export_dir
            else None
        )
        self.llm_base_url = _read_env("LLM_BASE_URL", "OPENAI_BASE_URL")
        self.llm_chat_completions_url = _read_env("LLM_CHAT_COMPLETIONS_URL")
        self.llm_provider_profile = _read_env("LLM_PROVIDER_PROFILE")
        self.llm_api_key = _read_env("LLM_API_KEY", "OPENAI_API_KEY")
        self.llm_model = _read_env("LLM_MODEL", "OPENAI_MODEL", default="gpt-4o-mini")
        self.llm_system_prompt = os.getenv(
            "LLM_SYSTEM_PROMPT",
            DEFAULT_LLM_SYSTEM_PROMPT,
        ).strip()

        llm_timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", "30").strip()
        self.llm_timeout_seconds = int(llm_timeout_raw) if llm_timeout_raw.isdigit() else 30

        self.llm_fallback_base_url = _read_env("LLM_FALLBACK_BASE_URL")
        self.llm_fallback_chat_completions_url = _read_env("LLM_FALLBACK_CHAT_COMPLETIONS_URL")
        self.llm_fallback_provider_profile = _read_env("LLM_FALLBACK_PROVIDER_PROFILE")
        self.llm_fallback_api_key = _read_env("LLM_FALLBACK_API_KEY")
        self.llm_fallback_model = _read_env("LLM_FALLBACK_MODEL")

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

        recent_messages_raw = os.getenv(
            "CONVERSATION_CONTEXT_RECENT_MESSAGES",
            str(DEFAULT_CONVERSATION_CONTEXT_RECENT_MESSAGES),
        ).strip()
        self.conversation_context_recent_messages = (
            int(recent_messages_raw)
            if recent_messages_raw.isdigit()
            else DEFAULT_CONVERSATION_CONTEXT_RECENT_MESSAGES
        )

        summary_max_raw = os.getenv(
            "CONVERSATION_SUMMARY_MAX_CHARS",
            str(DEFAULT_CONVERSATION_SUMMARY_MAX_CHARS),
        ).strip()
        self.conversation_summary_max_chars = (
            int(summary_max_raw)
            if summary_max_raw.isdigit()
            else DEFAULT_CONVERSATION_SUMMARY_MAX_CHARS
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
