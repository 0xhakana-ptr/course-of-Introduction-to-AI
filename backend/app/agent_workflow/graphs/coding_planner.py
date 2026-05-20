from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ...llm.client import call_llm_sync, llm_is_configured, preview_text


ALLOWED_CODING_PLANNER_ACTIONS = frozenset(
    {
        "workspace.write",
        "workspace.read",
        "workspace.list",
        "run.create",
    }
)
FORBIDDEN_ACTION_INPUT_KEY_PARTS = (
    "api_key",
    "args",
    "command",
    "cwd",
    "env",
    "password",
    "raw_error",
    "secret",
    "shell",
    "stderr",
    "stdout",
    "subprocess",
    "token",
)
JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
MAX_PLANNER_TASKS = 6
MAX_PLANNER_TASK_CHARS = 240
MAX_PLANNER_REASON_CHARS = 400
MAX_PLANNER_TEXT_VALUE_CHARS = 4000
LLM_PLANNER_MAX_TOKENS = 700


@dataclass(frozen=True, slots=True)
class CodingTaskPlan:
    tasks_list: list[str] = field(default_factory=list)
    executor_action_name: str | None = None
    executor_action_input: dict[str, object] = field(default_factory=dict)
    reason: str = ""
    target_files: list[str] = field(default_factory=list)
    planner_source: str = "llm"
    token_budget: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "tasks_list": list(self.tasks_list),
            "executor_action_name": self.executor_action_name,
            "executor_action_input": dict(self.executor_action_input),
            "reason": self.reason,
            "target_files": list(self.target_files),
            "planner_source": self.planner_source,
            "token_budget": dict(self.token_budget),
        }


@dataclass(frozen=True, slots=True)
class CodingPlannerResult:
    ok: bool
    plan: CodingTaskPlan | None = None
    error: str | None = None
    error_kind: str | None = None
    raw_output_preview: str | None = None
    planner_source: str = "llm"
    token_budget: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "plan": self.plan.as_dict() if self.plan else None,
            "error": self.error,
            "error_kind": self.error_kind,
            "raw_output_preview": self.raw_output_preview,
            "planner_source": self.planner_source,
            "token_budget": dict(self.token_budget),
        }


def _normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _clip_text(value: object, *, limit: int) -> str:
    text = _normalize_text(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _coerce_text_list(value: object, *, limit: int = MAX_PLANNER_TASK_CHARS) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _clip_text(item, limit=limit)
        if text:
            result.append(text)
        if len(result) >= MAX_PLANNER_TASKS:
            break
    return result


def _extract_json_text(raw_output: str) -> str:
    text = raw_output.strip()
    if not text:
        return ""

    fence_match = JSON_FENCE_PATTERN.search(text)
    if fence_match:
        return fence_match.group(1).strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1].strip()
    return text


def _has_forbidden_action_input_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key or "").strip().lower()
            if any(part in normalized for part in FORBIDDEN_ACTION_INPUT_KEY_PARTS):
                return True
            if _has_forbidden_action_input_key(item):
                return True
    if isinstance(value, list):
        return any(_has_forbidden_action_input_key(item) for item in value)
    return False


def _coerce_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return default


def _sanitize_text_mapping(value: Mapping[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in value.items():
        normalized_key = _normalize_text(key)
        if not normalized_key:
            continue
        if isinstance(item, str):
            result[normalized_key] = _clip_text(item, limit=MAX_PLANNER_TEXT_VALUE_CHARS)
        elif isinstance(item, int | float | bool) or item is None:
            result[normalized_key] = item
    return result


def _validate_planner_action_input(
    action_name: str | None,
    raw_action_input: object,
    *,
    prompt: str,
    context: str | None,
) -> tuple[dict[str, object], str | None]:
    if not action_name:
        return {}, None
    if not isinstance(raw_action_input, Mapping):
        return {}, "executor_action_input must be an object"
    if _has_forbidden_action_input_key(raw_action_input):
        return {}, "executor_action_input contains forbidden local execution keys"

    action_input = _sanitize_text_mapping(raw_action_input)
    if action_name == "workspace.write":
        rel_path = _normalize_text(action_input.get("rel_path"))
        content = _normalize_text(action_input.get("content"))
        if not rel_path or not content:
            return {}, "workspace.write requires rel_path and content"
        return {
            "rel_path": rel_path,
            "content": content,
            "overwrite": _coerce_bool(action_input.get("overwrite")),
        }, None

    if action_name == "workspace.read":
        rel_path = _normalize_text(action_input.get("rel_path"))
        if not rel_path:
            return {}, "workspace.read requires rel_path"
        return {"rel_path": rel_path}, None

    if action_name == "workspace.list":
        rel_path = _normalize_text(action_input.get("rel_path"), default=".")
        return {
            "rel_path": rel_path,
            "recursive": _coerce_bool(action_input.get("recursive")),
        }, None

    if action_name == "run.create":
        run_prompt = _normalize_text(action_input.get("prompt"), default=prompt)
        run_context = _normalize_text(action_input.get("context"), default=context or "")
        return {
            "prompt": run_prompt,
            "context": run_context or None,
        }, None

    return {}, f"unsupported executor_action_name: {action_name}"


def parse_llm_coding_plan_json(
    raw_output: str,
    *,
    prompt: str,
    context: str | None = None,
    token_budget: Mapping[str, int] | None = None,
) -> CodingPlannerResult:
    normalized_output = _normalize_text(raw_output)
    raw_output_preview = preview_text(normalized_output, limit=500)
    if not normalized_output:
        return CodingPlannerResult(
            ok=False,
            error="LLM planner returned empty output.",
            error_kind="empty_output",
            raw_output_preview=raw_output_preview,
            token_budget=dict(token_budget or {}),
        )

    try:
        parsed = json.loads(_extract_json_text(normalized_output))
    except json.JSONDecodeError as exc:
        return CodingPlannerResult(
            ok=False,
            error=f"LLM planner output is not valid JSON: {exc.msg}",
            error_kind="invalid_json",
            raw_output_preview=raw_output_preview,
            token_budget=dict(token_budget or {}),
        )

    if not isinstance(parsed, Mapping):
        return CodingPlannerResult(
            ok=False,
            error="LLM planner JSON must be an object.",
            error_kind="invalid_schema",
            raw_output_preview=raw_output_preview,
            token_budget=dict(token_budget or {}),
        )

    action_name = _normalize_text(parsed.get("executor_action_name")) or None
    if action_name is not None and action_name not in ALLOWED_CODING_PLANNER_ACTIONS:
        return CodingPlannerResult(
            ok=False,
            error=f"LLM planner requested unsupported action: {action_name}",
            error_kind="unsupported_action",
            raw_output_preview=raw_output_preview,
            token_budget=dict(token_budget or {}),
        )

    action_input, input_error = _validate_planner_action_input(
        action_name,
        parsed.get("executor_action_input"),
        prompt=prompt,
        context=context,
    )
    if input_error:
        return CodingPlannerResult(
            ok=False,
            error=input_error,
            error_kind="invalid_action_input",
            raw_output_preview=raw_output_preview,
            token_budget=dict(token_budget or {}),
        )

    tasks_list = _coerce_text_list(parsed.get("tasks_list"))
    if not tasks_list:
        tasks_list = [_clip_text(prompt, limit=MAX_PLANNER_TASK_CHARS)]

    target_files = _coerce_text_list(parsed.get("target_files"), limit=260)
    plan = CodingTaskPlan(
        tasks_list=tasks_list,
        executor_action_name=action_name,
        executor_action_input=action_input,
        reason=_clip_text(parsed.get("reason"), limit=MAX_PLANNER_REASON_CHARS),
        target_files=target_files,
        planner_source="llm",
        token_budget=dict(token_budget or {}),
    )
    return CodingPlannerResult(
        ok=True,
        plan=plan,
        raw_output_preview=raw_output_preview,
        token_budget=dict(token_budget or {}),
    )


def build_llm_coding_planner_prompt(
    *,
    user_input: str,
    current_task: str,
) -> str:
    return (
        "Plan one safe coding workflow step for the desktop agent backend.\n"
        "Return ONLY strict JSON. Do not use markdown. Do not execute tools.\n"
        "Allowed executor_action_name values are: workspace.write, workspace.read, "
        "workspace.list, run.create, or null.\n"
        "Never propose shell commands, subprocess, env, cwd, tokens, secrets, raw logs, "
        "or direct local execution.\n"
        "Schema:\n"
        "{\n"
        '  "tasks_list": ["short task"],\n'
        '  "executor_action_name": "workspace.write|workspace.read|workspace.list|run.create|null",\n'
        '  "executor_action_input": {},\n'
        '  "target_files": ["relative/path.txt"],\n'
        '  "reason": "short reason"\n'
        "}\n\n"
        f"User input:\n{user_input}\n\n"
        f"Current task:\n{current_task}"
    )


def plan_coding_task_with_llm(
    *,
    user_input: str,
    current_task: str,
    context: str | None = None,
) -> CodingPlannerResult:
    token_budget = {
        "prompt_chars": len(user_input),
        "current_task_chars": len(current_task),
        "context_chars": len(context or ""),
        "max_tokens": LLM_PLANNER_MAX_TOKENS,
    }
    if not llm_is_configured():
        return CodingPlannerResult(
            ok=False,
            error="LLM planner is not configured.",
            error_kind="unconfigured",
            token_budget=token_budget,
        )

    planner_prompt = build_llm_coding_planner_prompt(
        user_input=user_input,
        current_task=current_task,
    )
    result = call_llm_sync(
        planner_prompt,
        context=context,
        system_prompt=(
            "You are a strict JSON planner. You only produce a safe plan. "
            "You never execute tools and never output markdown."
        ),
        temperature=0.0,
        max_tokens=LLM_PLANNER_MAX_TOKENS,
    )
    token_budget["planner_prompt_chars"] = len(planner_prompt)
    if not result.ok:
        return CodingPlannerResult(
            ok=False,
            error=result.error or result.output or "LLM planner call failed.",
            error_kind=result.error_kind or "llm_call_failed",
            raw_output_preview=preview_text(result.output, limit=500),
            token_budget=token_budget,
        )

    return parse_llm_coding_plan_json(
        result.output,
        prompt=user_input,
        context=context,
        token_budget=token_budget,
    )
