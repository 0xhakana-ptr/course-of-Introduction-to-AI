import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.app.core.config import settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_runs_dir() -> None:
    settings.runs_dir.mkdir(parents=True, exist_ok=True)


def run_dir(run_id: str) -> Path:
    ensure_runs_dir()
    return settings.runs_dir / run_id


def run_file(run_id: str) -> Path:
    return run_dir(run_id) / "result.json"


def save_run_record(run_id: str, data: dict[str, object]) -> dict[str, object]:
    target_dir = run_dir(run_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = run_file(run_id)
    target_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data


def create_run_record(prompt: str, context: str | None, status: str, output: str) -> dict[str, object]:
    run_id = str(uuid4())
    timestamp = utc_now_iso()
    data = {
        "run_id": run_id,
        "prompt": prompt,
        "context": context,
        "status": status,
        "output": output,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    return save_run_record(run_id, data)


def load_run_record(run_id: str) -> dict[str, object] | None:
    target = run_file(run_id)
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))
