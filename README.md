# cyber-waifu-vue

一个基于 **Vue 3 + Vite + Electron + PixiJS** 的 Live2D 桌面小组件原型：

- 主窗口：透明/置顶/无边框的 Live2D 渲染窗口
- 控制台窗口：独立“命令行”UI，通过 IPC 控制主窗口的 **动作（motion）/表情（expression）/聚焦（focus）/点击（tap）**
- 字幕窗口（打趣）：透明背景白字，用于显示“打趣/吐槽”的话语（不用于输出专业调试信息）
- 聊天窗口（AI Chat）：专门用于与后台 AI agent 对话，输出“专业回答”（与字幕窗口输出接口完全分离）

默认加载的模型路径：`public/live2d/mianfeimox/llny.model3.json`。

> Live2D 资源与运行库放置细节见：`public/live2d/README.md`。

## 环境要求

- Node.js（建议 18+）
- pnpm
- Windows / macOS / Linux（Electron）
- uv（用于管理 Python 环境和后端依赖）
- Python（后端推荐 3.11，3.12 也可）

## 快速开始

安装依赖：

```bash
pnpm install
```

开发运行（会同时启动：Vite dev server + Electron 主窗口 + 控制台窗口）：

```bash
pnpm dev
```

说明：`pnpm dev` 会默认拉起三个窗口：主窗口（Live2D）、控制台窗口（CLI）、字幕窗口（打趣）。

补充：当前也会拉起一个聊天窗口（AI Chat）。

构建（会生成前端产物 `dist/`；Electron 主进程产物在 `dist-electron/`）：

```bash
pnpm build
```

仅预览 Web（不会启动 Electron 控制台窗口）：

```bash
pnpm preview
```

## 更换模型

1. 把你的模型文件夹放到 `public/live2d/<你的模型目录>/`（保持模型原始相对路径结构）。
2. 修改 `src/App.vue` 里的 `DEFAULT_MODEL_JSON_PATH` 指向你的 `*.model3.json` 或 `*.model.json`。

提示：

- `*.model3.json` 会走 Cubism 4 入口（`pixi-live2d-display/cubism4`）
- `*.model.json` 会走 Cubism 2 入口（`pixi-live2d-display/cubism2`）

## Live2D 运行库（重要）

`pixi-live2d-display` **不会自动把 Live2D Core 运行库文件放到你的静态资源目录**。

本项目采用“启动/构建前同步运行库到 public”的策略：

- 脚本：`scripts/sync-live2d-runtime.mjs`
- 触发时机：每次 `pnpm dev` / `pnpm build`
- 同步目标：
	- `public/live2d/live2dcubismcore.min.js`
	- `public/live2d/live2d.min.js`

这套方案的核心价值是：即使你拿不到某些官方 Core 的 wasm（例如 `_em_module.wasm`），也能先把 Cubism4 模型跑起来（依赖 `live2dcubismcore@1.0.2` 的 JS-only core）。

## 控制台窗口（CLI）

Electron 启动后会自动打开一个名为“Live2D 控制台”的窗口。

控制台输入命令后，会通过 IPC 转发给主窗口执行，并回显结果。

可用命令（输入 `help` 也能看到）：

- `status`：查看当前模型是否已加载、模型 URL
- `meta [reload]`：读取并打印 `model3.json` 里的 Motions/Expressions 元数据
- `list motions` / `list expressions`：列出可用动作/表情（输出的是“Action ID”，后端可直接拿去调用）
- `motion <group> [index]`：播放动作（index 省略=随机）
- `motion <file.motion3.json>`：按文件播放动作（不依赖 model3.json 声明）
- `expr <name|index>`：仅显示该表情（等价于：清空后 add）
- `expr <file.exp3.json>`：按文件设置表情（不依赖 model3.json 声明）
- `expr tag:<通用标签>`：通过“表情标签映射”播放（给 AI agent 用）
- `expr add <name|index>`：叠加一个表情（Cubism4/model3 优先）
- `expr add <file.exp3.json>`：按文件叠加表情
- `expr add tag:<通用标签>`：通过映射叠加表情
- `expr remove <name|index>`：移除一个表情
- `expr remove <file.exp3.json>`：移除按文件叠加的表情
- `expr clear`：清空所有叠加表情
- `expr active`：查看当前已叠加表情
- `startup expr <a,b,c>`：设置启动默认表情（逗号分隔）
- `startup clear`：清除启动默认表情
- `startup show`：查看启动默认表情
- `quip <text>`：把字幕窗口的文字更新为一段“打趣话语”
- （聊天窗口不通过此处命令控制，而是直接在 AI Chat 窗口内输入对话）
- `stop`：停止所有动作
- `focus <x> <y> [instant]`：视线/聚焦（`x/y` 范围 `-1..1`）
- `tap <x> <y>`：对屏幕像素坐标执行点击（触发 hitTest 与事件）

补充说明：

- “多表情叠加”优先走 Cubism4（`*.model3.json`）。Cubism2（`*.model.json`）会回落为单表情（库自身行为）。
- 启动默认表情会被当作“底层 pinned 表情”：后续执行 `expr <...>` / WS `mode:set` 只会覆盖非 pinned 的表情，不会把它覆盖掉（适合用来做“去水印”底座）。
- 启动默认表情也可以通过 URL 直接传：`/?startupExpr=水印,生气`（优先级高于本地保存）。也支持：`/?startupExpr=tag:开心,tag:害羞`。

## WebSocket 控制接口（给后端用）

为了便于“多模型兼容 + 给后端提供统一接口”，项目在 Electron 主进程内置了一个本地 WebSocket 服务：

- 默认监听：`ws://127.0.0.1:23333`
- 可配置环境变量：
	- `LIVE2D_WS_PORT`：端口（默认 23333）
	- `LIVE2D_WS_HOST`：绑定地址（默认 127.0.0.1，不建议改为 0.0.0.0）

### 消息协议（JSON）

所有请求都建议带一个 `reqId` 便于后端做并发匹配。

1) 查询状态：

```json
{ "op": "status", "reqId": "1" }
```

2) 列出可用动作/表情（统一 Action ID）：

```json
{ "op": "list", "reqId": "2" }
```

也支持按类型过滤（减少返回体积，兼容旧用法）：

```json
{ "op": "list", "reqId": "2e", "type": "expression" }
```

```json
{ "op": "list", "reqId": "2m", "type": "motion" }
```

返回的 `data.expressions` / `data.motions` 内每一项都有一个 `id`（推荐后端直接保存并回传这个 id）。

3) 播放：

```json
{ "op": "play", "reqId": "3", "type": "expression", "id": "expr/关闭水印.exp3.json", "mode": "set" }
```

也支持“通用表情标签”（推荐给 AI agent 用）：

```json
{ "op": "play", "reqId": "3b", "type": "expression", "id": "tag:开心", "mode": "set" }
```

```json
{ "op": "play", "reqId": "4", "type": "motion", "id": "motion/idle_01.motion3.json" }
```

说明：

- `type`：`expression` / `motion`
- `id`：必须来自 `list` 返回的 action id
- `mode`（仅 expression）：`set`（默认）/ `add`

4) 停止：

```json
{ "op": "stop", "reqId": "5" }
```

### 设计要点

- action id **尽量 file-first**：即使 `model3.json` 未声明，也可通过目录扫描的 sidecar 文件（`.exp3.json/.motion3.json`）生成并播放。
- WS 服务只负责转发，真正执行仍在渲染进程（持有 Live2D 实例）。

## 表情标签映射（给 AI agent 用）

AI agent 通常不知道当前模型有哪些真实表情文件/名称，所以项目支持把“通用标签”映射到真实表情：

- 映射文件格式：JSONC（支持 `//` 注释）
- 位置优先级：
	1) 与当前 `*.model3.json` 同目录：`expression-map.jsonc`（推荐：每模型一份）
	2) 全局兜底：`public/live2d/expression-map.jsonc`

### 映射文件怎么写

文件示例见：`public/live2d/expression-map.jsonc`。

核心字段：

- `map`：键是通用标签（例如：开心/生气/难过/疑惑…）
- value 支持三种形态：
	- 字符串：直接指定目标表情（推荐写 action id：`expr/xxx.exp3.json` 或 `expr/@name/Happy`）
	- 字符串数组：从多个候选里随机选一个（适合“开心”有多种表情）
	- `null`：禁用该 tag（收到也不播放）

value 也支持简写：

- 写 `xxx.exp3.json` 会被当作 `expr/xxx.exp3.json`
- 写 `Happy` 会被当作 `expr/@name/Happy`

### 怎么调用（WS / CLI / startup）

- WebSocket：`{"op":"play","type":"expression","id":"tag:开心"}`
- CLI：`expr tag:开心`
- 启动预设：`startup expr tag:开心,tag:害羞` 或 URL：`/?startupExpr=tag:开心,tag:害羞`

## 桌宠交互（透明/点穿透/淡出）

主窗口默认是“桌宠模式”：

- 鼠标移入窗口：会逐渐淡出并切换为点穿透（不挡鼠标）
- 按住 Ctrl 并悬停：保持可交互（可拖拽/缩放/退出等）

交互细节（Windows 无边框透明窗）：

- 为避免出现系统的“可见虚化边框”（`thickFrame`），主窗口不再依赖原生边框缩放。
- 拖拽：按住 Ctrl 时，仅窗口**中间 75% 区域**可拖动（避免拖拽区域覆盖到右上角按钮/缩放角）。
- 缩放：按住 Ctrl 时，窗口四边/四角提供较大的透明缩放热区（更容易点中）。
- 退出：右上角为红色“×”按钮（仅在 Ctrl 可交互时可点击）。

这套交互依赖 Electron 主进程的 `setIgnoreMouseEvents(true, { forward: true })`：

- `forward: true` 允许仍然收到 mousemove，用于做“悬停/离开”的状态机
- 需要额外兜底：透明/点穿透窗口在极端情况下可能漏掉 `pointerenter/pointerleave`，项目会通过主进程轮询“光标是否仍在窗口 bounds 内”作为可靠兜底（也能改善“鼠标快速进入窗口但没触发淡化”的情况）

## 常见问题（Troubleshooting）

### 1) Cubism4 报错提示 Core 初始化失败 / 找不到 wasm

项目默认使用“同步出来的 JS-only core”，通常不需要 wasm。

如果你替换了 Core 文件导致需要 wasm，则需要把对应文件放进 `public/live2d/`，并确保可通过浏览器路径访问：

- `public/live2d/_em_module.wasm` 或 `public/live2d/live2dcubismcore.wasm`

### 2) 我明明有表情/动作文件，但 `list expressions` / `list motions` 为空

控制台的 `list/meta` 主要通过解析 `*.model3.json` 的：

- `FileReferences.Expressions`
- `FileReferences.Motions`

如果你的模型只“放了文件”但没有在 `model3.json` 里声明引用：

- `meta` 仍会为空（因为它遵循 settings）
- `list` 会尝试回落为“扫描目录下的 sidecar 文件”（`.exp3.json/.motion3.json`）

更推荐的解决方法依然是：补齐 `model3.json` 的 `FileReferences`（`Name` + `File`），这样库的标准 definitions 也会完整。

### 3) 偶发模型缩放/偏移不稳定

本项目的布局逻辑使用 `getLocalBounds()` + `pivot` 居中，并在加入舞台后下一帧再次布局，以降低首帧 bounds 不稳定导致的跳变。

如果你换了模型仍出现异常，优先检查：模型 bounds 是否为 0、是否有极端的画布尺寸/遮罩。

### 4) 开了点穿透后，窗口状态偶尔“卡住”

原因通常是：点穿透后无法稳定接收 `pointerleave`，导致渲染侧误判仍在悬停。

本项目的做法：在淡出/点穿透期间，定时向主进程询问“光标是否还在窗口 bounds 内”，若不在则强制恢复为非悬停状态。

如果你自行改了交互逻辑，建议保留这个兜底，否则很容易出现“透明状态卡住”。

## 字幕窗口（打趣）

字幕窗口是一个独立的透明置顶小窗（`/?mode=quip`）：

- 背景透明、文字为白字
- 鼠标移入：整体逐渐变透明 + 切换为点穿透（点击可穿透到下一层窗口）
- 按住 Ctrl 悬停：恢复可交互（可拖拽/缩放）
- 右上角有一个灰色半透明的 `-`：点击最小化当前窗口

注意：由于点穿透需要由主进程启用 `setIgnoreMouseEvents(true)`，所以 **要点击 `-` 或拖拽/缩放时需要按住 Ctrl**（否则点击会直接穿透到下层窗口）。

## 聊天窗口（AI Chat）

聊天窗口是一个独立窗口（`/?mode=chat`），用于和后台 AI agent 对话，追求“近似原生命令行”的聊天体验。

快捷键：

- `Enter`：发送
- `Shift+Enter`：换行
- `↑/↓`：历史输入
- `Ctrl+L`：清屏

### 接入你的后台 AI agent

聊天窗口走独立 IPC：`agent:chat`（与字幕窗口 `quip:*` 完全不同）。

默认情况下项目内置了一个“占位 agent”，确保 UI 可用。

本项目使用 `uv` 管理 Python 后端环境。最小启动流程如下：

```powershell
# 推荐正式切到 3.11；如果你更想用 3.12，把下面的 3.11 改成 3.12 即可
uv python install 3.11
if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
uv venv --python 3.11 .venv
uv pip install -r backend/requirements.txt
uv run uvicorn backend.app.main:app --reload --port 8000
```

如果你只是想先验证后端在推荐版本下是否正常，也可以不重建 `.venv`，直接运行：

```powershell
uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
```

然后在启动 Electron 前设置环境变量 `AI_AGENT_ENDPOINT` 指向你的 HTTP 服务：

```bash
$env:AI_AGENT_ENDPOINT="http://127.0.0.1:8000/chat"
pnpm dev

# 或者直接用 npm:
set AI_AGENT_ENDPOINT=http://127.0.0.1:8000/chat
pnpm dev
```

- 请求：`POST` JSON `{ prompt, context }`
- 响应：可以返回纯文本；或返回 JSON `{ output: string }` / `{ text: string }`
- 设置 `AI_AGENT_ENDPOINT` 后，Electron 主进程会自动从同一后端轮询 `GET /messages`，接收 quip / expression / chat / status / error 消息。
- 如果消息接口地址需要单独指定，可以额外设置 `AI_AGENT_MESSAGES_ENDPOINT` 覆盖默认推导值。

完整后端说明见：`backend/README.md`。

## 目录结构（概览）

- `electron/`：Electron 主进程（创建主窗口与控制台窗口、IPC 桥）
- `src/`：Vue 渲染进程（Pixi + Live2D、命令解析与执行端）
- `public/live2d/`：Live2D 资源与运行库（会被原样拷贝到 `dist/live2d/`）
- `scripts/sync-live2d-runtime.mjs`：从 `node_modules/live2dcubismcore` 同步运行库到 `public/live2d/`

## 版本说明

详细的制作过程、踩坑与解决方案、结构与构建思路见：`VERSION.md`（当前：V0.6.5）。
