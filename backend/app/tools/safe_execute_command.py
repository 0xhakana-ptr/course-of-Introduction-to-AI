import subprocess

from backend.app.core.config import settings
from backend.app.tools.safe_fs import WORKSPACE_DIR, ensure_workspace_dirs, resolve_workspace_path


BLOCKED_TOKENS = (
    "rm ",
    "rmdir",
    "del ",
    "format ",
    "shutdown",
    "taskkill",
    "remove-item",
)


def is_blocked_command(command: str) -> bool:
    normalized = f" {command.strip().lower()} "
    return any(token in normalized for token in BLOCKED_TOKENS)


def safe_execute_command(
    command: str,
    cwd: str | None = None,
    timeout_seconds: int | None = None,
) -> dict[str, object]:
    if not command.strip():
        raise ValueError("命令不能为空")
    if is_blocked_command(command):
        raise PermissionError("命令被安全策略拦截")

    ensure_workspace_dirs()
    working_dir = WORKSPACE_DIR if cwd is None else resolve_workspace_path(cwd)
    timeout = timeout_seconds or settings.command_timeout_seconds

    try:
        completed = subprocess.run(
            command,
            shell=True,
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
