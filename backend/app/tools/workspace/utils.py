from ..safe_fs import get_workspace_dir, resolve_workspace_path
from ...core.text_utils import clip_text


def normalize_rel_path(rel_path: str | None) -> str:
    normalized = str(rel_path or ".").strip()
    return normalized or "."


def normalize_positive_limit(value: int | None, *, default: int) -> int:
    if value is None or value <= 0:
        return default
    return value


def resolve_workspace_rel_path(rel_path: str | None) -> str:
    normalized = normalize_rel_path(rel_path)
    target = resolve_workspace_path(normalized)
    return str(target.relative_to(get_workspace_dir())).replace("\\", "/")


def clip_output(text: str | None, *, limit: int) -> tuple[str, int, bool]:
    clipped, total_length, truncated = clip_text(text, limit=limit)
    return clipped or "", total_length, truncated


def normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_optional_bool(value: object) -> bool | None:
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


def contains_keyword(prompt: str, keywords: tuple[str, ...]) -> bool:
    normalized_prompt = prompt.lower()
    return any(keyword.lower() in normalized_prompt for keyword in keywords)

