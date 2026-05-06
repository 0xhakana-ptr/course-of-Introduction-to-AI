import pytest

from backend.app.tools.safe_fs import (
    resolve_workspace_path,
    safe_list_files,
    safe_read_file,
    safe_write_file,
)


def test_safe_fs_can_write_read_and_list_files():
    safe_write_file("notes/demo.txt", "hello")
    safe_write_file("notes/nested/info.txt", "world")

    assert safe_read_file("notes/demo.txt") == "hello"
    assert safe_list_files("notes") == ["notes/demo.txt"]
    assert safe_list_files("notes", recursive=True) == [
        "notes/demo.txt",
        "notes/nested/info.txt",
    ]


def test_safe_fs_blocks_workspace_escape():
    with pytest.raises(PermissionError):
        resolve_workspace_path("../outside.txt")

    with pytest.raises(PermissionError):
        safe_write_file("../outside.txt", "blocked")
