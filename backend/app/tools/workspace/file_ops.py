import re
import shutil
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from ...core.config import settings
from ..safe_execute_command import safe_execute_command
from ..safe_fs import (
    check_write_permission,
    get_effective_workspace_dir,
    resolve_workspace_path,
    safe_list_entries,
    safe_read_file,
    safe_write_file,
)
from .constants import (
    DEFAULT_DESKTOP_EXPORT_FILE_NAME,
    DEFAULT_FAILURE_SUMMARY_LIMIT,
    DEFAULT_TOOL_ENTRY_LIMIT,
    DEFAULT_TOOL_TEST_TIMEOUT_SECONDS,
    DEFAULT_TOOL_TEXT_LIMIT,
    DEFAULT_WRITE_TEXT_LIMIT,
)
from .utils import (
    clip_output,
    normalize_optional_text,
    normalize_positive_limit,
    resolve_workspace_rel_path,
)


def sanitize_desktop_export_file_name(rel_path: str | None) -> str:
    raw_name = Path(str(rel_path or "").replace("\\", "/")).name.strip()
    if not raw_name:
        raw_name = DEFAULT_DESKTOP_EXPORT_FILE_NAME
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw_name).strip(" .")
    if not cleaned:
        cleaned = DEFAULT_DESKTOP_EXPORT_FILE_NAME
    if not cleaned.lower().endswith(".txt"):
        cleaned = f"{cleaned}.txt"
    return cleaned


def desktop_export_disabled_summary() -> str | None:
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


def resolve_desktop_export_target(file_name: str) -> tuple[Path, Path]:
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


def workspace_rel_from_target(target: Path) -> str:
    return str(target.relative_to(get_effective_workspace_dir())).replace("\\", "/")


def list_workspace_entries(
    rel_path: str = ".",
    *,
    recursive: bool = False,
    max_entries: int = DEFAULT_TOOL_ENTRY_LIMIT,
) -> dict[str, object]:
    normalized_path = resolve_workspace_rel_path(rel_path)
    target = resolve_workspace_path(normalized_path)
    if not target.exists():
        return {
            "path": normalized_path,
            "exists": False,
            "kind": "missing",
            "recursive": recursive,
            "total": 0,
            "truncated": False,
            "items": [],
        }

    entries = safe_list_entries(normalized_path, recursive=recursive)
    limit = normalize_positive_limit(max_entries, default=DEFAULT_TOOL_ENTRY_LIMIT)
    return {
        "path": normalized_path,
        "exists": True,
        "kind": "file" if target.is_file() else "dir",
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
    normalized_path = resolve_workspace_rel_path(rel_path)
    content = safe_read_file(normalized_path)
    clipped_content, total_chars, truncated = clip_output(
        content,
        limit=normalize_positive_limit(max_chars, default=DEFAULT_TOOL_TEXT_LIMIT),
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
    normalized_path = resolve_workspace_rel_path(rel_path)
    target = resolve_workspace_path(normalized_path)
    existed = target.exists()
    if existed and not overwrite:
        raise FileExistsError(f"workspace file already exists: {normalized_path}")

    clipped_content, total_chars, truncated = clip_output(
        content,
        limit=normalize_positive_limit(max_chars, default=DEFAULT_WRITE_TEXT_LIMIT),
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
    disabled_summary = desktop_export_disabled_summary()
    if disabled_summary is not None:
        raise PermissionError(disabled_summary)

    file_name = sanitize_desktop_export_file_name(rel_path)
    export_dir, target = resolve_desktop_export_target(file_name)
    existed = target.exists()
    if existed and not overwrite:
        raise FileExistsError(f"desktop export file already exists: {target}")

    clipped_content, total_chars, truncated = clip_output(
        content,
        limit=normalize_positive_limit(max_chars, default=DEFAULT_WRITE_TEXT_LIMIT),
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


def move_workspace_path(
    source_path: str,
    target_path: str,
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    check_write_permission()

    normalized_source = resolve_workspace_rel_path(source_path)
    normalized_target = resolve_workspace_rel_path(target_path)
    source = resolve_workspace_path(normalized_source)
    target = resolve_workspace_path(normalized_target)

    if not source.exists():
        raise FileNotFoundError(normalized_source)
    if source == target:
        raise ValueError("source_path and target_path are the same")
    if source.is_dir():
        try:
            target.relative_to(source)
        except ValueError:
            pass
        else:
            raise PermissionError("cannot move a directory into itself")
    if target.exists():
        if not overwrite:
            raise FileExistsError(f"workspace path already exists: {normalized_target}")
        if target.is_dir():
            raise FileExistsError("cannot overwrite an existing directory")
        target.unlink()

    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return {
        "operation": "move",
        "source_path": normalized_source,
        "target_path": workspace_rel_from_target(target),
        "kind": "dir" if target.is_dir() else "file",
        "overwritten": overwrite,
    }


def copy_workspace_path(
    source_path: str,
    target_path: str,
    *,
    overwrite: bool = False,
    recursive: bool = False,
) -> dict[str, object]:
    check_write_permission()

    normalized_source = resolve_workspace_rel_path(source_path)
    normalized_target = resolve_workspace_rel_path(target_path)
    source = resolve_workspace_path(normalized_source)
    target = resolve_workspace_path(normalized_target)

    if not source.exists():
        raise FileNotFoundError(normalized_source)
    if source == target:
        raise ValueError("source_path and target_path are the same")
    if target.exists():
        if not overwrite:
            raise FileExistsError(f"workspace path already exists: {normalized_target}")
        if target.is_dir():
            raise FileExistsError("cannot overwrite an existing directory")
        target.unlink()

    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        if not recursive:
            raise IsADirectoryError("copying a directory requires recursive=true")
        shutil.copytree(source, target)
        kind = "dir"
    else:
        shutil.copy2(source, target)
        kind = "file"

    return {
        "operation": "copy",
        "source_path": normalized_source,
        "target_path": workspace_rel_from_target(target),
        "kind": kind,
        "overwritten": overwrite,
        "recursive": recursive,
    }


def delete_workspace_path(
    rel_path: str,
    *,
    recursive: bool = False,
) -> dict[str, object]:
    check_write_permission()

    normalized_path = resolve_workspace_rel_path(rel_path)
    target = resolve_workspace_path(normalized_path)
    if not target.exists():
        raise FileNotFoundError(normalized_path)

    if target.is_dir():
        if not recursive:
            raise IsADirectoryError("deleting a directory requires recursive=true")
        shutil.rmtree(target)
        kind = "dir"
    else:
        target.unlink()
        kind = "file"

    return {
        "operation": "delete",
        "path": normalized_path,
        "kind": kind,
        "recursive": recursive,
    }


def search_workspace_text(
    query: str,
    rel_path: str = ".",
    *,
    recursive: bool = True,
    max_matches: int = 20,
    max_chars: int = 240,
) -> dict[str, object]:
    normalized_query = normalize_optional_text(query)
    if normalized_query is None:
        raise ValueError("search query is required")

    normalized_path = resolve_workspace_rel_path(rel_path)
    root = resolve_workspace_path(normalized_path)
    if not root.exists():
        raise FileNotFoundError(normalized_path)

    if root.is_file():
        files = [root]
    elif recursive:
        files = [path for path in root.rglob("*") if path.is_file()]
    else:
        files = [path for path in root.glob("*") if path.is_file()]

    query_folded = normalized_query.casefold()
    limit = normalize_positive_limit(max_matches, default=20)
    preview_limit = normalize_positive_limit(max_chars, default=240)
    matches: list[dict[str, object]] = []
    scanned_files = 0

    for file_path in sorted(files, key=workspace_rel_from_target):
        if len(matches) >= limit:
            break
        scanned_files += 1
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for line_number, line in enumerate(content.splitlines(), start=1):
            if query_folded not in line.casefold():
                continue
            preview, _, truncated = clip_output(line.strip(), limit=preview_limit)
            matches.append(
                {
                    "path": workspace_rel_from_target(file_path),
                    "line_number": line_number,
                    "preview": preview,
                    "truncated": truncated,
                }
            )
            if len(matches) >= limit:
                break

    return {
        "operation": "search",
        "path": normalized_path,
        "query": normalized_query,
        "recursive": recursive,
        "scanned_files": scanned_files,
        "match_count": len(matches),
        "truncated": len(matches) >= limit,
        "matches": matches,
    }


def summarize_command_failure(
    result: Mapping[str, object],
    *,
    max_chars: int = DEFAULT_FAILURE_SUMMARY_LIMIT,
) -> str:
    limit = normalize_positive_limit(max_chars, default=DEFAULT_FAILURE_SUMMARY_LIMIT)
    sections: list[str] = []

    error = str(result.get("error") or "").strip()
    stderr = str(result.get("stderr") or "").strip()
    stdout = str(result.get("stdout") or "").strip()

    if error:
        error_preview, _, _ = clip_output(error, limit=limit)
        sections.append(f"error:\n{error_preview}")
    if stderr:
        stderr_preview, _, _ = clip_output(stderr, limit=limit)
        sections.append(f"stderr:\n{stderr_preview}")
    elif stdout:
        stdout_preview, _, _ = clip_output(stdout, limit=limit)
        sections.append(f"stdout:\n{stdout_preview}")

    if not sections:
        return "命令执行失败，但没有返回可用输出。"

    summary, _, truncated = clip_output("\n\n".join(sections), limit=limit)
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
        resolve_workspace_rel_path(path)
        for path in (test_paths or [])
        if str(path).strip()
    ]
    resolved_cwd = None if cwd is None else resolve_workspace_rel_path(cwd)
    output_limit = normalize_positive_limit(
        max_output_chars,
        default=DEFAULT_TOOL_TEXT_LIMIT,
    )

    command = [sys.executable, "-m", "pytest", *resolved_test_paths]
    result = safe_execute_command(
        command,
        cwd=resolved_cwd,
        timeout_seconds=timeout_seconds,
    )
    stdout_preview, stdout_length, stdout_truncated = clip_output(
        str(result.get("stdout") or ""),
        limit=output_limit,
    )
    stderr_preview, stderr_length, stderr_truncated = clip_output(
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

