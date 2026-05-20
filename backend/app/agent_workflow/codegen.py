import json
import re
from typing import Any

from ..core.text_utils import build_preview
from ..llm.client import call_llm_sync, llm_is_configured
from .types.run_types import LLM_PREVIEW_LIMIT, ScriptGenerationResult


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
    return build_preview(text, limit=limit, collapse_whitespace=False)


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


def _parse_script_generation_response(
    raw_output: str,
    *,
    fallback_filename: str,
    missing_code_error: str,
) -> ScriptGenerationResult:
    code = extract_python_code(raw_output)
    if not code:
        return ScriptGenerationResult(
            ok=False,
            raw_output=raw_output,
            error=missing_code_error,
        )

    filename = sanitize_filename(extract_filename(raw_output), fallback=fallback_filename)
    return ScriptGenerationResult(
        ok=True,
        file_name=filename,
        script_content=code,
        raw_output=raw_output,
    )


def _request_script_from_llm(
    *,
    prompt: str,
    context: str | None,
    system_prompt: str,
    temperature: float,
    fallback_filename: str,
    missing_code_error: str,
) -> ScriptGenerationResult:
    if not llm_is_configured():
        return ScriptGenerationResult(ok=False, error="未配置真实大模型。")

    llm_result = call_llm_sync(
        prompt=prompt,
        context=context,
        system_prompt=system_prompt,
        temperature=temperature,
    )
    if not llm_result.ok:
        return ScriptGenerationResult(
            ok=False,
            raw_output=llm_result.output,
            error=llm_result.error or llm_result.output,
        )

    return _parse_script_generation_response(
        llm_result.output,
        fallback_filename=fallback_filename,
        missing_code_error=missing_code_error,
    )


def generate_script_with_llm(prompt: str, context: str | None) -> ScriptGenerationResult:
    return _request_script_from_llm(
        prompt=prompt,
        context=context,
        system_prompt=CODE_SYSTEM_PROMPT,
        temperature=0.2,
        fallback_filename="main.py",
        missing_code_error="大模型返回内容中没有可解析的 Python 代码。",
    )


def generate_repaired_script_with_llm(
    prompt: str,
    context: str | None,
    file_name: str,
    script_content: str,
    failure_result: dict[str, Any],
) -> ScriptGenerationResult:
    return _request_script_from_llm(
        prompt=build_repair_prompt(prompt, context, file_name, script_content, failure_result),
        context=None,
        system_prompt=CODE_REPAIR_SYSTEM_PROMPT,
        temperature=0.1,
        fallback_filename=file_name,
        missing_code_error="大模型修复结果中没有可解析的 Python 代码。",
    )
