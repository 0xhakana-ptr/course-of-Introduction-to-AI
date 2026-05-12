from pathlib import Path

from ..core.config import settings


# 默认排除的目录
DEFAULT_EXCLUDED_DIRS = frozenset({
    # 版本控制
    ".git", ".svn", ".hg",
    # 依赖目录
    "node_modules", "__pycache__", ".venv", "venv", "env",
    # IDE 配置
    ".idea", ".vscode",
    # 构建输出
    "dist", "build", ".next", ".nuxt", "target",
})

# 默认排除的文件
DEFAULT_EXCLUDED_FILES = frozenset({
    # 环境变量
    ".env", ".env.local", ".env.development", ".env.production",
    # 凭证文件
    "credentials.json", "secrets.json", "secrets.yaml",
})


def get_workspace_dir() -> Path:
    return settings.workspace_dir.resolve()


def ensure_workspace_dirs() -> None:
    workspace_dir = get_workspace_dir()
    workspace_dir.mkdir(parents=True, exist_ok=True)
    settings.runs_dir.mkdir(parents=True, exist_ok=True)


def assert_within_workspace(target: Path) -> None:
    workspace_dir = get_workspace_dir()
    try:
        target.relative_to(workspace_dir)
    except ValueError as exc:
        raise PermissionError("路径超出 workspace 范围") from exc


def resolve_workspace_path(rel_path: str) -> Path:
    ensure_workspace_dirs()
    target = (get_workspace_dir() / rel_path).resolve()
    assert_within_workspace(target)
    return target


def _to_workspace_rel_path(target: Path) -> str:
    return str(target.relative_to(get_workspace_dir())).replace("\\", "/")


def safe_write_file(rel_path: str, content: str) -> str:
    target = resolve_workspace_path(rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)


def safe_read_file(rel_path: str) -> str:
    target = resolve_workspace_path(rel_path)
    return target.read_text(encoding="utf-8")


def safe_list_entries(
    rel_path: str = ".",
    *,
    recursive: bool = False,
    include_files: bool = True,
    include_dirs: bool = True,
) -> list[dict[str, str]]:
    target = resolve_workspace_path(rel_path)
    if not target.exists():
        return []
    if target.is_file():
        if not include_files:
            return []
        return [{"path": _to_workspace_rel_path(target), "kind": "file"}]

    pattern = "**/*" if recursive else "*"
    entries: list[dict[str, str]] = []
    for path in target.glob(pattern):
        if path.is_file() and include_files:
            entries.append({"path": _to_workspace_rel_path(path), "kind": "file"})
        elif path.is_dir() and include_dirs:
            entries.append({"path": _to_workspace_rel_path(path), "kind": "dir"})
    entries.sort(key=lambda item: (item["path"], item["kind"]))
    return entries


def safe_list_files(rel_path: str = ".", recursive: bool = False) -> list[str]:
    return [
        entry["path"]
        for entry in safe_list_entries(
            rel_path,
            recursive=recursive,
            include_files=True,
            include_dirs=False,
        )
    ]
