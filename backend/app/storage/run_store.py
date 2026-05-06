import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..core.config import settings


RUN_DEFAULTS: dict[str, object] = {
    "generator": None,
    "attempt_count": 0,
    "repair_attempted": False,
    "repair_count": 0,
    "started_at": None,
    "finished_at": None,
    "duration_ms": None,
    "error": None,
    "command": None,
    "returncode": None,
    "stdout": None,
    "stderr": None,
    "log_path": None,
    "artifacts": [],
    "attempts": [],
}


ATTEMPT_DEFAULTS: dict[str, object] = {
    "generator": "unknown",
    "repair_round": 0,
    "status": "running",
    "source_file_name": None,
    "attempt_file_name": None,
    "script_rel_path": None,
    "command": None,
    "cwd": None,
    "returncode": None,
    "stdout": None,
    "stderr": None,
    "error": None,
    "started_at": None,
    "finished_at": None,
    "duration_ms": None,
}


_RUN_LOCKS: dict[str, threading.RLock] = {}
_RUN_LOCKS_GUARD = threading.Lock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def duration_ms_from_iso(started_at: str | None, finished_at: str | None) -> int | None:
    if not started_at or not finished_at:
        return None
    try:
        started = datetime.fromisoformat(started_at)
        finished = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    return max(0, int((finished - started).total_seconds() * 1000))


def ensure_runs_dir() -> None:
    settings.runs_dir.mkdir(parents=True, exist_ok=True)


def run_dir(run_id: str) -> Path:
    ensure_runs_dir()
    return settings.runs_dir / run_id


def run_file(run_id: str) -> Path:
    return run_dir(run_id) / "result.json"


def log_file(run_id: str) -> Path:
    return run_dir(run_id) / "log.txt"


def normalize_attempt_record(data: dict[str, object]) -> dict[str, object]:
    attempt = dict(data)
    for key, value in ATTEMPT_DEFAULTS.items():
        attempt.setdefault(key, value)
    attempt["duration_ms"] = duration_ms_from_iso(
        str(attempt["started_at"]) if attempt.get("started_at") is not None else None,
        str(attempt["finished_at"]) if attempt.get("finished_at") is not None else None,
    )
    return attempt


def normalize_run_record(data: dict[str, object]) -> dict[str, object]:
    record = dict(data)
    for key, value in RUN_DEFAULTS.items():
        if isinstance(value, list):
            record.setdefault(key, list(value))
        else:
            record.setdefault(key, value)

    attempts: list[dict[str, object]] = []
    raw_attempts = record.get("attempts", [])
    if isinstance(raw_attempts, list):
        for item in raw_attempts:
            if isinstance(item, dict):
                attempts.append(normalize_attempt_record(item))
    record["attempts"] = attempts
    record["duration_ms"] = duration_ms_from_iso(
        str(record["started_at"]) if record.get("started_at") is not None else None,
        str(record["finished_at"]) if record.get("finished_at") is not None else None,
    )
    return record


def get_run_lock(run_id: str) -> threading.RLock:
    with _RUN_LOCKS_GUARD:
        lock = _RUN_LOCKS.get(run_id)
        if lock is None:
            lock = threading.RLock()
            _RUN_LOCKS[run_id] = lock
        return lock


def write_json_atomic(target_file: Path, data: dict[str, object]) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    temp_file = target_file.with_name(f".{target_file.name}.{uuid4().hex}.tmp")
    try:
        with temp_file.open("w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        temp_file.replace(target_file)
    finally:
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)


def _save_run_record_unlocked(run_id: str, data: dict[str, object]) -> dict[str, object]:
    normalized = normalize_run_record(data)
    target_dir = run_dir(run_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = run_file(run_id)
    write_json_atomic(target_file, normalized)
    return normalized


def _load_run_record_unlocked(
    run_id: str,
    *,
    allow_invalid: bool = False,
) -> dict[str, object] | None:
    target = run_file(run_id)
    if not target.exists():
        return None

    try:
        raw_data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if allow_invalid:
            return None
        raise ValueError(f"run record is unreadable: {run_id}") from exc

    if not isinstance(raw_data, dict):
        if allow_invalid:
            return None
        raise ValueError(f"run record is invalid: {run_id}")

    return normalize_run_record(raw_data)


def save_run_record(run_id: str, data: dict[str, object]) -> dict[str, object]:
    with get_run_lock(run_id):
        return _save_run_record_unlocked(run_id, data)


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
    data.update(RUN_DEFAULTS)
    return save_run_record(run_id, data)


def load_run_record(run_id: str, *, allow_invalid: bool = False) -> dict[str, object] | None:
    with get_run_lock(run_id):
        return _load_run_record_unlocked(run_id, allow_invalid=allow_invalid)


def update_run_record(run_id: str, **fields) -> dict[str, object]:
    with get_run_lock(run_id):
        record = _load_run_record_unlocked(run_id)
        if record is None:
            raise FileNotFoundError(f"run not found: {run_id}")

        record.update(fields)
        record["updated_at"] = utc_now_iso()
        return _save_run_record_unlocked(run_id, record)


def append_run_attempt(run_id: str, attempt: dict[str, object]) -> dict[str, object]:
    with get_run_lock(run_id):
        record = _load_run_record_unlocked(run_id)
        if record is None:
            raise FileNotFoundError(f"run not found: {run_id}")

        attempts = [item for item in record.get("attempts", []) if isinstance(item, dict)]
        attempts.append(normalize_attempt_record(attempt))
        record["attempts"] = attempts
        record["updated_at"] = utc_now_iso()
        return _save_run_record_unlocked(run_id, record)


def update_run_attempt(run_id: str, attempt_number: int, **fields) -> dict[str, object]:
    with get_run_lock(run_id):
        record = _load_run_record_unlocked(run_id)
        if record is None:
            raise FileNotFoundError(f"run not found: {run_id}")

        attempts = [item for item in record.get("attempts", []) if isinstance(item, dict)]
        for index, attempt in enumerate(attempts):
            current_number = attempt.get("attempt_number")
            if isinstance(current_number, int) and current_number == attempt_number:
                updated_attempt = dict(attempt)
                updated_attempt.update(fields)
                attempts[index] = normalize_attempt_record(updated_attempt)
                record["attempts"] = attempts
                record["updated_at"] = utc_now_iso()
                return _save_run_record_unlocked(run_id, record)

        raise FileNotFoundError(f"attempt not found: {run_id}#{attempt_number}")


def list_run_records() -> list[dict[str, object]]:
    ensure_runs_dir()
    records: list[dict[str, object]] = []

    for child in settings.runs_dir.iterdir():
        if not child.is_dir():
            continue
        with get_run_lock(child.name):
            record = _load_run_record_unlocked(child.name, allow_invalid=True)
        if record is not None:
            records.append(record)

    records.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
    return records


def append_run_log(run_id: str, text: str) -> str:
    target = log_file(run_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{utc_now_iso()}] {text.rstrip()}\n"
    with target.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return str(target)


def read_run_log(run_id: str) -> str:
    target = log_file(run_id)
    if not target.exists():
        return ""
    return target.read_text(encoding="utf-8")
