from backend.app.core.text_utils import build_preview, clip_text


def test_build_preview_collapses_whitespace_by_default():
    preview = build_preview("hello   world\n\nfrom backend", limit=100)

    assert preview == "hello world from backend"


def test_build_preview_can_preserve_internal_whitespace():
    preview = build_preview("line 1\nline 2", limit=100, collapse_whitespace=False)

    assert preview == "line 1\nline 2"


def test_clip_text_returns_lengths_and_truncation_flags():
    clipped, total_length, truncated = clip_text("abcdef", limit=4)

    assert clipped == "abcd"
    assert total_length == 6
    assert truncated is True
