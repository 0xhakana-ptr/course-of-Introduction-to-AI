# 真实项目访问功能设计

**日期:** 2026-05-12
**状态:** 待实现
**范围:** 让 AI 桌宠能够访问和修改用户真实项目代码

---

## 1. 概述

### 1.1 目标

打破现有 `backend/workspace/` 隔离，让 AI 能够：
- 读取用户真实项目中的代码文件
- 在授权情况下修改项目代码
- 保护敏感文件不被意外访问或修改

### 1.2 背景

当前限制：
- AI 只能操作 `backend/workspace/` 目录
- 无法访问用户实际开发的项目
- 无法参与真实的软件开发流程

### 1.3 范围

| 功能 | 包含 |
|------|------|
| 配置项目路径 | ✅ |
| 读取项目文件 | ✅ |
| 写入项目文件 | ✅（需显式启用） |
| 排除敏感路径 | ✅ |
| 执行命令/Git | ❌（后续迭代） |

---

## 2. 配置设计

### 2.1 环境变量

在 `backend/.env` 中新增：

```env
# 项目根目录（可选）
# 不配置时使用默认 workspace 目录
# 示例: PROJECT_ROOT=E:/my-project
PROJECT_ROOT=

# 是否允许写入项目文件
# 默认 false（只读模式）
# 启用后 AI 可修改项目代码
PROJECT_WRITE_ENABLED=false
```

### 2.2 配置类变更

文件: `backend/app/core/config.py`

```python
class Settings:
    def __init__(self) -> None:
        # ... existing code ...

        # 项目访问配置
        self.project_root = self._resolve_project_root()
        self.project_write_enabled = _read_bool_env(
            "PROJECT_WRITE_ENABLED", default=False
        )

    def _resolve_project_root(self) -> Path | None:
        """解析并验证 PROJECT_ROOT 配置"""
        raw = _read_env("PROJECT_ROOT")
        if not raw:
            return None
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            logger.warning("PROJECT_ROOT does not exist: %s", path)
            return None
        if not path.is_dir():
            logger.warning("PROJECT_ROOT is not a directory: %s", path)
            return None
        return path
```

---

## 3. 路径解析与安全

### 3.1 排除列表

文件: `backend/app/tools/safe_fs.py`

```python
# 默认排除的目录
DEFAULT_EXCLUDED_DIRS = frozenset({
    # 版本控制
    ".git", ".svn", ".hg",
    # 依赖目录
    "node_modules", "__pycache__", ".venv", "venv", "env",
    # IDE 配置
    ".idea", ".vscode", ".sublime-project",
    # 构建输出
    "dist", "build", ".next", ".nuxt", "target",
})

# 默认排除的文件模式
DEFAULT_EXCLUDED_FILES = frozenset({
    # 环境变量
    ".env", ".env.local", ".env.development", ".env.production",
    # 密钥文件
    "*.pem", "*.key", "*.p12",
    # 凭证文件
    "credentials.json", "secrets.json", "secrets.yaml",
})
```

### 3.2 路径检查函数

```python
def is_excluded_path(path: Path) -> bool:
    """检查路径是否在排除列表中"""
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

### 3.3 有效工作目录

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

### 3.4 路径解析修改

修改 `resolve_workspace_path()` 函数：

```python
def resolve_workspace_path(rel_path: str) -> Path:
    """解析相对路径到绝对路径（支持项目目录）"""
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
            "该路径被安全策略排除（敏感目录或文件）"
        )

    return target
```

---

## 4. 写入权限控制

### 4.1 写入检查函数

```python
def check_write_permission() -> None:
    """检查是否有写入权限"""
    if settings.project_root and not settings.project_write_enabled:
        raise PermissionError(
            "当前项目配置为只读模式。\n"
            "如需允许 AI 修改代码，请在 .env 中设置：\n"
            "PROJECT_WRITE_ENABLED=true"
        )
```

### 4.2 写入函数修改

修改 `safe_write_file()` 函数：

```python
def safe_write_file(rel_path: str, content: str) -> str:
    # 新增：写入权限检查
    check_write_permission()

    target = resolve_workspace_path(rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)
```

---

## 5. 工具行为变更

### 5.1 读取类工具

无行为变更，自动支持项目目录：

| 工具 | 说明 |
|------|------|
| `list_workspace_entries` | 列出项目目录结构 |
| `read_workspace_text` | 读取项目文件内容 |
| `build_workspace_overview` | 生成项目概览 |

### 5.2 写入类工具

`write_workspace_text` 新增检查：

1. 检查 `PROJECT_WRITE_ENABLED` 配置
2. 检查路径是否在排除列表
3. 失败时返回友好的错误提示

### 5.3 错误提示

**只读模式错误：**
```
当前项目配置为只读模式。
如需允许 AI 修改代码，请在 .env 中设置：
PROJECT_WRITE_ENABLED=true
```

**排除路径错误：**
```
该路径被安全策略排除（敏感目录或文件），不允许访问。
排除的目录包括: .git, node_modules, .env 等
```

---

## 6. 向后兼容性

### 6.1 行为对比

| 场景 | PROJECT_ROOT 未配置 | PROJECT_ROOT 已配置 |
|------|-------------------|-------------------|
| 工作目录 | `backend/workspace/` | 配置的项目路径 |
| 默认权限 | 读写允许 | 只读 |
| 排除检查 | 不检查 | 检查敏感路径 |
| 现有功能 | 完全兼容 | 完全兼容 |

### 6.2 迁移指南

用户只需在 `.env` 中添加：

```env
PROJECT_ROOT=E:/your-project
PROJECT_WRITE_ENABLED=true
```

---

## 7. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend/app/core/config.py` | 修改 | 新增配置项 |
| `backend/app/tools/safe_fs.py` | 修改 | 新增排除逻辑和权限检查 |
| `backend/app/tools/workspace_tools.py` | 修改 | 写入工具增加检查 |
| `backend/.env.example` | 修改 | 新增配置示例 |

---

## 8. 测试计划

### 8.1 单元测试

- [ ] `is_excluded_path()` 排除路径检测
- [ ] `get_effective_workspace_dir()` 路径解析
- [ ] `check_write_permission()` 权限检查
- [ ] `resolve_workspace_path()` 项目路径解析

### 8.2 集成测试

- [ ] 未配置 PROJECT_ROOT 时行为不变
- [ ] 配置 PROJECT_ROOT 后读取项目文件
- [ ] 只读模式拒绝写入
- [ ] 排除路径拒绝访问

---

## 9. 后续迭代

本设计完成后，可继续实现：

1. **Git 工具** - 版本控制操作
2. **受控 Shell** - 白名单命令执行
3. **多项目支持** - `ALLOWED_PROJECTS` 配置
