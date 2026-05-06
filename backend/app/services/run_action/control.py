import subprocess
import threading
from dataclasses import dataclass, field


@dataclass(slots=True)
class RunControlEntry:
    cancel_event: threading.Event = field(default_factory=threading.Event)
    process: subprocess.Popen[str] | None = None


_RUN_CONTROL_REGISTRY: dict[str, RunControlEntry] = {}
_RUN_CONTROL_LOCK = threading.Lock()


def _ensure_run_control_unlocked(run_id: str) -> RunControlEntry:
    entry = _RUN_CONTROL_REGISTRY.get(run_id)
    if entry is None:
        entry = RunControlEntry()
        _RUN_CONTROL_REGISTRY[run_id] = entry
    return entry


def ensure_run_control(run_id: str) -> RunControlEntry:
    with _RUN_CONTROL_LOCK:
        return _ensure_run_control_unlocked(run_id)


def is_run_cancel_requested(run_id: str) -> bool:
    with _RUN_CONTROL_LOCK:
        entry = _RUN_CONTROL_REGISTRY.get(run_id)
        return bool(entry and entry.cancel_event.is_set())


def register_run_process(run_id: str, process: subprocess.Popen[str]) -> None:
    should_terminate = False
    with _RUN_CONTROL_LOCK:
        entry = _ensure_run_control_unlocked(run_id)
        entry.process = process
        should_terminate = entry.cancel_event.is_set()

    if should_terminate and process.poll() is None:
        try:
            process.terminate()
        except OSError:
            pass


def clear_run_process(run_id: str, process: subprocess.Popen[str] | None = None) -> None:
    with _RUN_CONTROL_LOCK:
        entry = _RUN_CONTROL_REGISTRY.get(run_id)
        if entry is None:
            return
        if process is not None and entry.process is not process:
            return
        entry.process = None


def request_run_cancel(run_id: str) -> bool:
    process: subprocess.Popen[str] | None
    already_requested = False

    with _RUN_CONTROL_LOCK:
        entry = _ensure_run_control_unlocked(run_id)
        already_requested = entry.cancel_event.is_set()
        entry.cancel_event.set()
        process = entry.process

    if process is not None and process.poll() is None:
        try:
            process.terminate()
        except OSError:
            pass

    return not already_requested


def clear_run_control(run_id: str) -> None:
    with _RUN_CONTROL_LOCK:
        _RUN_CONTROL_REGISTRY.pop(run_id, None)
