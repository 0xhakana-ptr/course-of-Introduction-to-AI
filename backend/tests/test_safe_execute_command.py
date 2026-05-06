import sys
import threading
import time

import pytest

from backend.app.tools.safe_execute_command import safe_execute_command
from backend.app.tools.safe_fs import safe_write_file


def test_safe_execute_command_blocks_shell_executables():
    with pytest.raises(PermissionError):
        safe_execute_command(["powershell", "-Command", "Write-Host hello"])


def test_safe_execute_command_blocks_dangerous_argument_tokens():
    with pytest.raises(PermissionError):
        safe_execute_command([sys.executable, "-c", "print('hello')"])


def test_safe_execute_command_runs_python_script_inside_workspace():
    safe_write_file("scripts/echo.py", 'print("safe execution ok")\n')

    result = safe_execute_command([sys.executable, "echo.py"], cwd="scripts")

    assert result["ok"] is True
    assert result["returncode"] == 0
    assert "safe execution ok" in str(result["stdout"])
    assert str(result["stderr"]) == ""


def test_safe_execute_command_returns_timeout_result():
    safe_write_file(
        "scripts/sleep.py",
        "import time\n"
        "time.sleep(2)\n"
        'print("done")\n',
    )

    result = safe_execute_command(
        [sys.executable, "sleep.py"],
        cwd="scripts",
        timeout_seconds=1,
    )

    assert result["ok"] is False
    assert result["returncode"] is None
    assert "命令执行超时" in str(result["error"])


def test_safe_execute_command_returns_cancelled_result():
    safe_write_file(
        "scripts/cancel_me.py",
        "import time\n"
        'print("start")\n'
        "time.sleep(5)\n"
        'print("done")\n',
    )
    cancel_event = threading.Event()

    def trigger_cancel() -> None:
        time.sleep(0.3)
        cancel_event.set()

    thread = threading.Thread(target=trigger_cancel, daemon=True)
    thread.start()

    result = safe_execute_command(
        [sys.executable, "cancel_me.py"],
        cwd="scripts",
        timeout_seconds=10,
        cancel_requested=cancel_event.is_set,
    )

    thread.join(timeout=2)
    assert result["ok"] is False
    assert result["cancelled"] is True
    assert "命令执行已取消" in str(result["error"])
