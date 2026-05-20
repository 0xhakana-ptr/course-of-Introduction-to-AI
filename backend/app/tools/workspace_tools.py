import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..schemas import (
    WORKSPACE_TOOL_CATEGORY,
    WORKSPACE_TOOL_OUTPUT_KIND,
)
from ..llm.client import call_llm_sync, llm_is_configured

from .safe_fs import resolve_workspace_path
from .workspace.constants import (
    CODE_CONTENT_SUFFIXES,
    DEFAULT_TOOL_ENTRY_LIMIT,
    DEFAULT_TOOL_TEST_TIMEOUT_SECONDS,
    DEFAULT_TOOL_TEXT_LIMIT,
    DEFAULT_WORKSPACE_OVERVIEW_ENTRY_LIMIT,
    DEFAULT_WORKSPACE_OVERVIEW_FILE_PREVIEW_LIMIT,
    DEFAULT_WORKSPACE_OVERVIEW_FILES,
    DEFAULT_WORKSPACE_TEST_PATH_CANDIDATES,
    DEFAULT_WRITE_TEXT_LIMIT,
    DEFAULT_WRITE_TEXT_REL_PATH,
    WORKSPACE_TOOL_CATEGORY_CONTEXT,
    WORKSPACE_TOOL_CATEGORY_EXECUTION,
    WORKSPACE_TOOL_COPY_KEYWORDS,
    WORKSPACE_TOOL_DELETE_KEYWORDS,
    WORKSPACE_TOOL_DESKTOP_KEYWORDS,
    WORKSPACE_TOOL_DIRECTORY_KEYWORDS,
    WORKSPACE_TOOL_ERROR_EXECUTION_FAILED,
    WORKSPACE_TOOL_ERROR_TARGET_DISABLED,
    WORKSPACE_TOOL_ERROR_TARGET_UNSUPPORTED,
    WORKSPACE_TOOL_ERROR_UNREGISTERED,
    WORKSPACE_TOOL_INPUT_KEYS,
    WORKSPACE_TOOL_LIST_KEYWORDS,
    WORKSPACE_TOOL_MOVE_KEYWORDS,
    WORKSPACE_TOOL_NAME_COPY,
    WORKSPACE_TOOL_NAME_DELETE,
    WORKSPACE_TOOL_NAME_LIST,
    WORKSPACE_TOOL_NAME_MOVE,
    WORKSPACE_TOOL_NAME_OVERVIEW,
    WORKSPACE_TOOL_NAME_READ,
    WORKSPACE_TOOL_NAME_SEARCH,
    WORKSPACE_TOOL_NAME_TEST,
    WORKSPACE_TOOL_NAME_WRITE,
    WORKSPACE_TOOL_OUTPUT_KIND_COMMAND_RESULT,
    WORKSPACE_TOOL_OUTPUT_KIND_FILE_OPERATION,
    WORKSPACE_TOOL_OUTPUT_KIND_FILE_PREVIEW,
    WORKSPACE_TOOL_OUTPUT_KIND_FILE_WRITE,
    WORKSPACE_TOOL_OUTPUT_KIND_LISTING,
    WORKSPACE_TOOL_OUTPUT_KIND_OVERVIEW,
    WORKSPACE_TOOL_OUTPUT_KIND_TEXT_SEARCH,
    WORKSPACE_TOOL_PATH_PATTERN,
    WORKSPACE_TOOL_QUOTED_PATH_PATTERN,
    WORKSPACE_TOOL_READ_KEYWORDS,
    WORKSPACE_TOOL_RECURSIVE_KEYWORDS,
    WORKSPACE_TOOL_SEARCH_KEYWORDS,
    WORKSPACE_TOOL_TEST_KEYWORDS,
    WORKSPACE_TOOL_TEXT_FILE_KEYWORDS,
    WORKSPACE_TOOL_WRITE_KEYWORDS,
    WORKSPACE_TOOL_CODEGEN_TASK_KEYWORDS,
)
from .workspace.file_ops import (
    copy_workspace_path,
    delete_workspace_path,
    desktop_export_disabled_summary as _desktop_export_disabled_summary,
    export_desktop_text,
    list_workspace_entries,
    move_workspace_path,
    read_workspace_text,
    run_workspace_tests,
    search_workspace_text,
    summarize_command_failure,
    write_workspace_text,
)
from .workspace.formatters import (
    format_file_operation_for_user as _format_file_operation_for_user,
    format_file_preview_for_user as _format_file_preview_for_user,
    format_listing_for_user as _format_listing_for_user,
    format_search_result_for_user as _format_search_result_for_user,
    format_test_result_for_user as _format_test_result_for_user,
    format_workspace_entry as _format_workspace_entry,
    format_workspace_listing_summary as _format_workspace_listing_summary,
    format_workspace_operation_summary as _format_workspace_operation_summary,
    format_workspace_search_summary as _format_workspace_search_summary,
    format_workspace_test_summary as _format_workspace_test_summary,
    format_workspace_write_summary as _format_workspace_write_summary,
)
from .workspace.utils import (
    contains_keyword as _contains_keyword,
    normalize_optional_bool as _normalize_optional_bool,
    normalize_optional_text as _normalize_optional_text,
    normalize_rel_path as _normalize_rel_path,
)
from .workspace_tool_models import (
    WorkspaceToolDescriptor,
    WorkspaceToolExecutionResult,
    WorkspaceToolPlan,
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


def _clean_prompt_path_candidate(candidate: str) -> str:
    cleaned = candidate.strip().strip("`'\"“”‘’.,:;()[]{}<>，。！？、；：")
    return cleaned.replace("\\", "/")


def _looks_like_path_candidate(candidate: str) -> bool:
    cleaned = _clean_prompt_path_candidate(candidate)
    if not cleaned:
        return False
    if "/" in cleaned or "\\" in cleaned:
        return True
    return bool(Path(cleaned).suffix)


def _append_unique_path(paths: list[str], seen: set[str], candidate: str) -> None:
    rel_path = _clean_prompt_path_candidate(candidate)
    if not rel_path or rel_path in seen or not _looks_like_path_candidate(rel_path):
        return
    seen.add(rel_path)
    paths.append(rel_path)


def _iter_existing_workspace_paths(prompt: str) -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []

    for rel_path in _iter_prompt_path_candidates(prompt):
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
    for matched in WORKSPACE_TOOL_QUOTED_PATH_PATTERN.findall(prompt):
        _append_unique_path(paths, seen, matched)

    for matched in WORKSPACE_TOOL_PATH_PATTERN.findall(prompt):
        _append_unique_path(paths, seen, matched)
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


# Mapping of code language keywords to file extensions for write detection
_CODE_LANGUAGE_SUFFIX_MAP: dict[str, str] = {
    "cpp": ".cpp", "c++": ".cpp", "c": ".c",
    "python": ".py", "py": ".py",
    "java": ".java",
    "javascript": ".js", "js": ".js",
    "typescript": ".ts", "ts": ".ts",
    "go": ".go", "golang": ".go",
    "rust": ".rs", "rs": ".rs",
    "html": ".html",
    "css": ".css",
    "vue": ".vue",
    "sql": ".sql",
    "bash": ".sh", "shell": ".sh",
    "powershell": ".ps1",
    "ruby": ".rb",
    "php": ".php",
    "kotlin": ".kt",
    "swift": ".swift",
}

_CODE_LANGUAGE_PATTERN = re.compile(
    r"(?:\u5199|\u521b\u5efa|\u65b0\u5efa|\u751f\u6210|write|create|generate)\s*(?:\u4e00\u4e2a|\u4e2a|a|an)?\s*"
    r"([A-Za-z+#]+|\w+)\s*(?:\u4ee3\u7801|\u6587\u4ef6|\u811a\u672c|code|file|script)",
    re.IGNORECASE,
)

def _detect_code_language(prompt: str) -> str | None:
    """Detect programming language from a code-write request prompt.
    Returns file extension (e.g. '.cpp') or None.
    """
    text = prompt.lower()
    # Direct language name match
    for lang, ext in _CODE_LANGUAGE_SUFFIX_MAP.items():
        if lang in text:
            return ext
    # Pattern: "\u5199\u4e00\u4e2aXX\u4ee3\u7801" -> extract XX
    m = _CODE_LANGUAGE_PATTERN.search(prompt)
    if m:
        lang_hint = m.group(1).strip().lower()
        if lang_hint in _CODE_LANGUAGE_SUFFIX_MAP:
            return _CODE_LANGUAGE_SUFFIX_MAP[lang_hint]
    return None

def _infer_code_file_path(prompt: str) -> str:
    """Infer a reasonable file path from a code-write request."""
    ext = _detect_code_language(prompt) or ".txt"
    # Try to extract a topic/name from the prompt
    topic = ""
    # Pattern: "\u4e00\u4e2aXXX\u7684" -> XXX is the topic
    topic_m = re.search(r"(?:\u4e00\u4e2a|\u4e2a)(.+?)(?:\u7684|\u4ee3\u7801|\u6587\u4ef6|\u811a\u672c)", prompt)
    if topic_m:
        topic = topic_m.group(1).strip()
        # Sanitize topic to be a valid filename component
        topic = re.sub(r"[^\w\u4e00-\u9fff-]", "_", topic)[:30]
    if not topic:
        topic = "code"
    return f"{topic}{ext}"

def _generate_code_via_llm(prompt: str, language_hint: str) -> str:
    """Generate code content via LLM for a write request."""
    if not llm_is_configured():
        return ""
    system_prompt = f"You are a code generator. Write ONLY the code, no explanations. Language: {language_hint}. Output raw code only, no markdown fences."
    result = call_llm_sync(
        prompt=prompt,
        context=None,
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=3000,
    )
    if result.ok and result.output:
        code = result.output.strip()
        # Strip markdown fences if present
        code = re.sub(r"^```[\w]*\n", "", code)
        code = re.sub(r"\n```$", "", code)
        return code.strip()
    return ""

def _looks_like_text_file_write_request(prompt: str) -> bool:
    if not _contains_keyword(prompt, WORKSPACE_TOOL_WRITE_KEYWORDS):
        return False
    if _contains_keyword(prompt, WORKSPACE_TOOL_TEXT_FILE_KEYWORDS):
        return True
    if any(
        Path(candidate).suffix
        for candidate in _iter_prompt_path_candidates(prompt)
    ):
        return True
    # Also match code-language write requests like "\u5199\u4e00\u4e2aCPP\u4ee3\u7801"
    if _detect_code_language(prompt) is not None:
        return True
    return False


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
    suffixed_candidate = None
    for candidate in _iter_prompt_path_candidates(prompt):
        if candidate.lower().endswith(".txt"):
            return candidate
        if suffixed_candidate is None and Path(candidate).suffix:
            suffixed_candidate = candidate
    return suffixed_candidate


def _has_two_path_candidates(prompt: str) -> bool:
    return len(_iter_prompt_path_candidates(prompt)) >= 2


def _looks_like_move_request(prompt: str) -> bool:
    return _contains_keyword(prompt, WORKSPACE_TOOL_MOVE_KEYWORDS) and _has_two_path_candidates(prompt)


def _looks_like_copy_request(prompt: str) -> bool:
    return _contains_keyword(prompt, WORKSPACE_TOOL_COPY_KEYWORDS) and _has_two_path_candidates(prompt)


def _looks_like_delete_request(prompt: str) -> bool:
    return _contains_keyword(prompt, WORKSPACE_TOOL_DELETE_KEYWORDS) and bool(
        _iter_prompt_path_candidates(prompt)
    )


def _looks_like_search_request(prompt: str) -> bool:
    return _contains_keyword(prompt, WORKSPACE_TOOL_SEARCH_KEYWORDS) and (
        bool(_extract_search_query(prompt)) or bool(_iter_prompt_path_candidates(prompt))
    )


def _existing_workspace_path_is_dir(rel_path: str) -> bool:
    try:
        target = resolve_workspace_path(rel_path)
    except PermissionError:
        return False
    return target.exists() and target.is_dir()


def _prompt_mentions_directory(prompt: str) -> bool:
    return _contains_keyword(prompt, WORKSPACE_TOOL_DIRECTORY_KEYWORDS)


def _prompt_requests_recursive_operation(prompt: str) -> bool:
    return _contains_keyword(prompt, WORKSPACE_TOOL_RECURSIVE_KEYWORDS)


def _copy_recursive_from_prompt(prompt: str, source_path: str) -> bool:
    return (
        _existing_workspace_path_is_dir(source_path)
        or _prompt_mentions_directory(prompt)
        or _prompt_requests_recursive_operation(prompt)
    )


def _delete_recursive_from_prompt(prompt: str, rel_path: str) -> bool:
    return (
        _existing_workspace_path_is_dir(rel_path)
        and (_prompt_mentions_directory(prompt) or _prompt_requests_recursive_operation(prompt))
    )


def _destination_path_from_candidates(source_path: str, target_path: str) -> str:
    source = PurePosixPath(_clean_prompt_path_candidate(source_path))
    target = _clean_prompt_path_candidate(target_path)
    if not target:
        return target

    if target.endswith("/"):
        return str(PurePosixPath(target) / source.name)

    target_posix = PurePosixPath(target)
    if "/" not in target and source.parent != PurePosixPath("."):
        return str(source.parent / target_posix.name)

    try:
        target_workspace_path = resolve_workspace_path(target)
    except PermissionError:
        return target
    if target_workspace_path.exists() and target_workspace_path.is_dir():
        return str(target_posix / source.name)
    return target


def _source_and_target_candidates(prompt: str) -> tuple[str, str] | None:
    paths = _iter_prompt_path_candidates(prompt)
    if len(paths) < 2:
        return None
    source_path = paths[0]
    target_path = _destination_path_from_candidates(source_path, paths[1])
    if not source_path or not target_path:
        return None
    return source_path, target_path


def _strip_search_query(text: str) -> str:
    cleaned = text.strip().strip("`'\"“”‘’.,:;()[]{}<>，。！？、；：")
    suffixes = (
        "的文件",
        "文件",
        "内容",
        "text",
        "files",
        "file",
    )
    for suffix in suffixes:
        if cleaned.lower().endswith(suffix.lower()):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned.strip().strip("`'\"“”‘’.,:;()[]{}<>，。！？、；：")


def _extract_search_query(prompt: str) -> str:
    patterns = (
        r"(?:包含|含有|包括)\s*[`\"'“”‘’]?(.+?)[`\"'“”‘’]?(?:的文件|文件|$)",
        r"(?:搜索|查找)\s*[`\"'“”‘’]?(.+?)[`\"'“”‘’]?(?:的文件|文件|内容|$)",
        r"(?:搜索|查找)\s*[`\"'“”‘’]?(.+?)[`\"'“”‘’]?\s*(?:在|于)\b",
        r"(?:search for|find|grep|contains)\s*[`\"']?(.+?)[`\"']?(?:\s+in\b|$)",
    )
    for pattern in patterns:
        matched = re.search(pattern, prompt, flags=re.IGNORECASE | re.DOTALL)
        if matched is not None:
            query = _strip_search_query(matched.group(1))
            if query:
                return query
    return ""


def _search_root_from_prompt(prompt: str, matched_paths: Sequence[tuple[str, Path]]) -> str:
    matched_dir = _first_matching_path(matched_paths, want_file=False)
    if matched_dir is not None:
        return matched_dir

    path_candidates = _iter_prompt_path_candidates(prompt)
    if path_candidates:
        return path_candidates[0]

    bare_dir_patterns = (
        r"(?:在|查找|搜索)\s*([\w\u4e00-\u9fff_.-]+)\s*(?:下|目录|里|中)",
        r"([\w\u4e00-\u9fff_.-]+)\s*(?:目录)?(?:下|里|中)\s*(?:包含|含有|搜索|查找)",
    )
    for pattern in bare_dir_patterns:
        matched = re.search(pattern, prompt, flags=re.IGNORECASE)
        if matched is None:
            continue
        candidate = _clean_prompt_path_candidate(matched.group(1))
        if not candidate:
            continue
        try:
            target = resolve_workspace_path(candidate)
        except PermissionError:
            continue
        if target.exists() and target.is_dir():
            return candidate
    return "."


def _target_prefers_raw_code(rel_path: str | None) -> bool:
    suffix = Path(str(rel_path or "")).suffix.lower()
    return suffix in CODE_CONTENT_SUFFIXES


def _find_content_marker(prompt: str) -> re.Match[str] | None:
    pattern = re.compile(
        r"(?:内容是|内容为|内容如下|内容：|内容:|代码是|代码为|代码如下|"
        r"with content|content is|content:)\s*[:：]?\s*",
        flags=re.IGNORECASE,
    )
    return pattern.search(prompt)


def _mask_protected_content_blocks(content: str) -> str:
    chars = list(content)
    protected_patterns = (
        re.compile(r"```.*?```", flags=re.DOTALL),
        re.compile(r"\$\$.*?\$\$", flags=re.DOTALL),
    )
    for pattern in protected_patterns:
        for matched in pattern.finditer(content):
            for index in range(matched.start(), matched.end()):
                chars[index] = " "
    return "".join(chars)


def _strip_outer_fenced_code_block_if_needed(content: str, rel_path: str | None) -> str:
    if not _target_prefers_raw_code(rel_path):
        return content

    matched = re.fullmatch(
        r"\s*```[A-Za-z0-9_+.#-]*[^\n]*\n(?P<body>.*?)(?:\n)?```\s*",
        content,
        flags=re.DOTALL,
    )
    if matched is None:
        return content
    return matched.group("body").strip("\n")


def _last_path_index_in_prompt(prompt: str, rel_path: str) -> int:
    """Return the start index of the last occurrence of *rel_path* in *prompt*."""
    normalized = rel_path.replace("\\", "/").rstrip("/")
    idx = prompt.rfind(normalized)
    if idx >= 0:
        return idx
    basename = normalized.rsplit("/", 1)[-1]
    return prompt.rfind(basename)


def _strip_leading_clutter(text: str) -> str:
    """Strip leading punctuation, spaces, and connector phrases."""
    text = re.sub(
        r"^[\s\uFF0C,\u3002\uFF1B;\uFF1A:\u3001\uFF01!\uFF1F?]*(?:\u7684?\s*(?:\u6587\u4EF6|\u6587\u6863|\u6587\u672C|\u4EE3\u7801))?\s*[,\uFF0C]?\s*",
        "",
        text,
    )
    return text.strip()


def _extract_requested_text_content(prompt: str, *, rel_path: str | None = None) -> str:
    matched = _find_content_marker(prompt)
    if matched is not None:
        content = prompt[matched.end() :].strip()
        trimmed = _trim_followup_from_text_content(content)
        return _strip_outer_fenced_code_block_if_needed(trimmed, rel_path)

    # Fallback: no explicit content marker (e.g. "\u5185\u5BB9\u662F") was found.
    # For write-intent prompts we try to extract content after the last
    # occurrence of the file path, then trim any follow-up instructions.
    if rel_path:
        path_idx = _last_path_index_in_prompt(prompt, rel_path)
        if path_idx >= 0:
            raw = _strip_leading_clutter(prompt[path_idx + len(rel_path):])
            if raw:
                trimmed = _trim_followup_from_text_content(raw)
                return _strip_outer_fenced_code_block_if_needed(trimmed, rel_path)

    return ""


def _trim_followup_from_text_content(content: str) -> str:
    masked_content = _mask_protected_content_blocks(content)
    followup_pattern = re.compile(
        r"(?:\s*(?:，|,|。|；|;)?\s*)?"
        r"(?P<connector>然后|之后|随后|再|并且|并|then)\s*"
        r"(?:读|读取|读出来|查看|确认|列出|运行|测试|read|show|preview|list|run|test)",
        flags=re.IGNORECASE,
    )
    matched = followup_pattern.search(masked_content)
    if matched is None:
        return content
    cut_index = matched.start("connector")
    return content[:cut_index].rstrip(" \t\r\n，,。；;").strip()


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


def _workspace_tool_failure_summary(
    tool_name: str,
    tool_input: Mapping[str, object],
    exc: Exception,
) -> str:
    rel_path = _normalize_optional_text(tool_input.get("rel_path"))
    if isinstance(exc, FileNotFoundError):
        target = rel_path or "目标路径"
        return (
            f"没有找到 workspace 路径 `{target}`。\n\n"
            "请检查文件名和目录层级，或先让我列出上一级目录。"
        )
    if isinstance(exc, PermissionError):
        return (
            "该路径不允许访问。请确认目标仍在项目 workspace 内，"
            "不要使用绝对路径或 `..` 跳出工作区。"
        )
    return f"Workspace tool `{tool_name}` failed: {exc}"


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


def _execute_move_tool(tool_input: Mapping[str, object]) -> tuple[dict[str, object], str]:
    source_path = _normalize_rel_path(_normalize_optional_text(tool_input.get("source_path")))
    target_path = _normalize_rel_path(_normalize_optional_text(tool_input.get("target_path")))
    data = move_workspace_path(
        source_path,
        target_path,
        overwrite=bool(tool_input.get("overwrite", False)),
    )
    return data, _format_workspace_operation_summary(data)


def _execute_copy_tool(tool_input: Mapping[str, object]) -> tuple[dict[str, object], str]:
    source_path = _normalize_rel_path(_normalize_optional_text(tool_input.get("source_path")))
    target_path = _normalize_rel_path(_normalize_optional_text(tool_input.get("target_path")))
    data = copy_workspace_path(
        source_path,
        target_path,
        overwrite=bool(tool_input.get("overwrite", False)),
        recursive=bool(tool_input.get("recursive", False)),
    )
    return data, _format_workspace_operation_summary(data)


def _execute_delete_tool(tool_input: Mapping[str, object]) -> tuple[dict[str, object], str]:
    rel_path = _normalize_rel_path(_normalize_optional_text(tool_input.get("rel_path")))
    data = delete_workspace_path(
        rel_path,
        recursive=bool(tool_input.get("recursive", False)),
    )
    return data, _format_workspace_operation_summary(data)


def _execute_search_tool(tool_input: Mapping[str, object]) -> tuple[dict[str, object], str]:
    query = _normalize_optional_text(tool_input.get("query")) or ""
    rel_path = _normalize_rel_path(_normalize_optional_text(tool_input.get("rel_path")))
    data = search_workspace_text(
        query,
        rel_path=rel_path,
        recursive=bool(tool_input.get("recursive", True)),
        max_matches=int(tool_input.get("max_matches") or 20),
        max_chars=int(tool_input.get("max_chars") or 240),
    )
    return data, _format_workspace_search_summary(data)


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
    WORKSPACE_TOOL_NAME_MOVE: WorkspaceToolDefinition(
        name=WORKSPACE_TOOL_NAME_MOVE,
        title="移动或重命名工作区路径",
        description="在受控 workspace 内移动或重命名文件/目录。",
        category=WORKSPACE_TOOL_CATEGORY_EXECUTION,
        output_kind=WORKSPACE_TOOL_OUTPUT_KIND_FILE_OPERATION,
        input_keys=("source_path", "target_path", "overwrite"),
        executor=_execute_move_tool,
    ),
    WORKSPACE_TOOL_NAME_COPY: WorkspaceToolDefinition(
        name=WORKSPACE_TOOL_NAME_COPY,
        title="复制工作区路径",
        description="在受控 workspace 内复制文件；复制目录时必须显式 recursive=true。",
        category=WORKSPACE_TOOL_CATEGORY_EXECUTION,
        output_kind=WORKSPACE_TOOL_OUTPUT_KIND_FILE_OPERATION,
        input_keys=("source_path", "target_path", "overwrite", "recursive"),
        executor=_execute_copy_tool,
    ),
    WORKSPACE_TOOL_NAME_DELETE: WorkspaceToolDefinition(
        name=WORKSPACE_TOOL_NAME_DELETE,
        title="删除工作区路径",
        description="在受控 workspace 内删除文件；删除目录时必须显式 recursive=true。",
        category=WORKSPACE_TOOL_CATEGORY_EXECUTION,
        output_kind=WORKSPACE_TOOL_OUTPUT_KIND_FILE_OPERATION,
        input_keys=("rel_path", "recursive"),
        executor=_execute_delete_tool,
    ),
    WORKSPACE_TOOL_NAME_SEARCH: WorkspaceToolDefinition(
        name=WORKSPACE_TOOL_NAME_SEARCH,
        title="搜索工作区文本",
        description="在受控 workspace 内搜索文本文件内容并返回裁剪后的匹配行。",
        category=WORKSPACE_TOOL_CATEGORY_CONTEXT,
        output_kind=WORKSPACE_TOOL_OUTPUT_KIND_TEXT_SEARCH,
        input_keys=("rel_path", "query", "recursive", "max_matches", "max_chars"),
        executor=_execute_search_tool,
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


def plan_workspace_tool(prompt: str) -> dict[str, object] | None:
    normalized_prompt = str(prompt or "").strip()
    path_candidates = _iter_prompt_path_candidates(normalized_prompt)
    matched_paths = _iter_existing_workspace_paths(normalized_prompt)

    if _looks_like_move_request(normalized_prompt):
        source_and_target = _source_and_target_candidates(normalized_prompt)
        if source_and_target is not None:
            source_path, target_path = source_and_target
            return _build_workspace_tool_plan(
                WORKSPACE_TOOL_NAME_MOVE,
                reason="Prompt asks to move or rename a workspace path.",
                terminal=True,
                source_path=source_path,
                target_path=target_path,
                overwrite=False,
            )

    if _looks_like_copy_request(normalized_prompt):
        source_and_target = _source_and_target_candidates(normalized_prompt)
        if source_and_target is not None:
            source_path, target_path = source_and_target
            recursive = _copy_recursive_from_prompt(normalized_prompt, source_path)
            return _build_workspace_tool_plan(
                WORKSPACE_TOOL_NAME_COPY,
                reason="Prompt asks to copy a workspace path.",
                terminal=True,
                source_path=source_path,
                target_path=target_path,
                overwrite=False,
                recursive=recursive,
            )

    if _looks_like_delete_request(normalized_prompt):
        rel_path = path_candidates[0]
        return _build_workspace_tool_plan(
            WORKSPACE_TOOL_NAME_DELETE,
            reason="Prompt asks to delete a workspace path.",
            terminal=True,
            rel_path=rel_path,
            recursive=_delete_recursive_from_prompt(normalized_prompt, rel_path),
        )

    if _looks_like_search_request(normalized_prompt):
        query = _extract_search_query(normalized_prompt)
        if query:
            return _build_workspace_tool_plan(
                WORKSPACE_TOOL_NAME_SEARCH,
                reason="Prompt asks to search workspace text.",
                terminal=True,
                rel_path=_search_root_from_prompt(normalized_prompt, matched_paths),
                query=query,
                recursive=True,
                max_matches=20,
            )

    if _looks_like_text_file_write_request(normalized_prompt):
        rel_path = _first_text_file_candidate(normalized_prompt)
        content = _extract_requested_text_content(normalized_prompt, rel_path=rel_path)
        # If no explicit file path and no content, try to infer from code language context
        if not rel_path:
            inferred_path = _infer_code_file_path(normalized_prompt)
            if inferred_path != "code.txt":
                rel_path = inferred_path
            else:
                rel_path = DEFAULT_WRITE_TEXT_REL_PATH
        if not content:
            lang = _detect_code_language(normalized_prompt)
            if lang:
                lang_hint = lang.lstrip(".")
                content = _generate_code_via_llm(normalized_prompt, lang_hint)
        reason = "Prompt asks to create or write a file."
        if not content:
            reason = "Prompt asks to create or write a file (no content detected; LLM generation attempted)."
        return _build_workspace_tool_plan(
            WORKSPACE_TOOL_NAME_WRITE,
            reason=reason,
            terminal=True,
            rel_path=rel_path,
            content=content,
            overwrite=False,
            target_location=_target_location_from_prompt(normalized_prompt),
        )

    if _contains_keyword(normalized_prompt, WORKSPACE_TOOL_TEST_KEYWORDS):
        target_paths = [rel_path for rel_path, _ in matched_paths]
        if not target_paths:
            target_paths = path_candidates
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

    if _contains_keyword(normalized_prompt, WORKSPACE_TOOL_READ_KEYWORDS) and path_candidates:
        return _build_workspace_tool_plan(
            WORKSPACE_TOOL_NAME_READ,
            reason="Prompt asks to read a workspace path.",
            terminal=_looks_like_pure_read_request(normalized_prompt),
            rel_path=path_candidates[0],
        )

    if _contains_keyword(normalized_prompt, WORKSPACE_TOOL_LIST_KEYWORDS):
        matched_dir = _first_matching_path(matched_paths, want_file=False)
        rel_path = matched_dir or (path_candidates[0] if path_candidates else ".")
        return _build_workspace_tool_plan(
            WORKSPACE_TOOL_NAME_LIST,
            reason="Prompt asks for workspace structure.",
            terminal=_looks_like_pure_list_request(normalized_prompt),
            rel_path=rel_path,
            recursive=False,
            max_entries=DEFAULT_WORKSPACE_OVERVIEW_ENTRY_LIMIT,
        )

    # Codegen fallback: if it looks like a coding task, let routing use run.create
    if _looks_like_codegen_task(normalized_prompt):
        return None

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
        failure_summary = _workspace_tool_failure_summary(tool_name, tool_input, exc)
        return WorkspaceToolExecutionResult(
            tool_name=tool_name,
            tool_input=tool_input,
            ok=False,
            reason=reason,
            tool_category=tool_definition.category,
            tool_output_kind=tool_definition.output_kind,
            tool_error_code=WORKSPACE_TOOL_ERROR_EXECUTION_FAILED,
            tool_descriptor=WorkspaceToolDescriptor.from_value(tool_descriptor),
            summary=failure_summary,
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
    if output_kind == WORKSPACE_TOOL_OUTPUT_KIND_FILE_OPERATION:
        return _format_file_operation_for_user(data)
    if output_kind == WORKSPACE_TOOL_OUTPUT_KIND_TEXT_SEARCH:
        return _format_search_result_for_user(data)
    return None
