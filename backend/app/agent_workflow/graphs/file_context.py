from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import PurePosixPath


FILE_CONTEXT_KEYS = frozenset(
    {
        "last_file_action",
        "last_file_action_ok",
        "last_written_file",
        "last_created_file",
        "last_read_file",
        "last_deleted_file",
        "last_source_file",
        "last_search_results",
    }
)
FILE_REFERENCE_PHRASES = (
    "刚才创建的文件",
    "刚刚创建的文件",
    "刚才写入的文件",
    "刚刚写入的文件",
    "刚才保存的文件",
    "刚刚保存的文件",
    "刚才读取的文件",
    "刚刚读取的文件",
    "刚才那个文件",
    "刚刚那个文件",
    "刚才的文件",
    "刚刚的文件",
    "上一个文件",
    "前一个文件",
    "这个文件",
    "那个文件",
)
SEARCH_REFERENCE_PHRASES = (
    "刚才搜索到的文件",
    "刚刚搜索到的文件",
    "刚才查找到的文件",
    "刚刚查找到的文件",
    "搜索结果",
    "查找结果",
    "第一个结果",
    "第一个搜索结果",
    "第一条结果",
)
COPY_WITHOUT_TARGET_PHRASES = (
    "复制一份",
    "拷贝一份",
    "备份一份",
    "duplicate",
)
COPY_KEYWORDS = (
    "复制",
    "拷贝",
    "备份",
    "copy",
    "duplicate",
)
ENGLISH_FILE_REFERENCE_PATTERN = re.compile(
    r"\b(?:that|this|last|previous)\s+file\b",
    flags=re.IGNORECASE,
)
ENGLISH_SEARCH_REFERENCE_PATTERN = re.compile(
    r"\b(?:first\s+)?(?:search\s+)?result\b",
    flags=re.IGNORECASE,
)


def _normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _coerce_mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _coerce_search_results(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def coerce_file_context(value: object) -> dict[str, object]:
    raw = _coerce_mapping(value)
    context: dict[str, object] = {}
    for key in FILE_CONTEXT_KEYS:
        if key not in raw:
            continue
        if key == "last_file_action_ok":
            context[key] = _normalize_bool(raw.get(key))
            continue
        if key == "last_search_results":
            context[key] = _coerce_search_results(raw.get(key))
            continue
        text = _normalize_text(raw.get(key))
        if text:
            context[key] = text
    return context


def merge_file_context(
    current_context: object,
    updates: object,
) -> dict[str, object]:
    merged = coerce_file_context(current_context)
    for key, value in coerce_file_context(updates).items():
        merged[key] = value
    return merged


def file_state_from_action_result(
    action_name: str,
    action_input: Mapping[str, object],
    action_result: Mapping[str, object],
) -> dict[str, object]:
    data_map = _coerce_mapping(action_result.get("data"))
    state: dict[str, object] = {
        "last_file_action": action_name,
        "last_file_action_ok": bool(action_result.get("ok")),
    }
    path = data_map.get("path") or action_input.get("rel_path")
    source_path = data_map.get("source_path") or action_input.get("source_path")
    target_path = data_map.get("target_path") or action_input.get("target_path")

    if action_name in {"workspace.write", "workspace.export_desktop"} and path:
        state["last_written_file"] = str(path)
        state["last_created_file"] = str(path)
    if action_name == "workspace.read" and path:
        state["last_read_file"] = str(path)
    if action_name == "workspace.delete" and path:
        state["last_deleted_file"] = str(path)
    if action_name in {"workspace.move", "workspace.copy"}:
        if source_path:
            state["last_source_file"] = str(source_path)
        if target_path:
            state["last_created_file"] = str(target_path)
            state["last_written_file"] = str(target_path)
    if action_name == "workspace.search":
        matches = data_map.get("matches")
        state["last_search_results"] = matches if isinstance(matches, list) else []
    return state


def first_search_result_path(file_context: object) -> str | None:
    context = coerce_file_context(file_context)
    matches = _coerce_search_results(context.get("last_search_results"))
    if not matches:
        return None
    return _normalize_text(matches[0].get("path")) or None


def recent_file_path(file_context: object) -> str | None:
    context = coerce_file_context(file_context)
    for key in (
        "last_written_file",
        "last_created_file",
        "last_read_file",
        "last_source_file",
    ):
        path = _normalize_text(context.get(key))
        if path:
            return path
    return first_search_result_path(context)


def _prompt_has_any(prompt: str, phrases: tuple[str, ...]) -> bool:
    lowered = prompt.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def prompt_references_file_context(prompt: str) -> bool:
    text = str(prompt or "").strip()
    if not text:
        return False
    return (
        _prompt_has_any(text, FILE_REFERENCE_PHRASES)
        or _prompt_has_any(text, SEARCH_REFERENCE_PHRASES)
        or ENGLISH_FILE_REFERENCE_PATTERN.search(text) is not None
        or ENGLISH_SEARCH_REFERENCE_PATTERN.search(text) is not None
    )


def _source_path_for_prompt(prompt: str, file_context: object) -> str | None:
    text = str(prompt or "")
    if (
        _prompt_has_any(text, SEARCH_REFERENCE_PHRASES)
        or ENGLISH_SEARCH_REFERENCE_PATTERN.search(text) is not None
    ):
        return first_search_result_path(file_context) or recent_file_path(file_context)
    return recent_file_path(file_context)


def resolve_prompt_file_references(
    prompt: str,
    file_context: object,
) -> tuple[str, str | None]:
    text = str(prompt or "")
    if not text or not prompt_references_file_context(text):
        return text, None

    source_path = _source_path_for_prompt(text, file_context)
    if not source_path:
        return text, None

    resolved = text
    replacement = f" {source_path} "
    for phrase in sorted(SEARCH_REFERENCE_PHRASES + FILE_REFERENCE_PHRASES, key=len, reverse=True):
        if phrase in resolved:
            resolved = resolved.replace(phrase, replacement)

    resolved = ENGLISH_SEARCH_REFERENCE_PATTERN.sub(replacement, resolved)
    resolved = ENGLISH_FILE_REFERENCE_PATTERN.sub(replacement, resolved)
    return resolved, source_path


def prompt_requests_contextual_copy_without_target(prompt: str) -> bool:
    text = str(prompt or "").strip()
    if not text or not _prompt_has_any(text, COPY_KEYWORDS):
        return False
    return _prompt_has_any(text, COPY_WITHOUT_TARGET_PHRASES)


def build_copy_target_path(source_path: str) -> str:
    source = PurePosixPath(str(source_path).replace("\\", "/"))
    suffix = source.suffix
    if suffix:
        target_name = f"{source.stem}-copy{suffix}"
    else:
        target_name = f"{source.name}-copy"
    return str(source.with_name(target_name))
