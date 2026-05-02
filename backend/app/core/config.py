import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        backend_root = Path(__file__).resolve().parents[2]
        project_root = backend_root.parent

        self.app_version = os.getenv("APP_VERSION", "0.2.0").strip()
        self.project_root = project_root
        self.backend_root = backend_root
        self.workspace_dir = backend_root / "workspace"
        self.runs_dir = self.workspace_dir / "runs"

        self.llm_base_url = os.getenv("LLM_BASE_URL", "").strip()
        self.llm_api_key = os.getenv("LLM_API_KEY", "").strip()
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()

        timeout_raw = os.getenv("COMMAND_TIMEOUT_SECONDS", "15").strip()
        self.command_timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 15


settings = Settings()
