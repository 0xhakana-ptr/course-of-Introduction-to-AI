import re

from ...tools.workspace_tools import (
    WORKSPACE_TOOL_COPY_KEYWORDS,
    WORKSPACE_TOOL_DELETE_KEYWORDS,
    WORKSPACE_TOOL_NAME_COPY,
    WORKSPACE_TOOL_SEARCH_KEYWORDS,
)
from ..file import (
    build_copy_target_path,
    prompt_requests_contextual_copy_without_target,
    resolve_prompt_file_references,
)


MULTI_STEP_CONNECTORS = (
    "然后",
    "之后",
    "随后",
    "再",
    "并",
    "并且",
    "then",
)
READ_CONFIRMATION_KEYWORDS = (
    "读取",
    "读一下",
    "读出来",
    "查看",
    "确认内容",
    "确认一下",
    "read",
    "show",
    "preview",
)
SEARCH_RESULT_REFERENCE_KEYWORDS = (
    "第一个结果",
    "第一条结果",
    "搜索结果",
    "查找结果",
    "刚才搜索到的文件",
    "first result",
    "search result",
)
COPY_TARGET_AFTER_SEARCH_PATTERN = re.compile(
    r"(?:复制到|拷贝到|备份到|copy\s+to)\s*[`\"'“”‘’]?([^`\"'“”‘’，。,；;\n]+)",
    re.IGNORECASE,
)


def _normalize_text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def copy_action_from_file_context(
    prompt: str,
    file_context: object,
) -> tuple[str, dict[str, object], dict[str, object]] | None:
    if not prompt_requests_contextual_copy_without_target(prompt):
        return None
    _, source_path = resolve_prompt_file_references(prompt, file_context)
    if not source_path:
        return None

    target_path = build_copy_target_path(source_path)
    action_input = {
        "source_path": source_path,
        "target_path": target_path,
        "overwrite": False,
        "recursive": False,
    }
    return (
        "workspace.copy",
        action_input,
        {
            "tool_name": WORKSPACE_TOOL_NAME_COPY,
            "tool_input": dict(action_input),
            "reason": "Prompt asks to copy the recent file without an explicit target path.",
            "terminal": True,
            "file_context_reference": source_path,
            "contextual_prompt": prompt,
        },
    )


def prompt_references_search_result(prompt: str) -> bool:
    text = str(prompt or "").strip().lower()
    return any(keyword.lower() in text for keyword in SEARCH_RESULT_REFERENCE_KEYWORDS)


def initial_search_prompt_from_multistep(prompt: str) -> str | None:
    if not prompt_references_search_result(prompt):
        return None
    lowered_prompt = prompt.lower()
    if not any(keyword.lower() in lowered_prompt for keyword in WORKSPACE_TOOL_SEARCH_KEYWORDS):
        return None

    split_points = [
        index
        for connector in MULTI_STEP_CONNECTORS
        if (index := lowered_prompt.find(connector.lower())) > 0
    ]
    if not split_points:
        return None
    initial_prompt = prompt[: min(split_points)].strip(" ，,。；;")
    return initial_prompt or None


def prompt_requests_read_confirmation(prompt: str) -> bool:
    text = str(prompt or "").strip().lower()
    return (
        any(connector in text for connector in MULTI_STEP_CONNECTORS)
        and any(keyword in text for keyword in READ_CONFIRMATION_KEYWORDS)
    )


def workspace_followup_queue(
    *,
    prompt: str,
    action_name: str,
    action_input: dict[str, object],
) -> list[dict[str, object]]:
    rel_path = _normalize_text(action_input.get("rel_path"))
    if (
        action_name != "workspace.write"
        or not rel_path
        or not prompt_requests_read_confirmation(prompt)
    ):
        return []

    return [
        {
            "action_name": "workspace.read",
            "action_input": {"rel_path": rel_path},
        }
    ]


def first_search_match_path(action_result: dict[str, object]) -> str | None:
    data = action_result.get("data")
    if not isinstance(data, dict):
        return None
    matches = data.get("matches")
    if not isinstance(matches, list) or not matches:
        return None
    first_match = matches[0]
    if not isinstance(first_match, dict):
        return None
    return _normalize_text(first_match.get("path")) or None


def copy_target_from_search_followup(prompt: str, source_path: str) -> str:
    matched = COPY_TARGET_AFTER_SEARCH_PATTERN.search(prompt)
    if matched is None:
        return build_copy_target_path(source_path)
    return matched.group(1).strip().strip("`\"'“”‘’") or build_copy_target_path(source_path)


def workspace_dynamic_followup_queue(
    *,
    prompt: str,
    action_result: dict[str, object],
) -> list[dict[str, object]]:
    action_name = _normalize_text(action_result.get("action_name"))
    if action_name != "workspace.search" or not bool(action_result.get("ok")):
        return []
    if not prompt_references_search_result(prompt):
        return []

    source_path = first_search_match_path(action_result)
    if not source_path:
        return []

    lowered_prompt = prompt.lower()
    if any(keyword.lower() in lowered_prompt for keyword in WORKSPACE_TOOL_COPY_KEYWORDS):
        return [
            {
                "action_name": "workspace.copy",
                "action_input": {
                    "source_path": source_path,
                    "target_path": copy_target_from_search_followup(prompt, source_path),
                    "overwrite": False,
                    "recursive": False,
                },
            }
        ]
    if any(keyword.lower() in lowered_prompt for keyword in WORKSPACE_TOOL_DELETE_KEYWORDS):
        return [
            {
                "action_name": "workspace.delete",
                "action_input": {"rel_path": source_path, "recursive": False},
            }
        ]
    if any(keyword.lower() in lowered_prompt for keyword in READ_CONFIRMATION_KEYWORDS):
        return [
            {
                "action_name": "workspace.read",
                "action_input": {"rel_path": source_path},
            }
        ]
    return []
