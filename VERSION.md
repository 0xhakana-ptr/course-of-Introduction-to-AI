# VERSION.md

## V0.5.0（2026-04-09）

本文档用于记录本项目在 V0.5.0 阶段的：

- 整体结构与模块职责
- 构建与运行链路（为什么这么组织）
- 制作过程中遇到的关键问题与解决方法（可复用的排障结论）

---

## 1. 项目目标（V0.5.0）

在桌面端（Electron）实现一个可控的 Live2D 小组件：

- 主窗口负责渲染 Live2D（透明、置顶、无边框）
- 通过一个独立的“命令行控制台窗口”控制模型：动作、表情、聚焦、点击
- 控制接口要求“通用”：换模型后仍尽量可用（不为单个模型硬编码动作/表情名）

---

## 2. 技术选型与理由

- Vue 3 + Vite：渲染进程 UI 与开发体验
- Electron：桌面窗口能力（透明、置顶、独立控制台窗口、IPC）
- PixiJS 6：WebGL 2D 渲染层
- pixi-live2d-display：把 Live2D（Cubism2/Cubism4）以 Pixi DisplayObject 的形式接入，并提供 motion/expression/focus/tap API

### 为什么要做“独立控制台窗口”

直接在主窗口里加输入框会影响交互与展示；独立窗口可以做到：

- 主窗口尽量保持“娃/桌宠”呈现，不混杂调试 UI
- 控制台窗口可以持续输出日志，适合调试动作组、表情名、模型元数据
- 命令接口天然可脚本化（后续可扩展为快捷键/预设脚本，但 V0.5.0 不做额外功能）

---

## 3. 目录结构与职责（V0.5.0）

- `electron/main.ts`
  - 创建两个窗口：主窗口 + 控制台窗口
  - 提供 IPC 桥：控制台窗口命令 → 主窗口执行 → 返回结果

- `src/App.vue`
  - 主窗口模式：初始化 Pixi、加载 Live2D、布局与渲染
  - CLI 模式（`?mode=cli`）：渲染控制台组件
  - 统一命令解析与执行（通用接口）：`help/status/meta/list/motion/expr/stop/focus/tap`

- `src/components/Live2DConsole.vue`
  - 控制台 UI：输入命令、回显输出
  - 通过 `ipcRenderer.invoke('live2d:command', cmd)` 发送命令

- `src/platform/electronIpc.ts`
  - 对 `ipcRenderer` 的轻量封装：在 Web 与 Electron 环境下都能安全调用

- `public/live2d/`
  - Live2D 资源与运行库静态文件
  - 构建后会被原样复制到 `dist/live2d/`
  - 细则见 `public/live2d/README.md`

- `scripts/sync-live2d-runtime.mjs`
  - 每次 dev/build 前把 Live2D runtime 从依赖同步到 `public/live2d/`

---

## 4. 运行与构建链路（思路）

### 4.1 开发态（`pnpm dev`）

脚本：

1. `node scripts/sync-live2d-runtime.mjs`
   - 复制：
     - `node_modules/live2dcubismcore/live2dcubismcore.min.js` → `public/live2d/live2dcubismcore.min.js`
     - `node_modules/live2dcubismcore/live2d.min.js` → `public/live2d/live2d.min.js`
2. `vite`
   - Vite dev server 提供静态资源与热更新
3. `vite-plugin-electron`
   - 在 Vite 启动后拉起 Electron
   - Electron 主进程读取 `process.env.VITE_DEV_SERVER_URL` 加载页面

结果：Electron 同时打开两个窗口：

- 主窗口：加载 `/`，渲染 Live2D
- 控制台窗口：加载 `/?mode=cli`，渲染控制台 UI

### 4.2 构建态（`pnpm build`）

1. 同样先同步运行库到 `public/live2d/`
2. `vue-tsc -b` 做类型检查
3. `vite build` 输出前端产物到 `dist/`
4. Electron 主进程产物输出到 `dist-electron/`（由 `vite-plugin-electron` 处理）

注意：本仓库 **未内置安装包/分发打包流程**（如 electron-builder）。

---

## 5. 关键问题与解决方法（V0.5.0）

### 5.1 Cubism4 模型加载崩溃：缺失 `_em_module.wasm`

现象：

- 使用 Cubism4 `.model3.json` 时，渲染阶段出现 `renderOrders`/`renderOrder[0]` 等读取异常
- 追踪后发现 Core 运行库是 Emscripten/WASM 变体，内部会请求 `_em_module.wasm`
- 但 `public/live2d/` 目录没有 wasm 文件，导致 Core 未初始化完全，后续数据结构为 `undefined`

解决：

- 改用 npm 依赖 `live2dcubismcore@1.0.2` 提供的 **JS-only core**（默认不依赖 wasm）
- 用 `scripts/sync-live2d-runtime.mjs` 在 dev/build 前同步到 `public/live2d/`
- 在渲染侧（`src/App.vue`）增加更稳的 ready 检测：
  - 兼容 “core 本体” 或 “thenable module（_em_module）” 两种形态
  - 同时保留 `locateFile`，在用户替换为需要 wasm 的 core 时仍可指定 wasm 路径

可复用结论：

- “模型文件齐全”不代表能跑：Cubism4 的 core 是否需要 wasm 取决于你使用的 core 版本/构建方式
- 出现渲染阶段的 `undefined` 结构读写时，要优先排查 runtime 是否 ready

### 5.2 偶发布局放大/偏移：首帧 bounds 不稳定

现象：

- 模型偶尔出现“镜头怼脸/偏移”等布局跳变
- 简单用 `model.width/height` 或只在加载时布局，容易受内部初始化顺序影响

解决：

- 使用 `getLocalBounds()` 作为布局依据
- 通过 `pivot` 把模型的局部中心对齐到舞台中心，缩放更稳定
- 在 `stage.addChild(model)` 后：
  - 立即布局一次
  - 下一帧再布局一次（ticker/addOnce），规避首帧 bounds 波动

可复用结论：

- 对 Live2D 这类内部会延迟初始化 drawables 的对象，首帧 bounds 可能不可靠

### 5.3 控制台 `list expressions` 为空：表情文件存在但“未声明”

现象：

- 模型目录下有 `expressions/*.exp3.json`
- 但控制台 `list expressions` 为空

根因：

- `pixi-live2d-display` 与本项目的通用控制逻辑都依赖 `model3.json` 的标准字段：
  - `FileReferences.Expressions`
  - `FileReferences.Motions`
- 如果模型作者没有把表情/动作写入 `model3.json`（只放文件），框架无法自动发现

解决：

- 补齐对应模型的 `*.model3.json`：把每个表情以 `{ Name, File }` 的形式写入 `FileReferences.Expressions`
- 同理补齐 `FileReferences.Motions`（至少提供一个 Idle 组用于测试）

可复用结论：

- “文件存在 ≠ 可被框架发现”
- 要做“通用控制接口”，就必须以标准 settings JSON 为数据源

### 5.4 IPC 命令桥：跨窗口控制要可追踪、可超时

实现要点：

- 控制台窗口发起命令：`ipcRenderer.invoke('live2d:command', cmd)`
- 主进程生成 `requestId`（UUID），转发到主窗口执行：`mainWindow.webContents.send('live2d:command', {id, cmd})`
- 主窗口执行后回传：`ipcRenderer.send('live2d:commandResult', {id, ok, output})`
- 主进程维护 pending Map 并设置 5s 超时，避免控制台卡死

可复用结论：

- 多窗口 IPC 的关键是“请求-响应”要有 id，且一定要有超时策略

---

## 6. 当前能力边界（V0.5.0）

- 已实现：加载模型、动作/表情控制、基础交互（focus/tap）、双窗口与 IPC
- 未实现（刻意不做）：安装包打包、配置化 UI、动作/表情预设与快捷键、模型管理器

---

## 7. 如何验证（建议自测清单）

1. `pnpm dev` 后应同时看到：主窗口 + 控制台窗口
2. 控制台输入：
   - `status`
   - `meta`
   - `list motions`
   - `list expressions`
   - `motion Idle 0`
   - `expr 0` 或 `expr <表情名>`
3. 若 `list expressions` 仍为空：检查模型的 `*.model3.json` 是否包含 `FileReferences.Expressions`

---

## V0.5.2（2026-04-22）

V0.5.2 在 V0.5.0 的基础上，主要补齐“桌宠交互体验”和“表情能力”的两块短板：

- 桌宠交互：悬停淡出 + 点穿透；按住 Ctrl 保持可交互（拖拽/缩放等）
- 表情能力：支持多表情叠加（Cubism4/model3 优先），并支持配置“启动默认表情”
 - 对话体验：新增一个专门用于与后台 AI agent 对话的聊天窗口（专业输出接口，与字幕窗口分离）

---

## 1. 使用方法（V0.5.2）

### 1.1 控制台命令（新增/变更）

表情：

- `expr <name|index>`：仅显示该表情（相当于：清空后 add）
- `expr add <name|index>`：叠加表情（Cubism4/model3 优先）
- `expr remove <name|index>`：移除一个叠加表情
- `expr clear`：清空所有叠加表情
- `expr active`：查看当前叠加的表情列表

启动默认表情：

- `startup expr <a,b,c>`：保存启动默认表情（逗号分隔）
- `startup show`：查看当前保存的启动默认表情
- `startup clear`：清除启动默认表情

也支持用 URL 参数直接指定（优先级更高）：

- `/?startupExpr=水印,生气`

字幕窗口：

- `quip <text>`：更新字幕窗口（打趣）的显示文字

聊天窗口：

- `/?mode=chat`：打开 AI Chat 窗口，在窗口里直接输入与后台 agent 对话（不走 `quip` 输出接口）

### 1.2 桌宠交互

主窗口默认走“桌宠模式”：

- 鼠标移入：逐渐淡出，并切换为点穿透（不挡鼠标）
- 按住 Ctrl 悬停：保持可交互（用于拖拽/缩放等）

### 1.3 字幕窗口（打趣）

新增一个独立的透明置顶窗口（`/?mode=quip`），用于显示“打趣/吐槽”的话语：

- 背景透明、白字
- 鼠标移入：整体逐渐变透明，并切换为点穿透（点击可穿透到下层窗口）
- 按住 Ctrl 悬停：恢复可交互（可拖拽/缩放）
- 右上角 `-`：最小化窗口

### 1.4 聊天窗口（AI Chat）

新增一个专门用于与后台 AI agent 对话的窗口（`/?mode=chat`），目标是“近似原生命令行”的聊天体验：

- 回显区 + 多行输入
- 快捷键：Enter 发送、Shift+Enter 换行、↑/↓ 历史、Ctrl+L 清屏
- 输出走独立接口：IPC `agent:chat`（与字幕窗口 `quip:*` 分离）

接入方式（可替换真实 agent）：

- 主进程会读取环境变量 `AI_AGENT_ENDPOINT`
- 若存在则 `POST` JSON `{ prompt, context }` 调用你的 HTTP 服务，并把结果回显到聊天窗口
- 若不存在则使用占位 agent（保证 UI 可用）

---

## 2. 中间踩过的坑（V0.5.2）

### 2.1 `expr add xxx` 失败：实际上走到了旧的单表情逻辑

现象：

- `expr add 水印` 返回 `expression failed`
- 但 `expr 水印` 返回 `expression set`

根因：

- 命令解析仍按旧版：`expr <id>` / `expr reset`
- `add` 会被当成“表情名”传入，导致设置失败

解决：

- 把 `expr` 命令升级为子命令：`add/remove/clear/active`
- 同时保持兼容：`expr <id>` 作为 “set-only” 的快捷写法

可复用结论：

- CLI 这类“字符串命令”最容易因为回退/合并冲突把能力悄悄抹掉；建议把 `help` 输出当成冒烟测试的一部分

### 2.2 多表情叠加的实现坑：默认行为会把旧表情 fade out

背景：

- `pixi-live2d-display` 的 Cubism4 表情实现本质是 expression motion queue
- 默认 `startMotion` 会让“当前队列里的 motion”启动 fade out，从而表现为“只能保留一个表情”

解决策略（本项目 V0.5.2 的做法）：

- 针对 Cubism4 的 `expressionManager.queueManager.startMotion` 做“叠加启动”适配：
  - 启动新表情时，临时屏蔽队列中已有 motion 的 `setFadeOut` 调用
  - 从而避免启动新表情时把旧表情 fade out

可复用结论：

- “看起来像表情系统”的 API，底层可能仍是 motion queue；要叠加就要先搞清楚队列策略

### 2.3 点穿透后 `pointerleave` 不可靠，容易出现“透明状态卡住”

现象：

- 开启点穿透后，渲染侧可能收不到 `pointerleave`
- 导致状态机误以为鼠标仍在窗口内，从而一直维持透明/点穿透状态

解决：

- 主进程提供“光标是否在窗口 bounds 内”的查询（使用屏幕坐标 + `win.getBounds()`）
- 渲染进程在淡出/点穿透期间轮询该查询，离开则强制恢复

可复用结论：

- 只靠 DOM 事件做 hover 状态，在点穿透场景下是不够的，需要主进程兜底

### 2.4 点穿透与窗口按钮的矛盾：要“点穿透”就不能点击窗口内控件

现象：

- 需求上希望“窗口可点击穿透到下层”，同时窗口右上角还要能点 `-` 最小化

原因：

- Electron 的 OS 级点穿透依赖 `BrowserWindow.setIgnoreMouseEvents(true)`
- 一旦启用，窗口将拿不到任何 click 事件，窗口内按钮自然也无法点击

本项目在 V0.5.2 的取舍：

- 默认悬停时点穿透
- **按住 Ctrl 才恢复可交互**，此时才可以点击 `-` 或拖拽/缩放窗口

### 2.5 “打趣输出”与“专业输出”必须分离，否则体验会很混乱

原因：

- 字幕窗口更偏“氛围与打趣”，需要短句、强可读性，且要遵循点穿透/透明展示规则
- 聊天窗口需要“专业输出”，更长、更结构化，且要支持快捷键/历史/多行输入

本项目的做法：

- 字幕窗口使用 `quip:setText`（单向推送，显示用）
- 聊天窗口使用 `agent:chat`（请求-响应，专业输出用）

---

## 3. 用到了什么技术（V0.5.2）

- Electron：透明置顶无边框窗口；点穿透（`setIgnoreMouseEvents` + `forward`）；主进程判定光标是否在窗口内
- Electron 多窗口：主窗口（Live2D）+ 控制台窗口（CLI）+ 字幕窗口（打趣）
- Electron 多窗口（扩展）：新增聊天窗口（AI Chat）
- Vue 3 + Vite：渲染进程 UI 与开发/构建
- PixiJS + pixi-live2d-display：Live2D 渲染与通用控制（motion/expression/focus/tap）
- IPC 请求-响应桥：控制台窗口 → 主进程 → 主窗口；带 requestId 与超时
- IPC 单向转发：任意窗口 → 主进程 → 字幕窗口（推送 quip 文本）
- IPC 请求-响应：聊天窗口 → 主进程（agent:chat）→ 返回专业输出
- LocalStorage + URL 参数：保存并覆盖“启动默认表情”配置

---

## 4. 从这里继续写

（下一版本从这里开始追加：例如 V0.5.3…）
