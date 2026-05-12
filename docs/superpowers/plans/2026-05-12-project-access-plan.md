# 真实项目访问功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AI 桌宠能够访问和修改用户真实项目代码，同时保护敏感文件。

**Architecture:** 扩展现有 `safe_fs.py` 和 `config.py`，新增 `PROJECT_ROOT` 配置项和排除列表机制，通过统一路径解析层支持真实项目访问。

**Tech Stack:** Python 3.11+, FastAPI, pytest

---

## 文件结构

| 文件 | 变更类型 | 职责 |
|------|---------|------|
| `backend/app/core/config.py` | 修改 | 新增 `project_root` 和 `project_write_enabled` 配置 |
| `backend/app/tools/safe_fs.py` | 修改 | 新增排除列表、路径解析函数、写入权限检查 |
| `backend/.env.example` | 修改 | 新增配置示例 |
| `backend/tests/tools/test_safe_fs.py` | 修改 | 新增排除路径、权限检查测试 |

---

### Task 1: 添加排除列表常量

**Files:**
- Modify: `backend/app/tools/safe_fs.py` (文件开头)

- [ ] **Step 1: 在 safe_fs.py 开头添加排除列表常量**

在现有 import 语句之后，`get_workspace_dir()` 函数之前添加：

```python
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
```

- [ ] **Step 2: 提交更改**

```bash
git add backend/app/tools/safe_fs.py
git commit -m "feat: add default excluded dirs and files constants

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 添加排除路径检查函数

**Files:**
- Modify: `backend/app/tools/safe_fs.py`
- Modify: `backend/tests/tools/test_safe_fs.py`

- [ ] **Step 1: 编写排除路径检查函数的测试**

在 `backend/tests/tools/test_safe_fs.py` 末尾添加：

```python
from backend.app.tools.safe_fs import is_excluded_path


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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_is_excluded_path_detects_excluded_dirs -v
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_is_excluded_path_detects_excluded_files -v
```

Expected: FAIL - `is_excluded_path` not defined

- [ ] **Step 3: 实现 is_excluded_path 函数**

在 `backend/app/tools/safe_fs.py` 中，排除列表常量之后添加：

```python
from pathlib import Path


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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_is_excluded_path_detects_excluded_dirs -v
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_is_excluded_path_detects_excluded_files -v
```

Expected: PASS

- [ ] **Step 5: 提交更改**

```bash
git add backend/app/tools/safe_fs.py backend/tests/tools/test_safe_fs.py
git commit -m "feat: add is_excluded_path function for security check

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 添加配置项到 Settings 类

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: 在 config.py 中添加项目根目录配置**

在 `Settings.__init__` 方法中，找到 `self.llm_fallback_timeout_seconds` 赋值之后，添加：

```python
        # 项目访问配置
        self.project_root = self._resolve_project_root()
        self.project_write_enabled = _read_bool_env("PROJECT_WRITE_ENABLED", default=False)
```

在 `Settings` 类中添加新方法：

```python
    def _resolve_project_root(self) -> "Path | None":
        """解析并验证 PROJECT_ROOT 配置"""
        raw = _read_env("PROJECT_ROOT")
        if not raw:
            return None
        from pathlib import Path
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            logger.warning("PROJECT_ROOT does not exist: %s", path)
            return None
        if not path.is_dir():
            logger.warning("PROJECT_ROOT is not a directory: %s", path)
            return None
        return path
```

- [ ] **Step 2: 在 .env.example 中添加配置示例**

在 `backend/.env.example` 文件末尾添加：

```env

# Project Access Configuration
# ----------------------------
# 项目根目录（可选，不配置则使用默认 workspace 目录）
# 示例: PROJECT_ROOT=E:/my-project
PROJECT_ROOT=

# 是否允许写入项目文件（默认 false，只读模式）
# 启用后 AI 可修改项目代码
PROJECT_WRITE_ENABLED=false
```

- [ ] **Step 3: 提交更改**

```bash
git add backend/app/core/config.py backend/.env.example
git commit -m "feat: add PROJECT_ROOT and PROJECT_WRITE_ENABLED config

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 添加有效工作目录解析函数

**Files:**
- Modify: `backend/app/tools/safe_fs.py`
- Modify: `backend/tests/tools/test_safe_fs.py`

- [ ] **Step 1: 编写 get_effective_workspace_dir 测试**

在 `backend/tests/tools/test_safe_fs.py` 中添加：

```python
import os
from pathlib import Path
from unittest.mock import patch

from backend.app.tools.safe_fs import get_effective_workspace_dir


def test_get_effective_workspace_dir_returns_default_when_no_project_root():
    """未配置 PROJECT_ROOT 时返回默认 workspace"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.project_root = None
        result = get_effective_workspace_dir()
        assert result.name == "workspace"


def test_get_effective_workspace_dir_returns_project_root_when_configured():
    """配置 PROJECT_ROOT 时返回项目目录"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.project_root = Path("/tmp/test-project")
        result = get_effective_workspace_dir()
        assert result == Path("/tmp/test-project")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_get_effective_workspace_dir_returns_default_when_no_project_root -v
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_get_effective_workspace_dir_returns_project_root_when_configured -v
```

Expected: FAIL - `get_effective_workspace_dir` not defined

- [ ] **Step 3: 实现 get_effective_workspace_dir 函数**

在 `backend/app/tools/safe_fs.py` 中，`get_workspace_dir()` 函数之后添加：

```python
def get_effective_workspace_dir() -> Path:
    """返回实际工作目录

    - 配置了 PROJECT_ROOT 时返回项目目录
    - 否则返回默认 workspace 目录
    """
    if settings.project_root:
        return settings.project_root
    return get_workspace_dir()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_get_effective_workspace_dir_returns_default_when_no_project_root -v
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_get_effective_workspace_dir_returns_project_root_when_configured -v
```

Expected: PASS

- [ ] **Step 5: 提交更改**

```bash
git add backend/app/tools/safe_fs.py backend/tests/tools/test_safe_fs.py
git commit -m "feat: add get_effective_workspace_dir function

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 添加写入权限检查函数

**Files:**
- Modify: `backend/app/tools/safe_fs.py`
- Modify: `backend/tests/tools/test_safe_fs.py`

- [ ] **Step 1: 编写 check_write_permission 测试**

在 `backend/tests/tools/test_safe_fs.py` 中添加：

```python
from backend.app.tools.safe_fs import check_write_permission


def test_check_write_permission_raises_when_project_readonly():
    """项目只读模式下写入应抛出异常"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.project_root = Path("/tmp/test-project")
        mock_settings.project_write_enabled = False
        
        with pytest.raises(PermissionError) as exc_info:
            check_write_permission()
        
        assert "只读模式" in str(exc_info.value)


def test_check_write_permission_passes_when_write_enabled():
    """启用写入权限时检查通过"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.project_root = Path("/tmp/test-project")
        mock_settings.project_write_enabled = True
        
        # 不应抛出异常
        check_write_permission()


def test_check_write_permission_passes_when_no_project_root():
    """未配置项目目录时允许写入（默认 workspace）"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.project_root = None
        mock_settings.project_write_enabled = False
        
        # 不应抛出异常
        check_write_permission()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_check_write_permission_raises_when_project_readonly -v
```

Expected: FAIL - `check_write_permission` not defined

- [ ] **Step 3: 实现 check_write_permission 函数**

在 `backend/app/tools/safe_fs.py` 中添加：

```python
def check_write_permission() -> None:
    """检查是否有写入权限
    
    Raises:
        PermissionError: 项目只读模式下尝试写入
    """
    if settings.project_root and not settings.project_write_enabled:
        raise PermissionError(
            "当前项目配置为只读模式。\n"
            "如需允许 AI 修改代码，请在 .env 中设置：\n"
            "PROJECT_WRITE_ENABLED=true"
        )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_check_write_permission_raises_when_project_readonly -v
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_check_write_permission_passes_when_write_enabled -v
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_check_write_permission_passes_when_no_project_root -v
```

Expected: PASS

- [ ] **Step 5: 提交更改**

```bash
git add backend/app/tools/safe_fs.py backend/tests/tools/test_safe_fs.py
git commit -m "feat: add check_write_permission function

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: 修改路径解析函数支持项目目录和排除检查

**Files:**
- Modify: `backend/app/tools/safe_fs.py`
- Modify: `backend/tests/tools/test_safe_fs.py`

- [ ] **Step 1: 编写 resolve_workspace_path 排除检查测试**

在 `backend/tests/tools/test_safe_fs.py` 中添加：

```python
def test_resolve_workspace_path_blocks_excluded_dirs():
    """排除目录应被阻止访问"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.project_root = None
        
        # .git 目录应被阻止
        with pytest.raises(PermissionError) as exc_info:
            resolve_workspace_path(".git/config")
        assert "排除" in str(exc_info.value)
        
        # node_modules 应被阻止
        with pytest.raises(PermissionError):
            resolve_workspace_path("node_modules/package/index.js")


def test_resolve_workspace_path_blocks_excluded_files():
    """排除文件应被阻止访问"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.project_root = None
        
        # .env 文件应被阻止
        with pytest.raises(PermissionError) as exc_info:
            resolve_workspace_path(".env")
        assert "排除" in str(exc_info.value)
        
        # credentials.json 应被阻止
        with pytest.raises(PermissionError):
            resolve_workspace_path("credentials.json")


def test_resolve_workspace_path_allows_normal_paths():
    """正常路径应允许访问"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.project_root = None
        
        # 正常文件路径应正常解析
        result = resolve_workspace_path("src/main.py")
        assert result.name == "main.py"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_resolve_workspace_path_blocks_excluded_dirs -v
```

Expected: FAIL - 排除路径未被阻止

- [ ] **Step 3: 修改 resolve_workspace_path 函数**

找到 `backend/app/tools/safe_fs.py` 中的 `resolve_workspace_path` 函数，修改为：

```python
def resolve_workspace_path(rel_path: str) -> Path:
    """解析相对路径到绝对路径（支持项目目录）
    
    Args:
        rel_path: 相对路径
    
    Returns:
        解析后的绝对路径
    
    Raises:
        PermissionError: 路径超出允许范围或在排除列表中
    """
    ensure_workspace_dirs()
    base_dir = get_effective_workspace_dir()
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_resolve_workspace_path_blocks_excluded_dirs -v
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_resolve_workspace_path_blocks_excluded_files -v
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_resolve_workspace_path_allows_normal_paths -v
```

Expected: PASS

- [ ] **Step 5: 提交更改**

```bash
git add backend/app/tools/safe_fs.py backend/tests/tools/test_safe_fs.py
git commit -m "feat: integrate exclusion check into resolve_workspace_path

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: 修改写入函数添加权限检查

**Files:**
- Modify: `backend/app/tools/safe_fs.py`
- Modify: `backend/tests/tools/test_safe_fs.py`

- [ ] **Step 1: 编写 safe_write_file 权限检查测试**

在 `backend/tests/tools/test_safe_fs.py` 中添加：

```python
def test_safe_write_file_blocked_when_readonly():
    """项目只读模式下写入应被阻止"""
    with patch("backend.app.tools.safe_fs.settings") as mock_settings:
        mock_settings.project_root = Path("/tmp/test-project")
        mock_settings.project_write_enabled = False
        
        with pytest.raises(PermissionError) as exc_info:
            safe_write_file("test.txt", "content")
        assert "只读模式" in str(exc_info.value)


def test_safe_write_file_allowed_when_write_enabled():
    """启用写入权限时写入成功"""
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("backend.app.tools.safe_fs.settings") as mock_settings:
            mock_settings.project_root = Path(tmpdir)
            mock_settings.project_write_enabled = True
            
            result = safe_write_file("test.txt", "content")
            assert Path(result).exists()
            assert Path(result).read_text() == "content"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_safe_write_file_blocked_when_readonly -v
```

Expected: FAIL - 写入未被阻止

- [ ] **Step 3: 修改 safe_write_file 函数**

找到 `backend/app/tools/safe_fs.py` 中的 `safe_write_file` 函数，修改为：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_safe_write_file_blocked_when_readonly -v
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py::test_safe_write_file_allowed_when_write_enabled -v
```

Expected: PASS

- [ ] **Step 5: 提交更改**

```bash
git add backend/app/tools/safe_fs.py backend/tests/tools/test_safe_fs.py
git commit -m "feat: add write permission check to safe_write_file

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: 运行完整测试套件

**Files:**
- None

- [ ] **Step 1: 运行所有 safe_fs 相关测试**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/tools/test_safe_fs.py -v
```

Expected: All tests PASS

- [ ] **Step 2: 运行所有后端测试确保无回归**

```bash
cd E:/artificialIntelligence/course-of-Introduction-to-AI
.venv/Scripts/python -m pytest backend/tests/ -v
```

Expected: All tests PASS

---

### Task 9: 更新文档和最终提交

**Files:**
- Modify: `backend/README.md`

- [ ] **Step 1: 在 backend/README.md 中添加项目访问配置说明**

找到适当位置（如配置章节）添加：

```markdown
### Project Access

By default, the AI can only access `backend/workspace/` directory. To allow access to your real project:

```env
# .env
PROJECT_ROOT=/path/to/your/project
PROJECT_WRITE_ENABLED=true
```

**Security Notes:**
- Without `PROJECT_WRITE_ENABLED=true`, the project is read-only
- Sensitive paths are automatically excluded: `.git`, `.env`, `node_modules`, etc.
- Files like `credentials.json`, `.env.local` are protected from access
```

- [ ] **Step 2: 提交文档更新**

```bash
git add backend/README.md
git commit -m "docs: add project access configuration guide

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

- [ ] **Step 3: 创建总结性提交（可选）**

```bash
git log --oneline -10
```

---

## 实现完成检查清单

- [ ] 所有测试通过
- [ ] `PROJECT_ROOT` 配置生效
- [ ] `PROJECT_WRITE_ENABLED` 写入控制生效
- [ ] 排除路径正确阻止访问
- [ ] 向后兼容：未配置时行为不变
- [ ] 文档已更新
