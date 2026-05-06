from pathlib import Path

from ..core.config import settings


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


def safe_write_file(rel_path: str, content: str) -> str:
    target = resolve_workspace_path(rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)


def safe_read_file(rel_path: str) -> str:
    target = resolve_workspace_path(rel_path)
    return target.read_text(encoding="utf-8")


def safe_list_files(rel_path: str = ".", recursive: bool = False) -> list[str]:
    target = resolve_workspace_path(rel_path)
    workspace_dir = get_workspace_dir()
    if not target.exists():
        return []
    if target.is_file():
        return [str(target.relative_to(workspace_dir)).replace("\\", "/")]

    pattern = "**/*" if recursive else "*"
    files: list[str] = []
    for path in target.glob(pattern):
        if path.is_file():
            files.append(str(path.relative_to(workspace_dir)).replace("\\", "/"))
    files.sort()
    return files
