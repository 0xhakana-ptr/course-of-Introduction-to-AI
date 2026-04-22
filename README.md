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
- `list motions` / `list expressions`
- `motion <group> [index]`：播放动作（index 省略=随机）
- `expr <name|index>`：仅显示该表情（等价于：清空后 add）
- `expr add <name|index>`：叠加一个表情（Cubism4/model3 优先）
- `expr remove <name|index>`：移除一个表情
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
- 启动默认表情也可以通过 URL 直接传：`/?startupExpr=水印,生气`（优先级高于本地保存）。

## 桌宠交互（透明/点穿透/淡出）

主窗口默认是“桌宠模式”：

- 鼠标移入窗口：会逐渐淡出并切换为点穿透（不挡鼠标）
- 按住 Ctrl 并悬停：保持可交互（可拖拽/缩放等）

这套交互依赖 Electron 主进程的 `setIgnoreMouseEvents(true, { forward: true })`：

- `forward: true` 允许仍然收到 mousemove，用于做“悬停/离开”的状态机
- 需要额外兜底：因为点穿透后可能收不到 `pointerleave`，项目会在淡出时轮询“光标是否仍在窗口内”来恢复状态

## 常见问题（Troubleshooting）

### 1) Cubism4 报错提示 Core 初始化失败 / 找不到 wasm

项目默认使用“同步出来的 JS-only core”，通常不需要 wasm。

如果你替换了 Core 文件导致需要 wasm，则需要把对应文件放进 `public/live2d/`，并确保可通过浏览器路径访问：

- `public/live2d/_em_module.wasm` 或 `public/live2d/live2dcubismcore.wasm`

### 2) 我明明有表情/动作文件，但 `list expressions` / `list motions` 为空

控制台的 `list/meta` 是通过解析 `*.model3.json` 的：

- `FileReferences.Expressions`
- `FileReferences.Motions`

如果你的模型只“放了文件”但没有在 `model3.json` 里声明引用，库和控制台都无法“发现”它们。

解决方法：补齐 `model3.json` 的 `FileReferences`（`Name` + `File`）。

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

要接入真实后台：在启动 Electron 前设置环境变量 `AI_AGENT_ENDPOINT` 指向你的 HTTP 服务：

- 请求：`POST` JSON `{ prompt, context }`
- 响应：可以返回纯文本；或返回 JSON `{ output: string }` / `{ text: string }`

## 目录结构（概览）

- `electron/`：Electron 主进程（创建主窗口与控制台窗口、IPC 桥）
- `src/`：Vue 渲染进程（Pixi + Live2D、命令解析与执行端）
- `public/live2d/`：Live2D 资源与运行库（会被原样拷贝到 `dist/live2d/`）
- `scripts/sync-live2d-runtime.mjs`：从 `node_modules/live2dcubismcore` 同步运行库到 `public/live2d/`

## 版本说明

详细的制作过程、踩坑与解决方案、结构与构建思路见：`VERSION.md`（当前：V0.5.2）。
