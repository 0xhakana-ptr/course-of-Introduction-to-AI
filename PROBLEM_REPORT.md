# 问题报告：cyber-waifu-vue

> 生成时间：2026-06-03 | 基准 commit：`cb91038`

---

## 一、仓库污染（低风险，容易修）

### 1.1 Git 跟踪了运行时产物（~90 个文件）

`backend/workspace/runs/` 下有约 90 个文件被 Git 跟踪——这些是 AI 生成代码的历史运行结果（`generated/*.py`、`log.txt`、`result.json`）。

**根因**：`backend/.gitignore` 写了 `/workspace/` 规则，但这些文件在添加 `.gitignore` **之前**就已被 commit。`.gitignore` 只对 untracked 文件生效。

**影响**：仓库体积膨胀，每次 `git clone` 都会拉下无用文件；`git log` 里能看到每次 AI 生成的临时代码。

**修复方式**：
```bash
git rm --cached -r backend/workspace/runs/
```

---

### 1.2 根目录有垃圾文件

| 文件 | 来源 |
|---|---|
| `$null` | PowerShell `> $null` 重定向误写成的实体文件 |
| `temp_fix10.py` | 调试临时文件 |
| `temp_search.py` | 调试临时文件 |
| `temp_simple.py` | 调试临时文件 |

**影响**：项目根目录不整洁；`$null` 文件名在 Windows 资源管理器中可能引起困惑。

**修复方式**：
```bash
git rm '$null' temp_fix10.py temp_search.py temp_simple.py
```
并在根 `.gitignore` 追加一行 `temp_*.py` 防止以后再出现。

---

### 1.3 截图缓存被 Git 跟踪

`backend/.tmp_cache/vision_screenshots/screenshot_latest.png` 被跟踪。

**根因**：`backend/.gitignore` 写了 `/.tmp_cache/*` 但同样是"先 commit 后补规则"的问题。

**修复方式**：
```bash
git rm --cached backend/.tmp_cache/vision_screenshots/screenshot_latest.png
```

---

### 1.4 `.gitignore` 拼写错误

[backend/.gitignore:10](backend/.gitignore#L10)：

```diff
- # temperary files
+ # temporary files
```

不影响功能，但显得粗糙。

---

## 二、代码质量问题（中风险，建议修但不紧急）

### 2.1 `roleplay.py` 旧 API 与新 API 并存（907 行）

[backend/app/agent_workflow/roleplay.py](backend/app/agent_workflow/roleplay.py) 是项目中最长的单文件，存在两套做相同事情的代码路径：

| 旧版（模块级函数） | 新版（类方法） | 所在行 |
|---|---|---|
| `generate_roleplay_response()` | `RoleplayAgent._generate_persona_response()` | L409 / L674 |
| `_build_state_context()` | `RoleplayAgent._build_context_text()` | L330 / L743 |
| `emit_roleplay_to_frontend()` | `RoleplayAgent._emit_to_frontend()` | L470 / L759 |

**风险**：改一处逻辑容易忘记同步另一处，两套代码行为会逐渐分化，产生难以排查的 bug。

**建议**：
1. 用 `rg "generate_roleplay_response|emit_roleplay_to_frontend|emit_roleplay_chat" --type py` 找到所有调用方
2. 逐一迁移到 `RoleplayAgent` 的方法
3. 删除旧函数

---

### 2.2 全局可变单例导致多会话不安全

```python
# backend/app/agent_workflow/roleplay.py:206
_session_mood = RoleplayMood()       # ← 所有会话共享一个情绪状态

# backend/app/agent_workflow/engine.py:184
work_agent = WorkAgent()             # ← 模块级单例

# backend/app/agent_workflow/router.py:363
routing_guard = RoutingGuard()       # ← 模块级单例
```

**具体场景**：如果用户 A 连续三次请求失败，`_session_mood` 进入"沮丧"状态。此时用户 B 发起新对话，也会被回应沮丧语气——因为 `_session_mood` 是全局共享的。

**目前影响**：项目定位是本地单用户桌宠，所以暂时不会出问题。但如果答辩时老师要求同时开两个窗口演示，就会暴露。

**建议**：将 `_session_mood` 改为 `dict[str, RoleplayMood]`，以 `session_id` 为键。`WorkAgent` 和 `RoutingGuard` 本身无状态，去掉模块级单例影响不大。

---

### 2.3 魔法数字散落各处

| 值 | 出现位置 |
|---|---|
| `temperature=0.78` | roleplay.py 多处 LLM 调用 |
| `temperature=0.85` | roleplay.py `emit_vision_quip()` |
| `duration=5000` / `4000` / `3000` | roleplay.py 前端事件发送 |
| `poll_interval = 0.2` | safe_execute_command.py |
| `max_tokens=2000` | roleplay.py vision quip |
| `intensity=0.85` / `0.75` | roleplay.py 表情强度 |

**风险**：调参时容易漏改；新人看代码不知道这些值为什么是这个数。

**建议**：统一收到 [backend/app/core/config.py](backend/app/core/config.py) 或 [backend/app/core/limits.py](backend/app/core/limits.py) 中，用 `settings.xxx` 引用。

---

### 2.4 `intent.py` 中关键词列表冗余

[backend/app/agent_workflow/intent.py](backend/app/agent_workflow/intent.py) 中 `CODING_ACTION_KEYWORDS` 和 `STRONG_OPERATION_ACTION_KEYWORDS` 有大量重叠（后者几乎是前者的子集去掉了几个词）。维护两个几乎相同的列表容易产生不一致。

---

## 三、架构隐患（高风险，改动需谨慎）

### 3.1 惰性导入暗示循环依赖

[backend/app/agent_workflow/engine.py:117](backend/app/agent_workflow/engine.py#L117)：

```python
def _execute_loop(self, decision, ...):
    from .graphs.loop_agent_loop_graph import run_agent_loop   # ← 方法内导入
    ...
```

[backend/app/agent_workflow/roleplay.py:567](backend/app/agent_workflow/roleplay.py#L567)：

```python
@property
def work_agent(self):
    if self._work_agent is None:
        from .engine import work_agent   # ← property 内导入
    return self._work_agent
```

这些都是为了绕过循环依赖而打的补丁。

**风险**：如果有人重构时把惰性 import 提到文件顶部（IDE 的 auto-import 经常干这事），直接 `ImportError`。而且循环依赖让模块无法独立测试。

**建议**：
1. 先画出完整的模块依赖图：`router → roleplay → engine → graphs → state → ...`
2. 找到循环闭合的位置
3. 用依赖反转解决（抽取接口/协议层，或引入 `core/types.py` 作为共享类型层）

> **这是整个项目最不该乱动的部分。没有充分测试覆盖前不要重构。**

---

### 3.2 无持久化存储——重启即失忆

`conversation_store`（[backend/app/storage/conversation_store.py](backend/app/storage/conversation_store.py)）是纯内存实现。服务重启 → 所有对话历史丢失。

对于一个"桌面 AI 伴侣"定位的产品，用户关掉应用再打开发现 AI 完全不记得之前的对话，体验会很差。

**建议**：加 SQLite（推荐 `aiosqlite`）或 JSON 文件持久化。改动范围可限制在 `storage/` 目录内，不影响其他模块。

---

## 四、工程规范缺失（低风险，加分项）

| 缺失项 | 影响 |
|---|---|
| 无 lint 配置（ruff / black / mypy） | 代码风格因人而异，PR review 时耗费精力在格式上 |
| 无 pre-commit hooks | 临时代码、调试 print 容易混入 commit |
| 无 CI（GitHub Actions） | push 后不知道测试是否通过，靠人工跑 |
| 部分文件缺少 `__init__.py` 的 `__all__` | 公共 API 边界不清 |

---

## 五、修复优先级建议

```
第一梯队: 零风险，独立可做，建议立即修
  ├─ 1.1  git rm --cached 清理仓库污染       ← 5 分钟
  ├─ 1.2  删除根目录垃圾文件                  ← 2 分钟
  ├─ 1.3  删除截图缓存跟踪                    ← 1 分钟
  └─ 1.4  修复 .gitignore 拼写错误            ← 10 秒

第二梯队: 改善质量，需要跑一次测试验证
  ├─ 2.3  魔法数字集中化                      ← 30 分钟
  └─ 2.2  全局状态改为会话级作用域            ← 1-2 小时

第三梯队: 需要完整回归测试，风险较高
  ├─ 2.1  统一 roleplay.py 新旧 API           ← 2-4 小时
  ├─ 3.1  解开循环依赖                        ← 需先画依赖图
  └─ 3.2  添加持久化存储                      ← 半天

第四梯队: 锦上添花，不影响功能
  ├─ 加 lint / pre-commit / CI
  ├─ 修复 intent.py 关键词列表冗余
  └─ 补充 docstring 和缺失的类型标注
```

---

## 六、修复顺序原则

1. **第一梯队先做**——都是 `git rm --cached` 级别的操作，不会引入任何 bug。
2. **第二梯队每改一个就跑一次 `pytest`**——[backend/tests/](backend/tests/) 下有覆盖，确保不引入回归。
3. **第三梯队建议在答辩之后做**——除非答辩要求展示"代码整洁度"。
4. 每次改完 commit 一次，不要一个大 PR 改所有东西——方便出问题时 `git bisect`。
