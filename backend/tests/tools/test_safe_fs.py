import pytest
from pathlib import Path
from unittest.mock import patch

from backend.app.tools.safe_fs import (
    get_effective_workspace_dir,
    is_excluded_path,
    resolve_workspace_path,
    safe_list_entries,
    safe_list_files,
    safe_read_file,
    safe_write_file,
)


def test_safe_fs_can_write_read_and_list_files():
    safe_write_file("notes/demo.txt", "hello")
    safe_write_file("notes/nested/info.txt", "world")

    assert safe_read_file("notes/demo.txt") == "hello"
    assert safe_list_entries("notes", recursive=True) == [
        {"path": "notes/demo.txt", "kind": "file"},
        {"path": "notes/nested", "kind": "dir"},
        {"path": "notes/nested/info.txt", "kind": "file"},
    ]
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


def test_is_excluded_path_detects_excluded_dirs():
    """测试排除目录检测"""
    # .git 目录应被排除
    assert is_excluded_path(Path("project/.git/config")) is True
    assert is_excluded_path(Path("project/.git")) is True

    # node_modules 应被排除
    assert is_excluded_path(Path("project/node_modules/package/index.js")) is True

    # 正常目录不应被排除
    assert is_excluded_path(Path("project/src/main.py")) is False


def test_is_excluded_path_detects_excluded_files():
    """测试排除文件检测"""
    # .env 文件应被排除
    assert is_excluded_path(Path("project/.env")) is True
    assert is_excluded_path(Path("project/.env.local")) is True

    # credentials.json 应被排除
    assert is_excluded_path(Path("project/credentials.json")) is True

    # 正常文件不应被排除
    assert is_excluded_path(Path("project/config.json")) is False
    assert is_excluded_path(Path("project/src/main.py")) is False


def test_get_effective_workspace_dir_returns_default_when_no_project_root():
    """未配置 PROJECT_ROOT 时返回默认 workspace"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.accessible_project_root = None
        mock_settings.workspace_dir.resolve.return_value = Path("/default/workspace")
        result = get_effective_workspace_dir()
        assert result == Path("/default/workspace")


def test_get_effective_workspace_dir_returns_project_root_when_configured():
    """配置 PROJECT_ROOT 时返回项目目录"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.accessible_project_root = Path("/tmp/test-project")
        result = get_effective_workspace_dir()
        assert result == Path("/tmp/test-project")


def test_check_write_permission_raises_when_project_readonly():
    """项目只读模式下写入应抛出异常"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.accessible_project_root = Path("/tmp/test-project")
        mock_settings.project_write_enabled = False

        with pytest.raises(PermissionError) as exc_info:
            from backend.app.tools.safe_fs import check_write_permission
            check_write_permission()

        assert "只读模式" in str(exc_info.value)


def test_check_write_permission_passes_when_write_enabled():
    """启用写入权限时检查通过"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.accessible_project_root = Path("/tmp/test-project")
        mock_settings.project_write_enabled = True

        from backend.app.tools.safe_fs import check_write_permission
        # 不应抛出异常
        check_write_permission()


def test_check_write_permission_passes_when_no_project_root():
    """未配置项目目录时允许写入（默认 workspace）"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.accessible_project_root = None
        mock_settings.project_write_enabled = False

        from backend.app.tools.safe_fs import check_write_permission
        # 不应抛出异常
        check_write_permission()


def test_resolve_workspace_path_blocks_excluded_dirs():
    """排除目录应被阻止访问"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("backend.app.tools.safe_fs.settings") as mock_settings:
            mock_settings.accessible_project_root = Path(tmpdir)
            mock_settings.workspace_dir = Path(tmpdir)  # 添加这个以避免 ensure_workspace_dirs 出错

            # .git 目录应被阻止
            with pytest.raises(PermissionError) as exc_info:
                resolve_workspace_path(".git/config")
            assert "排除" in str(exc_info.value)

            # node_modules 应被阻止
            with pytest.raises(PermissionError):
                resolve_workspace_path("node_modules/package/index.js")


def test_resolve_workspace_path_blocks_excluded_files():
    """排除文件应被阻止访问"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("backend.app.tools.safe_fs.settings") as mock_settings:
            mock_settings.accessible_project_root = Path(tmpdir)
            mock_settings.workspace_dir = Path(tmpdir)

            # .env 文件应被阻止
            with pytest.raises(PermissionError) as exc_info:
                resolve_workspace_path(".env")
            assert "排除" in str(exc_info.value)

            # credentials.json 应被阻止
            with pytest.raises(PermissionError):
                resolve_workspace_path("credentials.json")


def test_resolve_workspace_path_allows_normal_paths():
    """正常路径应允许访问"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("backend.app.tools.safe_fs.settings") as mock_settings:
            mock_settings.accessible_project_root = Path(tmpdir)
            mock_settings.workspace_dir = Path(tmpdir)

            # 正常文件路径应正常解析
            result = resolve_workspace_path("src/main.py")
            assert result.name == "main.py"
