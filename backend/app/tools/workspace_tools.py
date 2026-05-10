import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.config import settings
from ..core.text_utils import clip_text
from ..schemas import (
    WORKSPACE_TOOL_CATEGORY,
    WORKSPACE_TOOL_ERROR_CODE,
    WORKSPACE_TOOL_OUTPUT_KIND,
)
from .safe_execute_command import safe_execute_command
from .safe_fs import (
    get_workspace_dir,
    resolve_workspace_path,
    safe_list_entries,
    safe_read_file,
    safe_write_file,
)
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
DEFAULT_WRITE_TEXT_LIMIT = 8000
DEFAULT_WRITE_TEXT_REL_PATH = "generated/request.txt"
DEFAULT_DESKTOP_EXPORT_FILE_NAME = "request.txt"
WORKSPACE_TOOL_NAME_OVERVIEW = "build_workspace_overview"
WORKSPACE_TOOL_NAME_LIST = "list_workspace_entries"
WORKSPACE_TOOL_NAME_READ = "read_workspace_text"
WORKSPACE_TOOL_NAME_TEST = "run_workspace_tests"
WORKSPACE_TOOL_NAME_WRITE = "write_workspace_text"
WORKSPACE_TOOL_CATEGORY_CONTEXT: WORKSPACE_TOOL_CATEGORY = "context"
WORKSPACE_TOOL_CATEGORY_EXECUTION: WORKSPACE_TOOL_CATEGORY = "execution"
WORKSPACE_TOOL_OUTPUT_KIND_OVERVIEW: WORKSPACE_TOOL_OUTPUT_KIND = "overview_text"
WORKSPACE_TOOL_OUTPUT_KIND_LISTING: WORKSPACE_TOOL_OUTPUT_KIND = "entry_listing"
WORKSPACE_TOOL_OUTPUT_KIND_FILE_PREVIEW: WORKSPACE_TOOL_OUTPUT_KIND = "file_preview"
WORKSPACE_TOOL_OUTPUT_KIND_COMMAND_RESULT: WORKSPACE_TOOL_OUTPUT_KIND = "command_result"
WORKSPACE_TOOL_OUTPUT_KIND_FILE_WRITE: WORKSPACE_TOOL_OUTPUT_KIND = "file_write"
WORKSPACE_TOOL_ERROR_UNREGISTERED: WORKSPACE_TOOL_ERROR_CODE = "WORKSPACE_TOOL_UNREGISTERED"
WORKSPACE_TOOL_ERROR_EXECUTION_FAILED: WORKSPACE_TOOL_ERROR_CODE = (
    "WORKSPACE_TOOL_EXECUTION_FAILED"
)
WORKSPACE_TOOL_ERROR_TARGET_UNSUPPORTED: WORKSPACE_TOOL_ERROR_CODE = (
    "WORKSPACE_TOOL_TARGET_UNSUPPORTED"
)
WORKSPACE_TOOL_ERROR_TARGET_DISABLED: WORKSPACE_TOOL_ERROR_CODE = (
    "WORKSPACE_TOOL_TARGET_DISABLED"
)
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
WORKSPACE_TOOL_READ_KEYWORDS = (
    "读取",
    "读一下",
    "查看",
    "看一下",
    "显示",
    "打开",
    "预览",
    "read",
    "show",
    "view",
    "open",
    "cat",
    "preview",
)
WORKSPACE_TOOL_WRITE_KEYWORDS = (
    "创建",
    "新建",
    "写入",
    "保存",
    "create",
    "new",
    "write",
    "save",
)
WORKSPACE_TOOL_TEXT_FILE_KEYWORDS = (
    ".txt",
    "txt",
    "文本文件",
    "text file",
)
WORKSPACE_TOOL_DESKTOP_KEYWORDS = (
    "桌面",
    "desktop",
)
WORKSPACE_TOOL_CODEGEN_TASK_KEYWORDS = (
    "修复",
    "修改",
    "改",
    "优化",
    "实现",
    "编写",
    "开发",
    "生成代码",
    "写代码",
    "重构",
    "补充",
    "完善",
    "新增功能",
    "分析",
    "诊断",
    "问题",
    "报错",
    "失败",
    "bug",
    "fix",
    "modify",
    "update",
    "change",
    "optimize",
    "implement",
    "build",
    "develop",
    "generate code",
    "write code",
    "refactor",
    "add feature",
    "analyze",
    "diagnose",
    "problem",
    "error",
    "failed",
    "failure",
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
    "content",
    "overwrite",
    "target_location",
)


@dataclass(frozen=True, slots=True)
class WorkspaceToolDefinition:
    name: str
    title: str
    description: str
    category: WORKSPACE_TOOL_CATEGORY
    output_kind: WORKSPACE_TOOL_OUTPUT_KIND
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


def _normalize_optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _contains_keyword(prompt: str, keywords: Sequence[str]) -> bool:
    normalized_prompt = prompt.lower()
    return any(keyword.lower() in normalized_prompt for keyword in keywords)


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


def _iter_prompt_path_candidates(prompt: str) -> list[str]:
    seen: set[str] = set()
    paths: list[str] = []
    for matched in WORKSPACE_TOOL_PATH_PATTERN.findall(prompt):
        rel_path = _clean_prompt_path_candidate(matched)
        if not rel_path or rel_path in seen:
            continue
        seen.add(rel_path)
        paths.append(rel_path)
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


def _looks_like_text_file_write_request(prompt: str) -> bool:
    return _contains_keyword(prompt, WORKSPACE_TOOL_WRITE_KEYWORDS) and _contains_keyword(
        prompt,
        WORKSPACE_TOOL_TEXT_FILE_KEYWORDS,
    )


def _looks_like_codegen_task(prompt: str) -> bool:
    return _contains_keyword(prompt, WORKSPACE_TOOL_CODEGEN_TASK_KEYWORDS)


def _looks_like_pure_read_request(prompt: str) -> bool:
    return (
        _contains_keyword(prompt, WORKSPACE_TOOL_READ_KEYWORDS)
        and not _looks_like_codegen_task(prompt)
    )


def _looks_like_pure_list_request(prompt: str) -> bool:
    return (
        _contains_keyword(prompt, WORKSPACE_TOOL_LIST_KEYWORDS)
        and not _looks_like_codegen_task(prompt)
    )


def _looks_like_pure_test_request(prompt: str) -> bool:
    return (
        _contains_keyword(prompt, WORKSPACE_TOOL_TEST_KEYWORDS)
        and not _looks_like_codegen_task(prompt)
    )


def _target_location_from_prompt(prompt: str) -> str:
    if _contains_keyword(prompt, WORKSPACE_TOOL_DESKTOP_KEYWORDS):
        return "desktop"
    return "workspace"


def _first_text_file_candidate(prompt: str) -> str | None:
    for candidate in _iter_prompt_path_candidates(prompt):
        if candidate.lower().endswith(".txt"):
            return candidate
    return None


def _extract_requested_text_content(prompt: str) -> str:
    patterns = (
        r"(?:内容是|内容为|内容：|内容:)\s*(.+)$",
        r"(?:with content|content is)\s*[:：]?\s*(.+)$",
    )
    for pattern in patterns:
        matched = re.search(pattern, prompt, flags=re.IGNORECASE | re.DOTALL)
        if matched is not None:
            return matched.group(1).strip()
    return ""


def _sanitize_desktop_export_file_name(rel_path: str | None) -> str:
    raw_name = Path(str(rel_path or "").replace("\\", "/")).name.strip()
    if not raw_name:
        raw_name = DEFAULT_DESKTOP_EXPORT_FILE_NAME
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "_", raw_name).strip(" .")
    if not cleaned:
        cleaned = DEFAULT_DESKTOP_EXPORT_FILE_NAME
    if not cleaned.lower().endswith(".txt"):
        cleaned = f"{cleaned}.txt"
    return cleaned


def _desktop_export_disabled_summary() -> str | None:
    if not settings.desktop_export_enabled:
        return (
            "我不能直接写桌面路径，因为桌面导出功能没有开启。"
            "可以先把文件创建到项目 workspace 中，或在 `.env` 中显式开启 "
            "`DESKTOP_EXPORT_ENABLED=true` 并配置 `DESKTOP_EXPORT_DIR`。"
        )
    if settings.desktop_export_dir is None:
        return (
            "桌面导出功能已经开启，但还没有配置 `DESKTOP_EXPORT_DIR`。"
            "请先指定一个明确的本地导出目录。"
        )
    return None


def _resolve_desktop_export_target(file_name: str) -> tuple[Path, Path]:
    if settings.desktop_export_dir is None:
        raise PermissionError("DESKTOP_EXPORT_DIR is not configured")
    export_dir = settings.desktop_export_dir.expanduser().resolve()
    export_dir.mkdir(parents=True, exist_ok=True)
    target = (export_dir / file_name).resolve()
    try:
        target.relative_to(export_dir)
    except ValueError as exc:
        raise PermissionError("桌面导出路径超出 DESKTOP_EXPORT_DIR 范围") from exc
    return export_dir, target


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
    terminal: bool | None = None,
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
        terminal=terminal,
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
    terminal = _normalize_optional_bool(value.get("terminal"))
    return WorkspaceToolPlan(
        tool_name=tool_name or WORKSPACE_TOOL_NAME_OVERVIEW,
        tool_input=tool_input,
        reason=reason,
        terminal=terminal,
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


def write_workspace_text(
    rel_path: str,
    content: str = "",
    *,
    overwrite: bool = False,
    max_chars: int = DEFAULT_WRITE_TEXT_LIMIT,
) -> dict[str, object]:
    normalized_path = _resolve_workspace_rel_path(rel_path)
    target = resolve_workspace_path(normalized_path)
    existed = target.exists()
    if existed and not overwrite:
        raise FileExistsError(f"workspace file already exists: {normalized_path}")

    clipped_content, total_chars, truncated = _clip_output(
        content,
        limit=_normalize_positive_limit(max_chars, default=DEFAULT_WRITE_TEXT_LIMIT),
    )
    safe_write_file(normalized_path, clipped_content)
    return {
        "path": normalized_path,
        "created": not existed,
        "overwritten": existed,
        "chars_written": len(clipped_content),
        "total_chars": total_chars,
        "truncated": truncated,
    }


def export_desktop_text(
    rel_path: str | None,
    content: str = "",
    *,
    overwrite: bool = False,
    max_chars: int = DEFAULT_WRITE_TEXT_LIMIT,
) -> dict[str, object]:
    disabled_summary = _desktop_export_disabled_summary()
    if disabled_summary is not None:
        raise PermissionError(disabled_summary)

    file_name = _sanitize_desktop_export_file_name(rel_path)
    export_dir, target = _resolve_desktop_export_target(file_name)
    existed = target.exists()
    if existed and not overwrite:
        raise FileExistsError(f"desktop export file already exists: {target}")

    clipped_content, total_chars, truncated = _clip_output(
        content,
        limit=_normalize_positive_limit(max_chars, default=DEFAULT_WRITE_TEXT_LIMIT),
    )
    target.write_text(clipped_content, encoding="utf-8")
    return {
        "path": str(target),
        "export_dir": str(export_dir),
        "file_name": file_name,
        "created": not existed,
        "overwritten": existed,
        "chars_written": len(clipped_content),
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


def _format_workspace_entry_for_user(entry: Mapping[str, object]) -> str:
    kind = str(entry.get("kind") or "file").strip()
    kind_label = "目录" if kind == "dir" else "文件"
    path = str(entry.get("path") or "").strip() or "<unknown>"
    return f"- {kind_label}: {path}"


def _format_file_preview_for_user(data: Mapping[str, object]) -> str:
    path = str(data.get("path") or "").strip() or "目标文件"
    content = str(data.get("content") or "")
    lines = [f"我读到了 `{path}` 的内容。"]

    if not content:
        lines.append("")
        lines.append("这个文件目前没有可显示的文本内容。")
        return "\n".join(lines)

    lines.append("")
    lines.append("内容预览:")
    lines.append(content)
    if bool(data.get("truncated")):
        lines.append("")
        lines.append("内容比较长，我这里只显示了前半部分。")
    return "\n".join(lines)


def _format_listing_for_user(data: Mapping[str, object]) -> str:
    path = str(data.get("path") or ".").strip() or "."
    total = int(data.get("total") or 0)
    items = data.get("items")
    lines = [f"我列出了 `{path}` 下的内容，共找到 {total} 项。"]

    if isinstance(items, list) and items:
        lines.append("")
        lines.extend(
            _format_workspace_entry_for_user(entry)
            for entry in items
            if isinstance(entry, Mapping)
        )
    else:
        lines.append("")
        lines.append("这个目录目前是空的。")

    if bool(data.get("truncated")):
        shown = len(items) if isinstance(items, list) else 0
        lines.append("")
        lines.append(f"内容较多，这里先显示前 {shown} 项。")
    return "\n".join(lines)


def _format_test_result_for_user(data: Mapping[str, object]) -> str:
    ok = bool(data.get("ok"))
    target_paths = data.get("target_paths")
    targets = (
        ", ".join(str(path) for path in target_paths)
        if isinstance(target_paths, list) and target_paths
        else "默认测试目录"
    )
    summary = _normalize_optional_text(data.get("summary"))
    stdout_preview = _normalize_optional_text(data.get("stdout_preview"))
    stderr_preview = _normalize_optional_text(data.get("stderr_preview"))

    lines = [
        "我运行完测试了。",
        "",
        f"目标: {targets}",
        f"结果: {'通过' if ok else '未通过'}",
    ]

    if summary is not None:
        lines.extend(["", summary])

    if stderr_preview is not None:
        lines.extend(["", "错误输出预览:", stderr_preview])
    elif stdout_preview is not None and not ok:
        lines.extend(["", "输出预览:", stdout_preview])

    return "\n".join(lines)


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


def _format_workspace_write_summary(data: Mapping[str, object]) -> str:
    if str(data.get("target_location") or "").strip() == "desktop":
        action = "覆盖" if bool(data.get("overwritten")) else "导出"
        lines = [
            f"已按配置{action}文本文件到桌面导出目录。",
            "",
            f"path: {data.get('path')}",
            f"chars_written: {data.get('chars_written')}",
        ]
        if bool(data.get("truncated")):
            lines.append("注意: 内容超过长度限制，已裁剪后写入。")
        return "\n".join(lines)

    action = "覆盖" if bool(data.get("overwritten")) else "创建"
    lines = [
        f"已在 workspace 中{action}文本文件。",
        "",
        f"path: {data.get('path')}",
        f"chars_written: {data.get('chars_written')}",
    ]
    if bool(data.get("truncated")):
        lines.append("注意: 内容超过长度限制，已裁剪后写入。")
    return "\n".join(lines)


def _execute_write_tool(tool_input: Mapping[str, object]) -> tuple[dict[str, object], str]:
    rel_path = _normalize_rel_path(
        _normalize_optional_text(tool_input.get("rel_path")) or DEFAULT_WRITE_TEXT_REL_PATH
    )
    content = str(tool_input.get("content") or "")
    overwrite = bool(tool_input.get("overwrite", False))
    max_chars = int(tool_input.get("max_chars") or DEFAULT_WRITE_TEXT_LIMIT)
    target_location = str(tool_input.get("target_location") or "workspace").strip().lower()
    if target_location == "desktop":
        data = export_desktop_text(
            rel_path,
            content,
            overwrite=overwrite,
            max_chars=max_chars,
        )
        data["target_location"] = "desktop"
    else:
        data = write_workspace_text(
            rel_path,
            content,
            overwrite=overwrite,
            max_chars=max_chars,
        )
        data["target_location"] = "workspace"
    return data, _format_workspace_write_summary(data)


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
    WORKSPACE_TOOL_NAME_WRITE: WorkspaceToolDefinition(
        name=WORKSPACE_TOOL_NAME_WRITE,
        title="写入工作区文本",
        description="在受控 workspace 内创建或覆盖文本文件；不支持直接写桌面或任意系统路径。",
        category=WORKSPACE_TOOL_CATEGORY_EXECUTION,
        output_kind=WORKSPACE_TOOL_OUTPUT_KIND_FILE_WRITE,
        input_keys=("rel_path", "content", "overwrite", "max_chars", "target_location"),
        executor=_execute_write_tool,
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

    if _looks_like_text_file_write_request(normalized_prompt):
        return _build_workspace_tool_plan(
            WORKSPACE_TOOL_NAME_WRITE,
            reason="Prompt asks to create or write a text file.",
            terminal=True,
            rel_path=_first_text_file_candidate(normalized_prompt) or DEFAULT_WRITE_TEXT_REL_PATH,
            content=_extract_requested_text_content(normalized_prompt),
            overwrite=False,
            target_location=_target_location_from_prompt(normalized_prompt),
        )

    if _contains_keyword(normalized_prompt, WORKSPACE_TOOL_TEST_KEYWORDS):
        target_paths = [rel_path for rel_path, _ in matched_paths]
        if not target_paths:
            target_paths = _default_test_paths()
        if target_paths:
            return _build_workspace_tool_plan(
                WORKSPACE_TOOL_NAME_TEST,
                reason="Prompt asks for test-related coding work.",
                terminal=_looks_like_pure_test_request(normalized_prompt),
                test_paths=target_paths,
            )

    matched_file = _first_matching_path(matched_paths, want_file=True)
    if matched_file is not None:
        return _build_workspace_tool_plan(
            WORKSPACE_TOOL_NAME_READ,
            reason="Prompt references a workspace file path.",
            terminal=_looks_like_pure_read_request(normalized_prompt),
            rel_path=matched_file,
        )

    if _contains_keyword(normalized_prompt, WORKSPACE_TOOL_LIST_KEYWORDS):
        matched_dir = _first_matching_path(matched_paths, want_file=False) or "."
        return _build_workspace_tool_plan(
            WORKSPACE_TOOL_NAME_LIST,
            reason="Prompt asks for workspace structure.",
            terminal=_looks_like_pure_list_request(normalized_prompt),
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

    if (
        tool_name == WORKSPACE_TOOL_NAME_WRITE
        and str(tool_input.get("target_location") or "").strip().lower() == "desktop"
    ):
        disabled_summary = _desktop_export_disabled_summary()
        if disabled_summary is None:
            disabled_summary = ""
        if disabled_summary:
            return WorkspaceToolExecutionResult(
                tool_name=tool_name,
                tool_input=tool_input,
                ok=False,
                reason=reason,
                tool_category=tool_definition.category,
                tool_output_kind=tool_definition.output_kind,
                tool_error_code=WORKSPACE_TOOL_ERROR_TARGET_DISABLED,
                tool_descriptor=WorkspaceToolDescriptor.from_value(tool_descriptor),
                summary=disabled_summary,
                error="desktop export is disabled or not configured",
                data=None,
            ).as_dict()

    if (
        tool_name == WORKSPACE_TOOL_NAME_WRITE
        and str(tool_input.get("target_location") or "").strip().lower() not in {"", "workspace", "desktop"}
    ):
        return WorkspaceToolExecutionResult(
            tool_name=tool_name,
            tool_input=tool_input,
            ok=False,
            reason=reason,
            tool_category=tool_definition.category,
            tool_output_kind=tool_definition.output_kind,
            tool_error_code=WORKSPACE_TOOL_ERROR_TARGET_UNSUPPORTED,
            tool_descriptor=WorkspaceToolDescriptor.from_value(tool_descriptor),
            summary="当前只支持写入 workspace 或显式配置过的桌面导出目录。",
            error="unsupported write target location",
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


def build_workspace_tool_user_output(result: Mapping[str, object]) -> str | None:
    if _normalize_optional_text(result.get("error")) is not None:
        return _normalize_optional_text(result.get("summary"))

    data = result.get("data")
    if not isinstance(data, Mapping):
        return _normalize_optional_text(result.get("summary"))

    output_kind = str(result.get("tool_output_kind") or "").strip()
    if output_kind == WORKSPACE_TOOL_OUTPUT_KIND_FILE_PREVIEW:
        return _format_file_preview_for_user(data)
    if output_kind == WORKSPACE_TOOL_OUTPUT_KIND_LISTING:
        return _format_listing_for_user(data)
    if output_kind == WORKSPACE_TOOL_OUTPUT_KIND_COMMAND_RESULT:
        return _format_test_result_for_user(data)
    if output_kind == WORKSPACE_TOOL_OUTPUT_KIND_FILE_WRITE:
        return _normalize_optional_text(result.get("summary"))
    return None
