# 问题报告

---

## 前端（Electron + Vue + PixiJS）

| # | 项目 | 说明 | 难度 |
|---|---|---|---|
| 1 | **Bridge 轮询改 WebSocket** | 当前 `GET /messages` 每 1 秒轮询 + 8 秒超时，偶发 `AbortError`。后端已有 WebSocket 端点（`/ws/messages`），前端切过去可以消除超时问题 | 中 |
| 2 | **`src/App.vue` 默认模型路径硬编码** | [App.vue:15](src/App.vue#L15) `DEFAULT_MODEL_JSON_PATH` 写死了 `llny.model3.json`，可改为从 URL 参数或配置文件读取 | 低 |
| 3 | **主题初始化逻辑位置不当** | [AgentChat.vue:26-31](src/components/AgentChat.vue#L26-L31) 在 `<script setup>` 顶部有散落的 `localStorage` 操作，应该放到 `onMounted` 里 | 低 |
| 4 | **`copyMessage()` 用了废弃 API** | [AgentChat.vue:20](src/components/AgentChat.vue#L20) `document.execCommand('copy')` 已废弃，应改用 `navigator.clipboard.writeText`（已有但 fallback 写法是对的，注释标注即可） | 低 |
| 5 | **PixiJS 挂到 `window` 全局** | [App.vue:10](src/App.vue#L10) `(window as any).PIXI = PIXI` 是给 Live2D 库用的 hack，可以考虑封装成模块导入 | 低 |
| 6 | **鼠标追踪轮询兜底** | [App.vue:58-59](src/App.vue#L58-L59) `cursorPollTimer` 轮询光标位置做点穿透兜底，在不需要透明窗口的场景下是多余开销 | 低 |
| 7 | **highlight.js 按需加载** | [AgentChat.vue:34-45](src/components/AgentChat.vue#L34-L45) 手动 register 了 12 种语言，可改用 `highlight.js/lib/common` 一次性注册常用语言 | 低 |

---

## 后端（FastAPI + LangGraph）

| # | 项目 | 说明 | 难度 |
|---|---|---|---|
| 1 | **`roleplay.py` 新旧 API 统一** | 旧函数 `generate_roleplay_response` / `emit_roleplay_to_frontend` 和新的 `RoleplayAgent` 类方法做同样的事，合并后可删 ~200 行 | 中 |
| 2 | **全局 `_session_mood` 改会话级** | 目前所有会话共享一个情绪状态，改为 `dict[session_id → RoleplayMood]` 才能正确表现多会话 | 中 |
| 3 | **解开循环依赖** | `roleplay → engine → graphs → roleplay` 存在循环，靠方法内惰性 import 硬撑。需要抽取共享接口层 | 高 |
| 4 | **`intent.py` 关键词去重** | `CODING_ACTION_KEYWORDS` 和 `STRONG_OPERATION_ACTION_KEYWORDS` 大量重叠，合并后减少维护成本 | 低 |
| 5 | **桌面导出功能死代码** | `DESKTOP_EXPORT_ENABLED` 依赖前端 bridge 传确认消息，bridge 偶发超时就回退 workspace。如果实际不用，可以砍掉这个功能的代码路径 | 中 |
| 6 | **`vision/monitor.py` 截图间隔可配置但不统一** | `VISION_INTERVAL_SECONDS` 已在 `.env.example` 了，但 `electron/main.ts` 端另有一个 `VISION_INTERVAL_MS`（默认 30s），两边不一致，建议统一 | 低 |
| 7 | **缺少请求级日志追踪** | 每个请求没有 trace ID，出问题时只能靠时间戳猜。加一个 middleware 生成 `X-Request-ID` 会很有帮助 | 低 |

---

## 已知运行时问题

**`[backend-bridge] poll failed: AbortError`**

Electron 每 1 秒轮询 `GET /messages`（8 秒超时），Agent 任务耗时或截图识别卡顿时会触发超时。此时前端确认弹窗无法弹出，桌面导出回退到 `workspace/`。

- **临时缓解**：关闭视觉截图（`VISION_ENABLED=false`）、加大 `AI_AGENT_MESSAGES_TIMEOUT_MS`
- **根治**：Bridge 轮询改为 WebSocket（见前端 #1）