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


def is_excluded_path(path: Path) -> bool:
    """检查路径是否在排除列表中

    Args:
        path: 要检查的路径（Path 对象）

    Returns:
        True 表示路径被排除，False 表示允许访问
    """
    # 检查路径中的目录名
    for part in path.parts:
        if part in DEFAULT_EXCLUDED_DIRS:
            return True

    # 检查文件名
    name = path.name
    if name in DEFAULT_EXCLUDED_FILES:
        return True

    # 检查 .env.* 模式
    if name.startswith(".env"):
        return True

    return False


def get_workspace_dir() -> Path:
    return settings.workspace_dir.resolve()


def get_effective_workspace_dir() -> Path:
    """返回实际工作目录

    - 配置了 PROJECT_ROOT 时返回项目目录
    - 否则返回默认 workspace 目录
    """
    if settings.accessible_project_root:
        return settings.accessible_project_root
    return get_workspace_dir()


def check_write_permission() -> None:
    """检查是否有写入权限

    Raises:
        PermissionError: 项目只读模式下尝试写入
    """
    if settings.accessible_project_root and not settings.project_write_enabled:
        raise PermissionError(
            "当前项目配置为只读模式。\n"
            "如需允许 AI 修改代码，请在 .env 中设置：\n"
            "PROJECT_WRITE_ENABLED=true"
        )


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
    """解析相对路径到绝对路径（支持项目目录）

    Args:
        rel_path: 相对路径

    Returns:
        解析后的绝对路径

    Raises:
        PermissionError: 路径超出允许范围或在排除列表中
    """
    base_dir = get_effective_workspace_dir()

    # 如果使用默认 workspace，确保目录存在
    if not settings.accessible_project_root:
        ensure_workspace_dirs()

    target = (base_dir / rel_path).resolve()

    # 安全检查：确保路径在允许范围内
    try:
        target.relative_to(base_dir)
    except ValueError as exc:
        raise PermissionError("路径超出允许访问范围") from exc

    # 排除检查
    if is_excluded_path(target):
        raise PermissionError(
            "该路径被安全策略排除（敏感目录或文件），不允许访问。"
        )

    return target


def _to_workspace_rel_path(target: Path) -> str:
    return str(target.relative_to(get_effective_workspace_dir())).replace("\\", "/")


def safe_write_file(rel_path: str, content: str) -> str:
    """安全写入文件到工作区

    Args:
        rel_path: 相对路径
        content: 文件内容

    Returns:
        写入文件的绝对路径

    Raises:
        PermissionError: 无写入权限或路径在排除列表中
    """
    # 写入权限检查
    check_write_permission()

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
