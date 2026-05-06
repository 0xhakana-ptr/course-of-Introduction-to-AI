import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env")


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

        self.llm_base_url = os.getenv("LLM_BASE_URL", "").strip()
        self.llm_api_key = os.getenv("LLM_API_KEY", "").strip()
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
        self.llm_system_prompt = os.getenv(
            "LLM_SYSTEM_PROMPT",
            "You are a helpful AI assistant for an educational desktop AI project.",
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


settings = Settings()
