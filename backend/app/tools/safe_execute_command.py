import subprocess
from collections.abc import Sequence
from pathlib import Path

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
) -> dict[str, object]:
    normalized_command = normalize_command(command)
    if is_blocked_command(normalized_command):
        raise PermissionError("命令被安全策略拦截")

    ensure_workspace_dirs()
    working_dir = get_workspace_dir() if cwd is None else resolve_workspace_path(cwd)
    timeout = timeout_seconds or settings.command_timeout_seconds

    try:
        completed = subprocess.run(
            normalized_command,
            shell=False,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "cwd": str(working_dir),
            "error": f"命令执行超时（>{timeout}s）",
        }

    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "cwd": str(working_dir),
    }
