import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.text_utils import clip_text
from .safe_execute_command import safe_execute_command
from .safe_fs import get_workspace_dir, resolve_workspace_path, safe_list_entries, safe_read_file
from .workspace_tool_models import (
    WorkspaceToolDescriptor,
    WorkspaceToolExecutionResult,
    WorkspaceToolPlan,
)


DEFAULT_TOOL_TEXT_LIMIT = 4000
DEFAULT_TOOL_ENTRY_LIMIT = 200
DEFAULT_FAILURE_SUMMARY_LIMIT = 1200
DEFAULT_TOOL_TEST_TIMEOUT_SECONDS = 20
DEFAULT_WORKSPACE_OVERVIEW_ENTRY_LIMIT = 12
DEFAULT_WORKSPACE_OVERVIEW_FILE_PREVIEW_LIMIT = 600
DEFAULT_WORKSPACE_OVERVIEW_FILES = (
    "README.md",
    "backend/README.md",
    "backend/requirements.txt",
)
DEFAULT_WORKSPACE_TEST_PATH_CANDIDATES = (
    "backend/tests",
    "tests",
)
WORKSPACE_TOOL_NAME_OVERVIEW = "build_workspace_overview"
WORKSPACE_TOOL_NAME_LIST = "list_workspace_entries"
WORKSPACE_TOOL_NAME_READ = "read_workspace_text"
WORKSPACE_TOOL_NAME_TEST = "run_workspace_tests"
WORKSPACE_TOOL_CATEGORY_CONTEXT = "context"
WORKSPACE_TOOL_CATEGORY_EXECUTION = "execution"
WORKSPACE_TOOL_OUTPUT_KIND_OVERVIEW = "overview_text"
WORKSPACE_TOOL_OUTPUT_KIND_LISTING = "entry_listing"
WORKSPACE_TOOL_OUTPUT_KIND_FILE_PREVIEW = "file_preview"
WORKSPACE_TOOL_OUTPUT_KIND_COMMAND_RESULT = "command_result"
WORKSPACE_TOOL_ERROR_UNREGISTERED = "WORKSPACE_TOOL_UNREGISTERED"
WORKSPACE_TOOL_ERROR_EXECUTION_FAILED = "WORKSPACE_TOOL_EXECUTION_FAILED"
WORKSPACE_TOOL_PATH_PATTERN = re.compile(
    r"(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]*|[A-Za-z0-9_.-]+\.[A-Za-z0-9_-]+"
)
WORKSPACE_TOOL_TEST_KEYWORDS = (
    "pytest",
    "test",
    "tests",
    "单元测试",
    "测试",
    "运行测试",
    "run tests",
)
WORKSPACE_TOOL_LIST_KEYWORDS = (
    "目录",
    "结构",
    "文件列表",
    "list",
    "ls",
    "tree",
)
WORKSPACE_TOOL_INPUT_KEYS = (
    "rel_path",
    "recursive",
    "max_entries",
    "max_chars",
    "test_paths",
    "cwd",
    "timeout_seconds",
    "max_output_chars",
    "include_files",
    "file_preview_chars",
)


@dataclass(frozen=True, slots=True)
class WorkspaceToolDefinition:
    name: str
    title: str
    description: str
    category: str
    output_kind: str
    input_keys: tuple[str, ...]
    executor: Callable[[Mapping[str, object]], tuple[object, str]]


def _serialize_workspace_tool_definition(
    tool_definition: WorkspaceToolDefinition,
) -> dict[str, object]:
    descriptor = WorkspaceToolDescriptor.from_value(tool_definition)
    assert descriptor is not None
    return descriptor.as_dict()


def _normalize_rel_path(rel_path: str | None) -> str:
    normalized = str(rel_path or ".").strip()
    return normalized or "."


def _normalize_positive_limit(value: int | None, *, default: int) -> int:
    if value is None or value <= 0:
        return default
    return value


def _resolve_workspace_rel_path(rel_path: str | None) -> str:
    normalized = _normalize_rel_path(rel_path)
    target = resolve_workspace_path(normalized)
    return str(target.relative_to(get_workspace_dir())).replace("\\", "/")


def _clip_output(text: str | None, *, limit: int) -> tuple[str, int, bool]:
    clipped, total_length, truncated = clip_text(text, limit=limit)
    return clipped or "", total_length, truncated


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _contains_keyword(prompt: str, keywords: Sequence[str]) -> bool:
    normalized_prompt = prompt.lower()
    return any(keyword in normalized_prompt for keyword in keywords)


def _clean_prompt_path_candidate(candidate: str) -> str:
    cleaned = candidate.strip().strip("`'\".,:;()[]{}<>")
    return cleaned.replace("\\", "/")


def _iter_existing_workspace_paths(prompt: str) -> list[tuple[str, Path]]:
    seen: set[str] = set()
    paths: list[tuple[str, Path]] = []

    for matched in WORKSPACE_TOOL_PATH_PATTERN.findall(prompt):
        rel_path = _clean_prompt_path_candidate(matched)
        if not rel_path or rel_path in seen:
            continue
        seen.add(rel_path)

        try:
            target = resolve_workspace_path(rel_path)
        except PermissionError:
            continue

        if not target.exists():
            continue
        paths.append((rel_path, target))

    return paths


def _first_matching_path(
    paths: Sequence[tuple[str, Path]],
    *,
    want_file: bool,
) -> str | None:
    for rel_path, target in paths:
        if want_file and target.is_file():
            return rel_path
        if not want_file and target.is_dir():
            return rel_path
    return None


def _default_test_paths() -> list[str]:
    paths: list[str] = []
    for rel_path in DEFAULT_WORKSPACE_TEST_PATH_CANDIDATES:
        try:
            target = resolve_workspace_path(rel_path)
        except PermissionError:
            continue
        if target.exists():
            paths.append(rel_path)
    return paths


def _normalize_tool_input_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if str(key).strip()
    }


def _build_workspace_tool_plan(
    tool_name: str,
    *,
    reason: str,
    **tool_input: object,
) -> dict[str, object]:
    return WorkspaceToolPlan(
        tool_name=tool_name,
        tool_input={
            key: value
            for key, value in tool_input.items()
            if value is not None
        },
        reason=reason,
    ).as_dict()


def normalize_workspace_tool_plan(value: object) -> WorkspaceToolPlan | None:
    if value is None:
        return None
    if isinstance(value, WorkspaceToolPlan):
        return value
    if not isinstance(value, Mapping):
        return None

    tool_name = str(value.get("tool_name") or WORKSPACE_TOOL_NAME_OVERVIEW).strip()
    tool_input = _extract_workspace_tool_input(value)
    reason = _normalize_optional_text(value.get("reason"))
    return WorkspaceToolPlan(
        tool_name=tool_name or WORKSPACE_TOOL_NAME_OVERVIEW,
        tool_input=tool_input,
        reason=reason,
    )


def normalize_workspace_tool_result(value: object) -> WorkspaceToolExecutionResult:
    if isinstance(value, WorkspaceToolExecutionResult):
        return value
    if isinstance(value, Mapping):
        normalized = dict(value)
        descriptor = WorkspaceToolDescriptor.from_value(normalized.get("tool_descriptor"))
        normalized["tool_descriptor"] = descriptor
        normalized["tool_name"] = str(
            normalized.get("tool_name") or WORKSPACE_TOOL_NAME_OVERVIEW
        ).strip() or WORKSPACE_TOOL_NAME_OVERVIEW
        if not isinstance(normalized.get("tool_input"), Mapping):
            normalized["tool_input"] = {}
        return WorkspaceToolExecutionResult.model_validate(normalized)

    return WorkspaceToolExecutionResult(
        tool_name=WORKSPACE_TOOL_NAME_OVERVIEW,
        ok=False,
        tool_error_code=WORKSPACE_TOOL_ERROR_EXECUTION_FAILED,
        error=f"invalid workspace tool result: {type(value).__name__}",
        summary=f"Workspace tool result is invalid: {type(value).__name__}",
    )


def _extract_workspace_tool_input(plan: Mapping[str, object]) -> dict[str, object]:
    tool_input = _normalize_tool_input_mapping(plan.get("tool_input"))
    if tool_input:
        return tool_input

    return {
        key: plan[key]
        for key in WORKSPACE_TOOL_INPUT_KEYS
        if key in plan and plan[key] is not None
    }


def list_workspace_entries(
    rel_path: str = ".",
    *,
    recursive: bool = False,
    max_entries: int = DEFAULT_TOOL_ENTRY_LIMIT,
) -> dict[str, object]:
    normalized_path = _resolve_workspace_rel_path(rel_path)
    entries = safe_list_entries(normalized_path, recursive=recursive)
    limit = _normalize_positive_limit(max_entries, default=DEFAULT_TOOL_ENTRY_LIMIT)
    return {
        "path": normalized_path,
        "recursive": recursive,
        "total": len(entries),
        "truncated": len(entries) > limit,
        "items": entries[:limit],
    }


def read_workspace_text(
    rel_path: str,
    *,
    max_chars: int = DEFAULT_TOOL_TEXT_LIMIT,
) -> dict[str, object]:
    normalized_path = _resolve_workspace_rel_path(rel_path)
    content = safe_read_file(normalized_path)
    clipped_content, total_chars, truncated = _clip_output(
        content,
        limit=_normalize_positive_limit(max_chars, default=DEFAULT_TOOL_TEXT_LIMIT),
    )
    return {
        "path": normalized_path,
        "content": clipped_content,
        "total_chars": total_chars,
        "truncated": truncated,
    }


def summarize_command_failure(
    result: Mapping[str, object],
    *,
    max_chars: int = DEFAULT_FAILURE_SUMMARY_LIMIT,
) -> str:
    limit = _normalize_positive_limit(max_chars, default=DEFAULT_FAILURE_SUMMARY_LIMIT)
    sections: list[str] = []

    error = str(result.get("error") or "").strip()
    stderr = str(result.get("stderr") or "").strip()
    stdout = str(result.get("stdout") or "").strip()

    if error:
        error_preview, _, _ = _clip_output(error, limit=limit)
        sections.append(f"error:\n{error_preview}")
    if stderr:
        stderr_preview, _, _ = _clip_output(stderr, limit=limit)
        sections.append(f"stderr:\n{stderr_preview}")
    elif stdout:
        stdout_preview, _, _ = _clip_output(stdout, limit=limit)
        sections.append(f"stdout:\n{stdout_preview}")

    if not sections:
        return "命令执行失败，但没有返回可用输出。"

    summary, _, truncated = _clip_output("\n\n".join(sections), limit=limit)
    if truncated:
        return summary
    return summary


def run_workspace_tests(
    test_paths: Sequence[str] | None = None,
    *,
    cwd: str | None = None,
    timeout_seconds: int | None = DEFAULT_TOOL_TEST_TIMEOUT_SECONDS,
    max_output_chars: int = DEFAULT_TOOL_TEXT_LIMIT,
) -> dict[str, object]:
    resolved_test_paths = [
        _resolve_workspace_rel_path(path)
        for path in (test_paths or [])
        if str(path).strip()
    ]
    resolved_cwd = None if cwd is None else _resolve_workspace_rel_path(cwd)
    output_limit = _normalize_positive_limit(
        max_output_chars,
        default=DEFAULT_TOOL_TEXT_LIMIT,
    )

    command = [sys.executable, "-m", "pytest", *resolved_test_paths]
    result = safe_execute_command(
        command,
        cwd=resolved_cwd,
        timeout_seconds=timeout_seconds,
    )
    stdout_preview, stdout_length, stdout_truncated = _clip_output(
        str(result.get("stdout") or ""),
        limit=output_limit,
    )
    stderr_preview, stderr_length, stderr_truncated = _clip_output(
        str(result.get("stderr") or ""),
        limit=output_limit,
    )

    return {
        **result,
        "command": command,
        "target_paths": resolved_test_paths,
        "cwd": str(result.get("cwd") or ""),
        "stdout_preview": stdout_preview,
        "stdout_length": stdout_length,
        "stdout_truncated": stdout_truncated,
        "stderr_preview": stderr_preview,
        "stderr_length": stderr_length,
        "stderr_truncated": stderr_truncated,
        "summary": (
            "测试命令执行成功。"
            if bool(result.get("ok"))
            else summarize_command_failure(result)
        ),
    }


def _format_workspace_entry(entry: Mapping[str, object]) -> str:
    kind = str(entry.get("kind") or "file").strip() or "file"
    path = str(entry.get("path") or "").strip()
    return f"- [{kind}] {path}"


def _format_workspace_listing_summary(listing: Mapping[str, object]) -> str:
    lines = [
        f"Workspace listing for `{listing['path']}`:",
    ]
    items = listing.get("items")
    if isinstance(items, list) and items:
        lines.extend(
            _format_workspace_entry(entry)
            for entry in items
            if isinstance(entry, Mapping)
        )
    else:
        lines.append("- <empty>")

    if bool(listing.get("truncated")):
        lines.append(
            f"... (showing first {len(items) if isinstance(items, list) else 0} of {listing['total']} entries)"
        )
    return "\n".join(lines)


def _format_workspace_test_summary(result: Mapping[str, object]) -> str:
    lines = ["Workspace pytest result:"]

    target_paths = result.get("target_paths")
    if isinstance(target_paths, list) and target_paths:
        lines.append(f"targets: {', '.join(str(path) for path in target_paths)}")

    summary = _normalize_optional_text(result.get("summary"))
    if summary is not None:
        lines.append(summary)

    stdout_preview = _normalize_optional_text(result.get("stdout_preview"))
    if stdout_preview is not None:
        lines.append(f"stdout preview:\n{stdout_preview}")

    stderr_preview = _normalize_optional_text(result.get("stderr_preview"))
    if stderr_preview is not None:
        lines.append(f"stderr preview:\n{stderr_preview}")

    return "\n\n".join(lines)


def _execute_overview_tool(tool_input: Mapping[str, object]) -> tuple[str, str]:
    rel_path = _normalize_rel_path(_normalize_optional_text(tool_input.get("rel_path")))
    include_files = tool_input.get("include_files")
    normalized_include_files = (
        [str(path) for path in include_files if str(path).strip()]
        if isinstance(include_files, Sequence) and not isinstance(include_files, (str, bytes))
        else DEFAULT_WORKSPACE_OVERVIEW_FILES
    )
    file_preview_chars = int(
        tool_input.get("file_preview_chars") or DEFAULT_WORKSPACE_OVERVIEW_FILE_PREVIEW_LIMIT
    )
    data = build_workspace_overview(
        rel_path=rel_path,
        include_files=normalized_include_files,
        file_preview_chars=file_preview_chars,
    )
    summary = f"Workspace overview for the coding task:\n{data}" if data else ""
    return data, summary


def _execute_read_tool(tool_input: Mapping[str, object]) -> tuple[dict[str, object], str]:
    rel_path = _normalize_rel_path(_normalize_optional_text(tool_input.get("rel_path")))
    max_chars = int(tool_input.get("max_chars") or DEFAULT_TOOL_TEXT_LIMIT)
    data = read_workspace_text(rel_path, max_chars=max_chars)
    content = _normalize_optional_text(data.get("content")) or "<empty>"
    return data, f"Workspace file preview ({data['path']}):\n{content}"


def _execute_list_tool(tool_input: Mapping[str, object]) -> tuple[dict[str, object], str]:
    rel_path = _normalize_rel_path(_normalize_optional_text(tool_input.get("rel_path")))
    max_entries = int(tool_input.get("max_entries") or DEFAULT_TOOL_ENTRY_LIMIT)
    data = list_workspace_entries(
        rel_path,
        recursive=bool(tool_input.get("recursive", False)),
        max_entries=max_entries,
    )
    return data, _format_workspace_listing_summary(data)


def _execute_test_tool(tool_input: Mapping[str, object]) -> tuple[dict[str, object], str]:
    test_paths = tool_input.get("test_paths")
    normalized_test_paths = (
        [str(path) for path in test_paths if str(path).strip()]
        if isinstance(test_paths, Sequence) and not isinstance(test_paths, (str, bytes))
        else None
    )
    timeout_seconds = int(tool_input.get("timeout_seconds") or DEFAULT_TOOL_TEST_TIMEOUT_SECONDS)
    max_output_chars = int(tool_input.get("max_output_chars") or DEFAULT_TOOL_TEXT_LIMIT)
    cwd = _normalize_optional_text(tool_input.get("cwd"))
    data = run_workspace_tests(
        normalized_test_paths or None,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        max_output_chars=max_output_chars,
    )
    return data, _format_workspace_test_summary(data)


WORKSPACE_TOOL_REGISTRY: dict[str, WorkspaceToolDefinition] = {
    WORKSPACE_TOOL_NAME_OVERVIEW: WorkspaceToolDefinition(
        name=WORKSPACE_TOOL_NAME_OVERVIEW,
        title="工作区概览",
        description="读取项目顶层结构和关键文件摘要，用于创建代码任务前的轻量上下文补充。",
        category=WORKSPACE_TOOL_CATEGORY_CONTEXT,
        output_kind=WORKSPACE_TOOL_OUTPUT_KIND_OVERVIEW,
        input_keys=("rel_path", "include_files", "file_preview_chars"),
        executor=_execute_overview_tool,
    ),
    WORKSPACE_TOOL_NAME_READ: WorkspaceToolDefinition(
        name=WORKSPACE_TOOL_NAME_READ,
        title="读取工作区文本",
        description="读取单个工作区文本文件并返回裁剪后的内容预览。",
        category=WORKSPACE_TOOL_CATEGORY_CONTEXT,
        output_kind=WORKSPACE_TOOL_OUTPUT_KIND_FILE_PREVIEW,
        input_keys=("rel_path", "max_chars"),
        executor=_execute_read_tool,
    ),
    WORKSPACE_TOOL_NAME_LIST: WorkspaceToolDefinition(
        name=WORKSPACE_TOOL_NAME_LIST,
        title="列出工作区目录",
        description="列出工作区目录结构，用于理解项目布局。",
        category=WORKSPACE_TOOL_CATEGORY_CONTEXT,
        output_kind=WORKSPACE_TOOL_OUTPUT_KIND_LISTING,
        input_keys=("rel_path", "recursive", "max_entries"),
        executor=_execute_list_tool,
    ),
    WORKSPACE_TOOL_NAME_TEST: WorkspaceToolDefinition(
        name=WORKSPACE_TOOL_NAME_TEST,
        title="运行工作区测试",
        description="在受控 workspace 边界内运行 pytest，并返回摘要化测试结果。",
        category=WORKSPACE_TOOL_CATEGORY_EXECUTION,
        output_kind=WORKSPACE_TOOL_OUTPUT_KIND_COMMAND_RESULT,
        input_keys=("test_paths", "cwd", "timeout_seconds", "max_output_chars"),
        executor=_execute_test_tool,
    ),
}


def list_workspace_tool_names() -> tuple[str, ...]:
    return tuple(WORKSPACE_TOOL_REGISTRY.keys())


def get_workspace_tool_definition(tool_name: str) -> WorkspaceToolDefinition | None:
    normalized_tool_name = str(tool_name or "").strip()
    return WORKSPACE_TOOL_REGISTRY.get(normalized_tool_name)


def get_workspace_tool_descriptor(tool_name: str) -> dict[str, object] | None:
    tool_definition = get_workspace_tool_definition(tool_name)
    if tool_definition is None:
        return None
    return _serialize_workspace_tool_definition(tool_definition)


def list_workspace_tool_descriptors() -> list[dict[str, object]]:
    return [
        _serialize_workspace_tool_definition(tool_definition)
        for tool_definition in WORKSPACE_TOOL_REGISTRY.values()
    ]


def build_workspace_overview(
    *,
    rel_path: str = ".",
    max_entries: int = DEFAULT_WORKSPACE_OVERVIEW_ENTRY_LIMIT,
    include_files: Sequence[str] = DEFAULT_WORKSPACE_OVERVIEW_FILES,
    file_preview_chars: int = DEFAULT_WORKSPACE_OVERVIEW_FILE_PREVIEW_LIMIT,
) -> str:
    listing = list_workspace_entries(
        rel_path,
        recursive=False,
        max_entries=max_entries,
    )
    sections: list[str] = []

    items = listing["items"]
    if isinstance(items, list) and items:
        lines = ["Workspace top-level entries:"]
        lines.extend(
            _format_workspace_entry(entry)
            for entry in items
            if isinstance(entry, Mapping)
        )
        if bool(listing.get("truncated")):
            lines.append(f"... (showing first {len(items)} of {listing['total']} entries)")
        sections.append("\n".join(lines))

    for rel_file_path in include_files:
        try:
            preview = read_workspace_text(
                rel_file_path,
                max_chars=file_preview_chars,
            )
        except FileNotFoundError:
            continue

        content = str(preview.get("content") or "").strip()
        if not content:
            continue
        sections.append(f"{preview['path']} preview:\n{content}")

    return "\n\n".join(section for section in sections if section).strip()


def plan_workspace_tool(prompt: str) -> dict[str, object]:
    normalized_prompt = str(prompt or "").strip()
    matched_paths = _iter_existing_workspace_paths(normalized_prompt)

    if _contains_keyword(normalized_prompt, WORKSPACE_TOOL_TEST_KEYWORDS):
        target_paths = [rel_path for rel_path, _ in matched_paths]
        if not target_paths:
            target_paths = _default_test_paths()
        if target_paths:
            return _build_workspace_tool_plan(
                WORKSPACE_TOOL_NAME_TEST,
                reason="Prompt asks for test-related coding work.",
                test_paths=target_paths,
            )

    matched_file = _first_matching_path(matched_paths, want_file=True)
    if matched_file is not None:
        return _build_workspace_tool_plan(
            WORKSPACE_TOOL_NAME_READ,
            reason="Prompt references a workspace file path.",
            rel_path=matched_file,
        )

    if _contains_keyword(normalized_prompt, WORKSPACE_TOOL_LIST_KEYWORDS):
        matched_dir = _first_matching_path(matched_paths, want_file=False) or "."
        return _build_workspace_tool_plan(
            WORKSPACE_TOOL_NAME_LIST,
            reason="Prompt asks for workspace structure.",
            rel_path=matched_dir,
            recursive=False,
            max_entries=DEFAULT_WORKSPACE_OVERVIEW_ENTRY_LIMIT,
        )

    return _build_workspace_tool_plan(
        WORKSPACE_TOOL_NAME_OVERVIEW,
        reason="Provide a compact workspace overview before creating the run.",
        rel_path=".",
    )


def execute_workspace_tool_plan(plan: Mapping[str, object] | WorkspaceToolPlan) -> dict[str, object]:
    plan_model = normalize_workspace_tool_plan(plan)
    if plan_model is None:
        plan_model = WorkspaceToolPlan(
            tool_name=WORKSPACE_TOOL_NAME_OVERVIEW,
            tool_input={},
            reason="Workspace tool plan is missing or invalid; using default overview plan.",
        )

    tool_name = plan_model.tool_name.strip() or WORKSPACE_TOOL_NAME_OVERVIEW
    reason = _normalize_optional_text(plan_model.reason)
    tool_input = dict(plan_model.tool_input)
    tool_definition = get_workspace_tool_definition(tool_name)
    tool_descriptor = (
        _serialize_workspace_tool_definition(tool_definition)
        if tool_definition is not None
        else None
    )

    if tool_definition is None:
        return WorkspaceToolExecutionResult(
            tool_name=tool_name,
            tool_input=tool_input,
            ok=False,
            reason=reason,
            tool_category=None,
            tool_output_kind=None,
            tool_error_code=WORKSPACE_TOOL_ERROR_UNREGISTERED,
            tool_descriptor=None,
            summary=f"Workspace tool `{tool_name}` is not registered.",
            error=f"unregistered workspace tool: {tool_name}",
            data=None,
        ).as_dict()

    try:
        data, summary = tool_definition.executor(tool_input)

        return WorkspaceToolExecutionResult(
            tool_name=tool_name,
            tool_input=tool_input,
            ok=True,
            reason=reason,
            tool_category=tool_definition.category,
            tool_output_kind=tool_definition.output_kind,
            tool_error_code=None,
            tool_descriptor=WorkspaceToolDescriptor.from_value(tool_descriptor),
            summary=summary,
            data=data,
        ).as_dict()
    except Exception as exc:
        return WorkspaceToolExecutionResult(
            tool_name=tool_name,
            tool_input=tool_input,
            ok=False,
            reason=reason,
            tool_category=tool_definition.category,
            tool_output_kind=tool_definition.output_kind,
            tool_error_code=WORKSPACE_TOOL_ERROR_EXECUTION_FAILED,
            tool_descriptor=WorkspaceToolDescriptor.from_value(tool_descriptor),
            summary=f"Workspace tool `{tool_name}` failed: {exc}",
            error=str(exc),
            data=None,
        ).as_dict()


def build_workspace_tool_context(result: Mapping[str, object]) -> str | None:
    return _normalize_optional_text(result.get("summary"))
