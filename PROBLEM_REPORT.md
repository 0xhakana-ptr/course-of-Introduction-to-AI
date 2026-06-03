# 问题报告：cyber-waifu-vue

> 生成时间：2026-06-03 | 基准 commit：`cb91038` | 最后更新：2026-06-03（修复进度见各节）

---

## 一、仓库污染 ✅ 已修复

### 1.1 Git 跟踪了运行时产物（~90 个文件）✅

`backend/workspace/runs/` 下有约 90 个文件被 Git 跟踪——这些是 AI 生成代码的历史运行结果（`generated/*.py`、`log.txt`、`result.json`）。

**根因**：`backend/.gitignore` 写了 `/workspace/` 规则，但这些文件在添加 `.gitignore` **之前**就已被 commit。`.gitignore` 只对 untracked 文件生效。

**修复**：`git rm --cached -r backend/workspace/runs/`，已执行，当前跟踪数 = 0。

---

### 1.2 根目录有垃圾文件 ✅

| 文件 | 来源 |
|---|---|
| `$null` | PowerShell `> $null` 重定向误写成的实体文件 |
| `temp_fix10.py` | 调试临时文件 |
| `temp_search.py` | 调试临时文件 |
| `temp_simple.py` | 调试临时文件 |

**修复**：
```bash
git rm '$null' temp_fix10.py temp_search.py temp_simple.py
```
并在根 `.gitignore` 追加了 `temp_*.py` 防止以后再出现。当前跟踪数 = 0。

---

### 1.3 截图缓存被 Git 跟踪 ✅

`backend/.tmp_cache/vision_screenshots/screenshot_latest.png` 被跟踪。

**修复**：`git rm --cached backend/.tmp_cache/vision_screenshots/screenshot_latest.png`，当前跟踪数 = 0。

---

### 1.4 `.gitignore` 拼写错误 ✅

[backend/.gitignore:10](backend/.gitignore#L10)：`# temperary files` → `# temporary files`。已修正。

---

## 二、代码质量问题

### 2.1 `roleplay.py` 旧 API 与新 API 并存（~900 行）— 暂不修复

[backend/app/agent_workflow/roleplay.py](backend/app/agent_workflow/roleplay.py) 存在两套做相同事情的代码路径：

| 旧版（模块级函数） | 新版（类方法） |
|---|---|
| `generate_roleplay_response()` | `RoleplayAgent._generate_persona_response()` |
| `_build_state_context()` | `RoleplayAgent._build_context_text()` |
| `emit_roleplay_to_frontend()` | `RoleplayAgent._emit_to_frontend()` |

**不修复原因**：判断旧函数可能仍有隐式调用方，贸然删除风险高。当前无功能 bug，暂维持现状。

---

### 2.2 全局可变单例导致多会话不安全 — 暂不修复

```python
# backend/app/agent_workflow/roleplay.py
_session_mood = RoleplayMood()       # ← 所有会话共享一个情绪状态
```

**不修复原因**：项目定位是本地单用户桌宠，单会话场景下不受影响。改动涉及请求级作用域重构，风险较高。

---

### 2.3 魔法数字散落各处 ✅ 已修复

**修复内容**：所有裸魔法数字已集中到 [backend/app/core/limits.py](backend/app/core/limits.py)，涉及 7 个文件、13 类常量：

| 新常量名 | 值 | 替换位置（原裸值出现次数） |
|---|---|---|
| `ROLEPLAY_LLM_TEMPERATURE` | `0.78` | roleplay.py (×3) |
| `ROLEPLAY_VISION_LLM_TEMPERATURE` | `0.85` | roleplay.py, vision_routes.py (×2) |
| `ROLEPLAY_VISION_LLM_MAX_TOKENS` | `2000` | roleplay.py |
| `ROLEPLAY_VISION_TEST_MAX_TOKENS` | `120` | vision_routes.py |
| `ROLEPLAY_EXPRESSION_DURATION_MS` | `5000` | roleplay.py, vision_routes.py (×3) |
| `ROLEPLAY_CHAT_EXPRESSION_DURATION_MS` | `3000` | roleplay.py |
| `ROLEPLAY_QUIP_DURATION_MS` | `4000` | roleplay.py, runtime_tracker.py, vision_routes.py (×5) |
| `ROLEPLAY_VISION_QUIP_DURATION_MS` | `4500` | roleplay.py |
| `ROLEPLAY_IDLE_QUIP_DURATION_MS` | `3500` | roleplay.py, node_events.py (×2) |
| `ROLEPLAY_EXPRESSION_INTENSITY` | `0.85` | roleplay.py, vision_routes.py (×4) |
| `ROLEPLAY_EXPRESSION_INTENSITY_LIGHT` | `0.75` | roleplay.py |
| `ROUTER_LLM_EXTRACTION_TEMPERATURE` | `0.1` | router.py |
| `COMMAND_POLL_INTERVAL_SECONDS` | `0.2` | safe_execute_command.py |

**验证**：`pytest` 运行结果与原代码一致（240 passed / 67 failed，无新增回归）。

---

### 2.4 `intent.py` 中关键词列表冗余 — 暂不修复

[backend/app/agent_workflow/intent.py](backend/app/agent_workflow/intent.py) 中 `CODING_ACTION_KEYWORDS` 和 `STRONG_OPERATION_ACTION_KEYWORDS` 有大量重叠。

**不修复原因**：不确定是否有代码通过差异化这两个列表来实现不同的意图判断逻辑。

---

## 三、架构隐患

### 3.1 惰性导入暗示循环依赖 — 暂不修复

[backend/app/agent_workflow/engine.py:117](backend/app/agent_workflow/engine.py#L117) 和 [roleplay.py](backend/app/agent_workflow/roleplay.py#L567) 中存在方法内惰性 import，是为绕过循环依赖打的补丁。

> **这是整个项目最不该乱动的部分。没有充分测试覆盖前不要重构。**

---

### 3.2 无持久化存储 → 澄清：已实现本地记忆

原报告指出 `conversation_store` 是纯内存实现。**澄清**：已经做了本地记忆存储（保存在本地文件），此问题不成立。已从问题列表中移除。

---

## 四、工程规范缺失（低风险，加分项）

| 缺失项 | 影响 |
|---|---|
| 无 lint 配置（ruff / black / mypy） | 代码风格因人而异，PR review 时耗费精力在格式上 |
| 无 pre-commit hooks | 临时代码、调试 print 容易混入 commit |
| 无 CI（GitHub Actions） | push 后不知道测试是否通过，靠人工跑 |
| 部分文件缺少 `__init__.py` 的 `__all__` | 公共 API 边界不清 |

以上均为锦上添花项，不影响功能，暂不处理。

---

## 五、修复状态总览

```
已完成
  ✅ 1.1  清理 backend/workspace/runs/ 跟踪       (git rm --cached, 0 残留)
  ✅ 1.2  删除根目录垃圾文件 + .gitignore 防御    (4 文件移除, temp_*.py 规则)
  ✅ 1.3  删除截图缓存跟踪                        (git rm --cached)
  ✅ 1.4  修复 .gitignore 拼写错误                (temperary → temporary)
  ✅ 2.3  魔法数字集中化                          (13 常量 → limits.py, 7 文件修改)

暂不修复
  ⏸️ 2.1  统一 roleplay.py 新旧 API               (风险：隐式调用方不确定)
  ⏸️ 2.2  全局状态改为会话级作用域                (单用户场景不受影响)
  ⏸️ 2.4  修复 intent.py 关键词列表冗余           (不确定是否有意为之)
  ⏸️ 3.1  解开循环依赖                            (高风险)
  ⏸️ 4.x  lint / pre-commit / CI                  (锦上添花)
  ❌ 3.2  持久化存储                              (已实现本地记忆，不成立)
```

---

## 六、当前待提交变更

| 类型 | 文件 | 说明 |
|---|---|---|
| staged delete | `backend/workspace/runs/` (87 files) | 运行时产物清理 |
| staged delete | `$null`, `temp_*.py` (4 files) | 垃圾文件清理 |
| staged delete | `screenshot_latest.png` | 截图缓存清理 |
| unstaged modify | `.gitignore` | 追加 `temp_*.py` |
| unstaged modify | `backend/.gitignore` | 拼写修正 |
| unstaged modify | `backend/app/core/limits.py` | +17 新常量 |
| unstaged modify | `backend/app/agent_workflow/roleplay.py` | 12 处魔法数字 → 常量 |
| unstaged modify | `backend/app/agent_workflow/router.py` | 1 处 temperature → 常量 |
| unstaged modify | `backend/app/agent_workflow/runtime_tracker.py` | 2 处 duration → 常量 |
| unstaged modify | `backend/app/agent_workflow/output/node_events.py` | 1 处 duration → 常量 |
| unstaged modify | `backend/app/tools/safe_execute_command.py` | 1 处 poll_interval → 常量 |
| unstaged modify | `backend/app/api/vision_routes.py` | 4 处魔法数字 → 常量 |

---

## 七、已知运行时问题

### 7.1 `[backend-bridge] poll failed: AbortError`

**现象**：终端偶尔输出 `[backend-bridge] poll failed: AbortError: This operation was aborted`。此时前端的确认弹窗（如桌面导出确认）可能无法弹出，文件操作回退到 `workspace/`。

**根因**：[electron/main.ts:915-917](electron/main.ts#L915-L917) 中，Electron 每 1 秒轮询 `GET /messages`，超时设为 8 秒。当后端正在执行耗时 Agent 任务或截图识别时，`/messages` 响应慢了就会触发 `AbortController.abort()`。

**影响链路**：
```
用户请求导出文件到桌面
  → 后端通过 /messages 发确认请求给前端
  → Bridge 轮询超时（AbortError），消息未送达
  → 前端确认框弹不出
  → 后端收不到确认，回退到 workspace/
```

**临时缓解**：
1. 关闭视觉截图（`VISION_ENABLED=false`）可减少卡顿
2. 加大 `AI_AGENT_MESSAGES_TIMEOUT_MS`（默认 8000ms）可降低超时概率
3. 文件功能本身不受影响，只是落到了 `workspace/` 而非桌面导出目录

**是否修复**：暂不修复。根因修复需要改为 WebSocket 推送或 SSE，工作量较大。当前影响范围有限（偶发超时，功能回退可用）。
