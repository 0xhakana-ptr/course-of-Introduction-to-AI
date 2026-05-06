from pathlib import Path

from core.config import settings


WORKSPACE_DIR = settings.workspace_dir.resolve()


def ensure_workspace_dirs() -> None:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    settings.runs_dir.mkdir(parents=True, exist_ok=True)


def assert_within_workspace(target: Path) -> None:
    try:
        target.relative_to(WORKSPACE_DIR)
    except ValueError as exc:
        raise PermissionError("路径超出 workspace 范围") from exc


def resolve_workspace_path(rel_path: str) -> Path:
    ensure_workspace_dirs()
    target = (WORKSPACE_DIR / rel_path).resolve()
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
    if not target.exists():
        return []
    if target.is_file():
        return [str(target.relative_to(WORKSPACE_DIR)).replace("\\", "/")]

    pattern = "**/*" if recursive else "*"
    files: list[str] = []
    for path in target.glob(pattern):
        if path.is_file():
            files.append(str(path.relative_to(WORKSPACE_DIR)).replace("\\", "/"))
    files.sort()
    return files