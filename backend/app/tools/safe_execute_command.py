import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Callable

from ..core.config import settings
from .safe_fs import ensure_workspace_dirs, get_workspace_dir, resolve_workspace_path


BLOCKED_EXECUTABLES = {
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
    "sh",
    "bash",
}

BLOCKED_ARGUMENT_TOKENS = {
    "rm",
    "rmdir",
    "del",
    "format",
    "shutdown",
    "taskkill",
    "remove-item",
    "/c",
    "-c",
    "-command",
    "--command",
}


def normalize_command(command: Sequence[str]) -> list[str]:
    normalized = [str(part).strip() for part in command if str(part).strip()]
    if not normalized:
        raise ValueError("命令不能为空")
    return normalized


def is_blocked_command(command: Sequence[str]) -> bool:
    normalized = normalize_command(command)
    executable = Path(normalized[0]).name.lower()
    if executable in BLOCKED_EXECUTABLES:
        return True

    arguments = [part.lower() for part in normalized[1:]]
    return any(argument in BLOCKED_ARGUMENT_TOKENS for argument in arguments)


def safe_execute_command(
    command: Sequence[str],
    cwd: str | None = None,
    timeout_seconds: int | None = None,
    *,
    cancel_requested: Callable[[], bool] | None = None,
    on_process_start: Callable[[subprocess.Popen[str]], None] | None = None,
    on_process_end: Callable[[subprocess.Popen[str]], None] | None = None,
) -> dict[str, object]:
    normalized_command = normalize_command(command)
    if is_blocked_command(normalized_command):
        raise PermissionError("命令被安全策略拦截")

    ensure_workspace_dirs()
    working_dir = get_workspace_dir() if cwd is None else resolve_workspace_path(cwd)
    timeout = timeout_seconds or settings.command_timeout_seconds

    if cancel_requested and cancel_requested():
        return {
            "ok": False,
            "cancelled": True,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "cwd": str(working_dir),
            "error": "命令执行已取消",
        }

    def finalize_process(
        process: subprocess.Popen[str],
        error_message: str,
        *,
        cancelled: bool = False,
        returncode_override: int | None | object = ...,
    ) -> dict[str, object]:
        if process.poll() is None:
            try:
                process.terminate()
                stdout, stderr = process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
        else:
            stdout, stderr = process.communicate()

        return {
            "ok": False,
            "cancelled": cancelled,
            "returncode": (
                process.returncode
                if returncode_override is ...
                else returncode_override
            ),
            "stdout": stdout,
            "stderr": stderr,
            "cwd": str(working_dir),
            "error": error_message,
        }

    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            normalized_command,
            shell=False,
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if on_process_start is not None:
            on_process_start(process)

        started_at = time.monotonic()
        poll_interval = 0.2

        while True:
            if cancel_requested and cancel_requested():
                return finalize_process(process, "命令执行已取消", cancelled=True)

            elapsed = time.monotonic() - started_at
            if timeout is not None:
                remaining = timeout - elapsed
                if remaining <= 0:
                    return finalize_process(
                        process,
                        f"命令执行超时（>{timeout}s）",
                        returncode_override=None,
                    )
                wait_timeout = min(poll_interval, remaining)
            else:
                wait_timeout = poll_interval

            try:
                stdout, stderr = process.communicate(timeout=wait_timeout)
                was_cancelled = bool(cancel_requested and cancel_requested())
                if was_cancelled:
                    return {
                        "ok": False,
                        "cancelled": True,
                        "returncode": process.returncode,
                        "stdout": stdout,
                        "stderr": stderr,
                        "cwd": str(working_dir),
                        "error": "命令执行已取消",
                    }
                return {
                    "ok": process.returncode == 0,
                    "cancelled": False,
                    "returncode": process.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "cwd": str(working_dir),
                }
            except subprocess.TimeoutExpired:
                continue
    finally:
        if process is not None and on_process_end is not None:
            on_process_end(process)
