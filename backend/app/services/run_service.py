import json
import re
import subprocess
import sys
from typing import Any

from backend.app.core.config import settings
from backend.app.llm.client import call_llm_sync, llm_is_configured
from backend.app.schemas import (
    ATTEMPT_OUTPUT_STREAM,
    RunAttemptListResponse,
    RunAttemptOutputChunkResponse,
    RunAttemptResponse,
    RunAttemptScriptResponse,
    RunLogResponse,
    RunResponse,
)
from backend.app.storage.run_store import (
    append_run_log,
    append_run_attempt,
    create_run_record,
    list_run_records,
    load_run_record,
    read_run_log,
    utc_now_iso,
    update_run_attempt,
    update_run_record,
)
from backend.app.tools.safe_execute_command import safe_execute_command
from backend.app.tools.safe_fs import safe_read_file, safe_write_file


CODE_SYSTEM_PROMPT = """
You are a Python code generator for an educational backend service.

Write exactly one runnable Python script that solves the user's request.
Return the answer in the following format:

FILENAME: <name>.py
```python
# code here
```

Rules:
- Output only one file.
- The script must be runnable with `python <file>.py`.
- Do not require user input.
- Prefer standard library only.
- Include a few print statements so the result is observable.
- Do not include explanations outside the required format.
""".strip()


CODE_REPAIR_SYSTEM_PROMPT = """
You are repairing a Python script for an educational backend service.

You will receive:
- the original user request
- optional context
- the previous Python script
- the execution command
- stdout / stderr / error details

Return exactly one repaired runnable Python script in the following format:

FILENAME: <name>.py
```python
# fixed code here
```

Rules:
- Output only one file.
- Preserve the original task intent.
- The script must be runnable with `python <file>.py`.
- Do not require user input.
- Prefer standard library only.
- Fix the reported issue directly.
- Include visible print statements so the result can be inspected.
- Do not include explanations outside the required format.
""".strip()


LLM_PREVIEW_LIMIT = 400
SUMMARY_PREVIEW_LIMIT = 120
ATTEMPT_OUTPUT_PREVIEW_LIMIT = 2000
ATTEMPT_OUTPUT_CHUNK_LIMIT = 4000
ATTEMPT_OUTPUT_CHUNK_MAX_LIMIT = 20000


def preview_single_line(text: str, limit: int = SUMMARY_PREVIEW_LIMIT) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def clip_text(text: str | None, limit: int = ATTEMPT_OUTPUT_PREVIEW_LIMIT) -> tuple[str | None, int, bool]:
    raw = text or ""
    total_length = len(raw)
    if total_length <= limit:
        return (raw or None), total_length, False
    return raw[:limit], total_length, True


def describe_generator(generator: str) -> str:
    generator_map = {
        "template": "本地模板",
        "llm": "LLM 生成",
        "llm_repair": "LLM 修复",
    }
    return generator_map.get(generator, generator)


def build_attempt_summary(record: dict[str, object]) -> str:
    attempt_number = int(record.get("attempt_number") or 0)
    repair_round = int(record.get("repair_round") or 0)
    status = str(record.get("status") or "running")
    generator = describe_generator(str(record.get("generator") or "unknown"))
    prefix = f"第 {attempt_number} 次尝试"
    if repair_round > 0:
        prefix += f"（第 {repair_round} 轮自动修复后，{generator}）"
    else:
        prefix += f"（{generator}）"

    returncode = record.get("returncode")
    duration_ms = record.get("duration_ms")
    suffix_parts: list[str] = []
    if isinstance(returncode, int):
        suffix_parts.append(f"返回码 {returncode}")
    if isinstance(duration_ms, int):
        suffix_parts.append(f"耗时 {duration_ms} ms")
    suffix = f"；{'，'.join(suffix_parts)}" if suffix_parts else ""

    if status == "running":
        return f"{prefix}：正在执行。"

    if status == "done":
        stdout = str(record.get("stdout") or "").strip()
        if stdout:
            return f"{prefix}：执行成功{suffix}。输出摘要：{preview_single_line(stdout)}"
        return f"{prefix}：执行成功{suffix}。"

    failure_text = (
        str(record.get("error") or "").strip()
        or str(record.get("stderr") or "").strip()
        or str(record.get("stdout") or "").strip()
        or "未提供更多错误信息"
    )
    return f"{prefix}：执行失败{suffix}。错误摘要：{preview_single_line(failure_text)}"


def get_attempt_records(record: dict[str, object]) -> list[dict[str, object]]:
    attempts = [
        item
        for item in record.get("attempts", [])
        if isinstance(item, dict) and item.get("attempt_number") is not None
    ]
    attempts.sort(key=lambda item: int(item.get("attempt_number") or 0))
    return attempts


def find_attempt_record(record: dict[str, object], attempt_number: int) -> dict[str, object] | None:
    for item in get_attempt_records(record):
        current_number = int(item.get("attempt_number") or 0)
        if current_number == attempt_number:
            return item
    return None


def to_run_attempt_response(record: dict[str, object]) -> RunAttemptResponse:
    stdout_value, stdout_length, stdout_truncated = clip_text(
        str(record.get("stdout")) if record.get("stdout") is not None else None
    )
    stderr_value, stderr_length, stderr_truncated = clip_text(
        str(record.get("stderr")) if record.get("stderr") is not None else None
    )
    error_value, error_length, error_truncated = clip_text(
        str(record.get("error")) if record.get("error") is not None else None
    )
    script_rel_path = str(record["script_rel_path"]) if record.get("script_rel_path") is not None else None
    return RunAttemptResponse(
        attempt_number=int(record["attempt_number"]),
        generator=str(record["generator"]),
        repair_round=int(record["repair_round"]) if record.get("repair_round") is not None else 0,
        status=str(record["status"]),
        summary=build_attempt_summary(record),
        source_file_name=(
            str(record["source_file_name"]) if record.get("source_file_name") is not None else None
        ),
        attempt_file_name=(
            str(record["attempt_file_name"]) if record.get("attempt_file_name") is not None else None
        ),
        script_rel_path=script_rel_path,
        command=str(record["command"]) if record.get("command") is not None else None,
        cwd=str(record["cwd"]) if record.get("cwd") is not None else None,
        returncode=int(record["returncode"]) if record.get("returncode") is not None else None,
        stdout=stdout_value,
        stdout_length=stdout_length,
        stdout_truncated=stdout_truncated,
        stderr=stderr_value,
        stderr_length=stderr_length,
        stderr_truncated=stderr_truncated,
        error=error_value,
        error_length=error_length,
        error_truncated=error_truncated,
        script_available=script_rel_path is not None,
        started_at=str(record["started_at"]) if record.get("started_at") is not None else None,
        finished_at=str(record["finished_at"]) if record.get("finished_at") is not None else None,
        duration_ms=int(record["duration_ms"]) if record.get("duration_ms") is not None else None,
    )


def to_run_response(record: dict[str, object]) -> RunResponse:
    return RunResponse(
        run_id=str(record["run_id"]),
        status=str(record["status"]),
        output=str(record["output"]),
        created_at=str(record["created_at"]),
        updated_at=str(record["updated_at"]),
        generator=str(record["generator"]) if record.get("generator") is not None else None,
        attempt_count=int(record["attempt_count"]) if record.get("attempt_count") is not None else 0,
        repair_attempted=bool(record.get("repair_attempted", False)),
        repair_count=int(record["repair_count"]) if record.get("repair_count") is not None else 0,
        started_at=str(record["started_at"]) if record.get("started_at") is not None else None,
        finished_at=str(record["finished_at"]) if record.get("finished_at") is not None else None,
        duration_ms=int(record["duration_ms"]) if record.get("duration_ms") is not None else None,
        error=str(record["error"]) if record.get("error") is not None else None,
        prompt=str(record["prompt"]) if record.get("prompt") is not None else None,
        context=str(record["context"]) if record.get("context") is not None else None,
        command=str(record["command"]) if record.get("command") is not None else None,
        returncode=int(record["returncode"]) if record.get("returncode") is not None else None,
        stdout=str(record["stdout"]) if record.get("stdout") is not None else None,
        stderr=str(record["stderr"]) if record.get("stderr") is not None else None,
        log_path=str(record["log_path"]) if record.get("log_path") is not None else None,
        artifacts=[str(item) for item in record.get("artifacts", []) if isinstance(item, str)],
        attempts=[
            to_run_attempt_response(item)
            for item in get_attempt_records(record)
        ],
    )


def build_default_script(prompt: str) -> tuple[str, str]:
    safe_prompt = json.dumps(prompt, ensure_ascii=False)
    return (
        "hello.py",
        (
            'print("Demo coding task executed successfully.")\n'
            f"print('Prompt:', {safe_prompt})\n"
        ),
    )


def build_calculator_script() -> tuple[str, str]:
    return (
        "calculator.py",
        (
            "def add(a, b):\n"
            "    return a + b\n\n"
            "def subtract(a, b):\n"
            "    return a - b\n\n"
            'print("Calculator demo:")\n'
            'print("3 + 5 =", add(3, 5))\n'
            'print("9 - 4 =", subtract(9, 4))\n'
        ),
    )


def build_fibonacci_script() -> tuple[str, str]:
    return (
        "fibonacci.py",
        (
            "def fibonacci(n):\n"
            "    seq = []\n"
            "    a, b = 0, 1\n"
            "    for _ in range(n):\n"
            "        seq.append(a)\n"
            "        a, b = b, a + b\n"
            "    return seq\n\n"
            'print("Fibonacci demo:")\n'
            'print(fibonacci(10))\n'
        ),
    )


def build_failure_script() -> tuple[str, str]:
    return (
        "broken_demo.py",
        (
            'print("This demo will fail intentionally.")\n'
            'raise RuntimeError("Intentional demo failure")\n'
        ),
    )


def choose_demo_script(prompt: str) -> tuple[str, str]:
    text = prompt.lower()
    if any(keyword in text for keyword in ("calculator", "计算器", "加减", "四则运算")):
        return build_calculator_script()
    if any(keyword in text for keyword in ("fibonacci", "斐波那契", "数列")):
        return build_fibonacci_script()
    if any(keyword in text for keyword in ("error", "fail", "broken", "bug")):
        return build_failure_script()
    return build_default_script(prompt)


def sanitize_filename(name: str | None, fallback: str = "main.py") -> str:
    raw = (name or "").strip()
    if not raw:
        return fallback
    cleaned = raw.replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", cleaned)
    if not cleaned.endswith(".py"):
        cleaned += ".py"
    return cleaned or fallback


def build_attempt_filename(file_name: str, attempt_number: int) -> str:
    safe_name = sanitize_filename(file_name)
    return f"attempt_{attempt_number}_{safe_name}"


def extract_filename(raw_text: str) -> str | None:
    match = re.search(r"FILENAME:\s*([^\s]+)", raw_text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def extract_python_code(raw_text: str) -> str | None:
    fenced = re.search(r"```python\s*(.*?)```", raw_text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        code = fenced.group(1).strip()
        return code or None

    generic = re.search(r"```(?:\w+)?\s*(.*?)```", raw_text, flags=re.DOTALL)
    if generic:
        code = generic.group(1).strip()
        return code or None

    stripped = raw_text.strip()
    python_markers = ("def ", "import ", "from ", "print(", "class ", "if __name__")
    if any(marker in stripped for marker in python_markers):
        return stripped
    return None


def preview_text(text: str, limit: int = LLM_PREVIEW_LIMIT) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def format_artifacts(artifacts: list[str]) -> str:
    if not artifacts:
        return "(none)"
    return "\n".join(f"- {artifact}" for artifact in artifacts)


def validate_python_script(file_name: str, script_content: str) -> str | None:
    try:
        compile(script_content, file_name, "exec")
    except SyntaxError as exc:
        details = f"SyntaxError: {exc.msg} (line {exc.lineno}, column {exc.offset})"
        if exc.text:
            details = f"{details}\n{exc.text.rstrip()}"
        return details
    return None


def build_repair_prompt(
    prompt: str,
    context: str | None,
    file_name: str,
    script_content: str,
    failure_result: dict[str, Any],
) -> str:
    command = str(failure_result.get("command") or "(not executed)")
    returncode = failure_result.get("returncode")
    stdout = str(failure_result.get("stdout") or "").strip() or "(empty)"
    stderr = str(failure_result.get("stderr") or "").strip() or "(empty)"
    error = str(failure_result.get("error") or "").strip() or "(none)"

    return (
        "Original user request:\n"
        f"{prompt}\n\n"
        "Optional context:\n"
        f"{context or '(none)'}\n\n"
        "Previous filename:\n"
        f"{file_name}\n\n"
        "Previous code:\n"
        f"```python\n{script_content}\n```\n\n"
        "Execution command:\n"
        f"{command}\n\n"
        "Return code:\n"
        f"{returncode}\n\n"
        "stdout:\n"
        f"{stdout}\n\n"
        "stderr:\n"
        f"{stderr}\n\n"
        "error:\n"
        f"{error}\n\n"
        "Please repair the script and return only the required formatted result."
    )


def generate_script_with_llm(prompt: str, context: str | None) -> tuple[str, str, str] | None:
    if not llm_is_configured():
        return None

    raw = call_llm_sync(
        prompt=prompt,
        context=context,
        system_prompt=CODE_SYSTEM_PROMPT,
        temperature=0.2,
    )

    code = extract_python_code(raw)
    if not code:
        return None

    filename = sanitize_filename(extract_filename(raw), fallback="main.py")
    return filename, code, raw


def generate_repaired_script_with_llm(
    prompt: str,
    context: str | None,
    file_name: str,
    script_content: str,
    failure_result: dict[str, Any],
) -> tuple[str, str, str] | None:
    if not llm_is_configured():
        return None

    raw = call_llm_sync(
        prompt=build_repair_prompt(prompt, context, file_name, script_content, failure_result),
        context=None,
        system_prompt=CODE_REPAIR_SYSTEM_PROMPT,
        temperature=0.1,
    )

    code = extract_python_code(raw)
    if not code:
        return None

    filename = sanitize_filename(extract_filename(raw), fallback=file_name)
    return filename, code, raw


def build_attempt_record(
    generated_dir: str,
    file_name: str,
    attempt_number: int,
    generator: str,
    repair_round: int,
) -> dict[str, object]:
    source_file_name = sanitize_filename(file_name)
    attempt_file_name = build_attempt_filename(source_file_name, attempt_number)
    command = subprocess.list2cmdline([sys.executable, attempt_file_name])
    return {
        "attempt_number": attempt_number,
        "generator": generator,
        "repair_round": repair_round,
        "status": "running",
        "source_file_name": source_file_name,
        "attempt_file_name": attempt_file_name,
        "script_rel_path": f"{generated_dir}/{attempt_file_name}",
        "command": command,
        "cwd": generated_dir,
        "returncode": None,
        "stdout": None,
        "stderr": None,
        "error": None,
        "started_at": utc_now_iso(),
        "finished_at": None,
        "duration_ms": None,
    }


def execute_script_attempt(
    run_id: str,
    generated_dir: str,
    file_name: str,
    script_content: str,
    attempt_number: int,
    generator: str,
    repair_round: int,
) -> dict[str, Any]:
    attempt_record = build_attempt_record(
        generated_dir=generated_dir,
        file_name=file_name,
        attempt_number=attempt_number,
        generator=generator,
        repair_round=repair_round,
    )
    append_run_attempt(run_id, attempt_record)

    attempt_file_name = str(attempt_record["attempt_file_name"])
    script_rel_path = str(attempt_record["script_rel_path"])
    safe_write_file(script_rel_path, script_content)
    append_run_log(run_id, f"Generated file for attempt {attempt_number}: {script_rel_path}")

    command = str(attempt_record["command"])
    syntax_error = validate_python_script(attempt_file_name, script_content)
    if syntax_error:
        finished_at = utc_now_iso()
        append_run_log(run_id, f"Python validation failed on attempt {attempt_number}.")
        result = {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": syntax_error,
            "cwd": generated_dir,
            "error": "Python syntax validation failed",
            "command": command,
            "script_rel_path": script_rel_path,
            "attempt_file_name": attempt_file_name,
            "source_file_name": str(attempt_record["source_file_name"]),
            "generator": generator,
            "repair_round": repair_round,
            "started_at": attempt_record["started_at"],
            "finished_at": finished_at,
        }
        update_run_attempt(
            run_id,
            attempt_number,
            status="failed",
            cwd=generated_dir,
            returncode=None,
            stdout="",
            stderr=syntax_error,
            error="Python syntax validation failed",
            finished_at=finished_at,
        )
        return result

    append_run_log(run_id, f"Executing attempt {attempt_number}: {command}")
    result = safe_execute_command(command, cwd=generated_dir)
    finished_at = utc_now_iso()
    result["command"] = command
    result["script_rel_path"] = script_rel_path
    result["attempt_file_name"] = attempt_file_name
    result["source_file_name"] = str(attempt_record["source_file_name"])
    result["generator"] = generator
    result["repair_round"] = repair_round
    result["started_at"] = attempt_record["started_at"]
    result["finished_at"] = finished_at
    update_run_attempt(
        run_id,
        attempt_number,
        status="done" if bool(result.get("ok")) else "failed",
        cwd=str(result.get("cwd") or generated_dir),
        returncode=result.get("returncode"),
        stdout=str(result.get("stdout") or ""),
        stderr=str(result.get("stderr") or ""),
        error=str(result.get("error") or "") or None,
        finished_at=finished_at,
    )
    return result


def append_execution_logs(run_id: str, attempt_number: int, result: dict[str, Any]) -> None:
    stdout = str(result.get("stdout") or "").strip()
    stderr = str(result.get("stderr") or "").strip()
    error = str(result.get("error") or "").strip()

    if stdout:
        append_run_log(run_id, f"Attempt {attempt_number} stdout: {stdout}")
    if stderr:
        append_run_log(run_id, f"Attempt {attempt_number} stderr: {stderr}")
    if error:
        append_run_log(run_id, f"Attempt {attempt_number} error: {error}")


def can_attempt_repair(repair_count: int) -> bool:
    return llm_is_configured() and repair_count < settings.run_repair_max_attempts


def build_success_output(
    initial_generator: str,
    final_generator: str,
    attempt_count: int,
    repair_count: int,
    result: dict[str, Any],
    artifacts: list[str],
) -> str:
    stdout = str(result.get("stdout") or "").strip() or "(empty)"
    stderr = str(result.get("stderr") or "").strip()
    returncode = result.get("returncode")
    repair_summary = "未触发自动修复。"
    if repair_count > 0:
        repair_summary = "首次执行失败，自动修复后重试成功。"

    output = (
        "任务执行成功。\n\n"
        f"初始生成方式：{initial_generator}\n"
        f"最终生成方式：{final_generator}\n"
        f"执行尝试次数：{attempt_count}\n"
        f"自动修复次数：{repair_count}\n"
        f"{repair_summary}\n"
        f"最终执行命令：{result.get('command')}\n"
        f"最终返回码：{returncode}\n"
        f"产物：\n{format_artifacts(artifacts)}\n\n"
        f"stdout:\n{stdout}"
    )
    if stderr:
        output += f"\n\nstderr:\n{stderr}"
    return output


def build_failure_output(
    initial_generator: str,
    final_generator: str,
    attempt_count: int,
    repair_count: int,
    result: dict[str, Any],
    artifacts: list[str],
    repair_note: str | None,
) -> str:
    stdout = str(result.get("stdout") or "").strip() or "(empty)"
    stderr = str(result.get("stderr") or "").strip() or "(empty)"
    error = str(result.get("error") or "").strip()
    returncode = result.get("returncode")

    output = (
        "任务执行失败。\n\n"
        f"初始生成方式：{initial_generator}\n"
        f"最终生成方式：{final_generator}\n"
        f"执行尝试次数：{attempt_count}\n"
        f"自动修复次数：{repair_count}\n"
        f"最终执行命令：{result.get('command') or '(not executed)'}\n"
        f"最终返回码：{returncode}\n"
        f"产物：\n{format_artifacts(artifacts)}\n\n"
        f"stdout:\n{stdout}\n\n"
        f"stderr:\n{stderr}"
    )
    if error:
        output += f"\n\nerror:\n{error}"
    if repair_note:
        output += f"\n\nrepair:\n{repair_note}"
    return output


def create_run(prompt: str, context: str | None) -> RunResponse:
    record = create_run_record(
        prompt=prompt,
        context=context,
        status="queued",
        output="任务已创建，等待后台执行。",
    )
    run_id = str(record["run_id"])
    log_path = f"runs/{run_id}/log.txt"
    record = update_run_record(run_id, log_path=log_path)
    append_run_log(run_id, "Run queued.")
    return to_run_response(record)


def execute_run(run_id: str) -> RunResponse | None:
    record = load_run_record(run_id)
    if record is None:
        return None

    prompt = str(record.get("prompt") or "")
    context = str(record.get("context")) if record.get("context") is not None else None
    generated_dir = f"runs/{run_id}/generated"
    current_log_path = f"runs/{run_id}/log.txt"
    run_started_at = utc_now_iso()

    append_run_log(run_id, "Background execution started.")
    update_run_record(
        run_id,
        status="running",
        output="任务开始后台执行。",
        started_at=run_started_at,
        finished_at=None,
        error=None,
        generator=None,
        attempt_count=0,
        repair_attempted=False,
        repair_count=0,
        command=None,
        returncode=None,
        stdout=None,
        stderr=None,
        log_path=current_log_path,
        artifacts=[],
        attempts=[],
    )
    append_run_log(run_id, "Status updated to running.")

    llm_result = generate_script_with_llm(prompt, context)
    if llm_result is not None:
        current_file_name, current_script_content, raw_llm_output = llm_result
        initial_generator = "llm"
        append_run_log(run_id, "Using LLM-generated Python script.")
        append_run_log(run_id, f"LLM raw response preview: {preview_text(raw_llm_output)}")
    else:
        current_file_name, current_script_content = choose_demo_script(prompt)
        initial_generator = "template"
        append_run_log(run_id, "Falling back to local template script.")

    current_generator = initial_generator
    attempt_count = 0
    repair_count = 0
    repair_attempted = False
    repair_note: str | None = None
    artifacts: list[str] = []
    last_result: dict[str, Any] | None = None

    try:
        while True:
            attempt_count += 1
            update_run_record(
                run_id,
                generator=current_generator,
                attempt_count=attempt_count,
                repair_attempted=repair_attempted,
                repair_count=repair_count,
            )
            append_run_log(
                run_id,
                f"Starting attempt {attempt_count} with generator={current_generator}.",
            )
            result = execute_script_attempt(
                run_id=run_id,
                generated_dir=generated_dir,
                file_name=current_file_name,
                script_content=current_script_content,
                attempt_number=attempt_count,
                generator=current_generator,
                repair_round=repair_count,
            )
            artifacts.append(str(result["script_rel_path"]))
            update_run_record(run_id, artifacts=artifacts)
            append_execution_logs(run_id, attempt_count, result)
            last_result = result

            if bool(result.get("ok")):
                append_run_log(run_id, "Run finished successfully.")
                final_record = update_run_record(
                    run_id,
                    status="done",
                    output=build_success_output(
                        initial_generator=initial_generator,
                        final_generator=current_generator,
                        attempt_count=attempt_count,
                        repair_count=repair_count,
                        result=result,
                        artifacts=artifacts,
                    ),
                    generator=current_generator,
                    attempt_count=attempt_count,
                    repair_attempted=repair_attempted,
                    repair_count=repair_count,
                    finished_at=utc_now_iso(),
                    error=None,
                    command=str(result.get("command")) if result.get("command") is not None else None,
                    returncode=result.get("returncode"),
                    stdout=str(result.get("stdout") or "").strip() or None,
                    stderr=str(result.get("stderr") or "").strip() or None,
                    log_path=current_log_path,
                    artifacts=artifacts,
                )
                return to_run_response(final_record)

            if not can_attempt_repair(repair_count):
                if not llm_is_configured():
                    repair_note = "未配置真实大模型，无法自动修复失败脚本。"
                    append_run_log(run_id, repair_note)
                elif repair_count >= settings.run_repair_max_attempts:
                    repair_note = "已达到自动修复最大次数限制。"
                    append_run_log(run_id, repair_note)
                break

            repair_attempted = True
            repair_count += 1
            update_run_record(
                run_id,
                repair_attempted=repair_attempted,
                repair_count=repair_count,
            )
            append_run_log(
                run_id,
                (
                    f"Attempt {attempt_count} failed. Requesting LLM repair "
                    f"{repair_count}/{settings.run_repair_max_attempts}."
                ),
            )
            repaired_result = generate_repaired_script_with_llm(
                prompt=prompt,
                context=context,
                file_name=current_file_name,
                script_content=current_script_content,
                failure_result=result,
            )
            if repaired_result is None:
                repair_note = "自动修复已触发，但没有生成可解析的 Python 代码。"
                append_run_log(run_id, repair_note)
                break

            current_file_name, current_script_content, raw_repair_output = repaired_result
            current_generator = "llm_repair"
            append_run_log(run_id, "Using LLM-repaired Python script for the next attempt.")
            append_run_log(
                run_id,
                f"LLM repair response preview: {preview_text(raw_repair_output)}",
            )

        if last_result is None:
            raise RuntimeError("任务未产生任何执行结果")

        append_run_log(run_id, "Run failed.")
        final_record = update_run_record(
            run_id,
            status="failed",
            output=build_failure_output(
                initial_generator=initial_generator,
                final_generator=current_generator,
                attempt_count=attempt_count,
                repair_count=repair_count,
                result=last_result,
                artifacts=artifacts,
                repair_note=repair_note,
            ),
            generator=current_generator,
            attempt_count=attempt_count,
            repair_attempted=repair_attempted,
            repair_count=repair_count,
            finished_at=utc_now_iso(),
            error=(
                repair_note
                or str(last_result.get("error") or "").strip()
                or str(last_result.get("stderr") or "").strip()
                or "Command execution failed"
            ),
            command=str(last_result.get("command")) if last_result.get("command") is not None else None,
            returncode=last_result.get("returncode"),
            stdout=str(last_result.get("stdout") or "").strip() or None,
            stderr=str(last_result.get("stderr") or "").strip() or None,
            log_path=current_log_path,
            artifacts=artifacts,
        )
        return to_run_response(final_record)
    except Exception as exc:
        append_run_log(run_id, f"Unhandled exception: {exc}")
        return to_run_response(
            update_run_record(
                run_id,
                status="failed",
                generator=current_generator,
                attempt_count=attempt_count,
                repair_attempted=repair_attempted,
                repair_count=repair_count,
                finished_at=utc_now_iso(),
                output=f"任务执行过程中发生未处理异常：{exc}",
                error=str(exc),
                log_path=current_log_path,
                artifacts=artifacts,
            )
        )


def get_run(run_id: str) -> RunResponse | None:
    record = load_run_record(run_id)
    if record is None:
        return None
    return to_run_response(record)


def get_run_attempts(run_id: str) -> RunAttemptListResponse | None:
    record = load_run_record(run_id)
    if record is None:
        return None
    attempts = [to_run_attempt_response(item) for item in get_attempt_records(record)]
    return RunAttemptListResponse(
        run_id=run_id,
        attempt_count=int(record.get("attempt_count") or len(attempts)),
        attempts=attempts,
    )


def get_run_attempt(run_id: str, attempt_number: int) -> RunAttemptResponse | None:
    record = load_run_record(run_id)
    if record is None:
        return None

    attempt = find_attempt_record(record, attempt_number)
    if attempt is None:
        return None
    return to_run_attempt_response(attempt)


def get_run_attempt_script(run_id: str, attempt_number: int) -> RunAttemptScriptResponse | None:
    record = load_run_record(run_id)
    if record is None:
        return None

    attempt = find_attempt_record(record, attempt_number)
    if attempt is None:
        return None

    script_rel_path = str(attempt.get("script_rel_path") or "").strip()
    if not script_rel_path:
        return None

    try:
        content = safe_read_file(script_rel_path)
    except (FileNotFoundError, PermissionError):
        return None

    return RunAttemptScriptResponse(
        run_id=run_id,
        attempt_number=attempt_number,
        attempt_file_name=(
            str(attempt["attempt_file_name"]) if attempt.get("attempt_file_name") is not None else None
        ),
        script_rel_path=script_rel_path,
        content=content,
    )


def get_run_attempt_output_chunk(
    run_id: str,
    attempt_number: int,
    stream: ATTEMPT_OUTPUT_STREAM,
    offset: int = 0,
    limit: int = ATTEMPT_OUTPUT_CHUNK_LIMIT,
) -> RunAttemptOutputChunkResponse | None:
    record = load_run_record(run_id)
    if record is None:
        return None

    attempt = find_attempt_record(record, attempt_number)
    if attempt is None:
        return None

    safe_offset = max(0, offset)
    safe_limit = max(1, min(limit, ATTEMPT_OUTPUT_CHUNK_MAX_LIMIT))
    raw_content = str(attempt.get(stream) or "")
    total_length = len(raw_content)
    if safe_offset > total_length:
        safe_offset = total_length
    end = min(total_length, safe_offset + safe_limit)
    content = raw_content[safe_offset:end]

    return RunAttemptOutputChunkResponse(
        run_id=run_id,
        attempt_number=attempt_number,
        stream=stream,
        offset=safe_offset,
        limit=safe_limit,
        total_length=total_length,
        has_more=end < total_length,
        content=content,
    )


def list_runs() -> list[RunResponse]:
    return [to_run_response(record) for record in list_run_records()]


def get_run_log(run_id: str) -> RunLogResponse | None:
    record = load_run_record(run_id)
    if record is None:
        return None
    return RunLogResponse(
        run_id=run_id,
        log_path=str(record.get("log_path")) if record.get("log_path") is not None else None,
        content=read_run_log(run_id),
    )
