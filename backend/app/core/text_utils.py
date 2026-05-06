def normalize_whitespace(text: str) -> str:
    return " ".join(text.strip().split())


def build_preview(
    text: str,
    *,
    limit: int,
    collapse_whitespace: bool = True,
) -> str:
    normalized = normalize_whitespace(text) if collapse_whitespace else text.strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def clip_text(text: str | None, *, limit: int) -> tuple[str | None, int, bool]:
    raw = text or ""
    total_length = len(raw)
    if total_length <= limit:
        return (raw or None), total_length, False
    return raw[:limit], total_length, True
