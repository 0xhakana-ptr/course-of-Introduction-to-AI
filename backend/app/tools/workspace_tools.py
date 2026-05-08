import sys
from collections.abc import Mapping, Sequence

from ..core.text_utils import clip_text
from .safe_execute_command import safe_execute_command
from .safe_fs import get_workspace_dir, resolve_workspace_path, safe_list_entries, safe_read_file


DEFAULT_TOOL_TEXT_LIMIT = 4000
DEFAULT_TOOL_ENTRY_LIMIT = 200
DEFAULT_FAILURE_SUMMARY_LIMIT = 1200
DEFAULT_WORKSPACE_OVERVIEW_ENTRY_LIMIT = 12
DEFAULT_WORKSPACE_OVERVIEW_FILE_PREVIEW_LIMIT = 600
DEFAULT_WORKSPACE_OVERVIEW_FILES = (
    "README.md",
    "backend/README.md",
    "backend/requirements.txt",
)


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
    timeout_seconds: int | None = None,
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
