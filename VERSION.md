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

---

## V0.5.5（2026-04-30）

本版本聚焦于“全局鼠标追踪（跨窗口/跨应用）让模型头部/视线跟随”的稳定性与可维护性。

### 1. 现象回顾：链路通了，但“看起来不跟”

在 V0.5.4（开发中间态）阶段，已经做到：

- 主进程能持续获取系统鼠标位置并通过 IPC 推送
- 渲染进程能持续收到 `mouseTrack:point`

但模型表现仍可能“几乎不动”，给人的观感像是追踪失效。

### 2. 根因：把 `focus/drag` 的坐标系理解错了

`pixi-live2d-display` 的 `Live2DModel.focus(x, y)` / `drag(x, y)` 接口，期望输入通常是 **渲染画布/舞台的像素坐标（PIXI 全局坐标）**，库内部会把像素坐标换算到模型可用的参数空间。

而此前我们传入的是 **归一化坐标（[-1, 1]）**。这会导致：

- 库内部把“极小的数值”当成“靠近左上角的像素点”
- 结果就是模型变化幅度极小（肉眼看起来像没动）

### 3. 解决：统一改为窗口相对像素坐标 + 渲染侧直接喂给模型

改动点：

- 主进程（全局采样）发送：`screen -> window client` 的像素坐标（允许鼠标在窗口外时为负或超出窗口范围），并附带窗口尺寸用于调试。
- 渲染进程（模型驱动）每帧同时调用：
  - `model.drag(x, y)`（更偏头/身体，效果更明显）
  - `model.focus(x, y)`（更偏眼睛/视线）

可复用结论：

- 排查“追踪不动”时，优先确认“数据链路”还是“坐标系/单位”问题
- 对第三方图形库：`focus/drag` 这类接口更可能吃“像素坐标”，不要想当然按 [-1,1] 传

### 4. 调试与噪声日志

- 增加 `MOUSETRACK_DEBUG=1` 的主/渲染侧节流日志，便于确认：启用信号、点位接收频率、模型是否在 apply。
- 观察到 AMD 驱动在 Chromium/DirectComposition 路径会输出：
  - `AMD VideoProcessorGetOutputExtension failed (0x80070057)`
  这类日志通常是 GPU 管线告警/刷屏，和“鼠标追踪链路是否通”不是同一个问题。
- 提供可选环境变量开关（默认不启用，避免影响 WebGL/Live2D）：
  - `ELECTRON_DISABLE_DCOMP=1`
  - `ELECTRON_FORCE_ANGLE=opengl|d3d11|...`

---

## V0.5.6（2026-05-02）

本版本聚焦于“后端（AI agent）可通用控制 Live2D”，并降低“换模型后动作/表情不可用”的概率。

### 1. 新增：本地 WebSocket 控制入口

- 默认地址：`ws://127.0.0.1:23333`
- 环境变量：`LIVE2D_WS_HOST` / `LIVE2D_WS_PORT`
- 支持 op：
  - `status`：查询当前模型/状态摘要
  - `list`：列出可用动作/表情（返回 action id）
  - `play`：播放动作/表情（按 action id）
  - `stop`：停止（按类型）

### 2. 重构：统一为 Action ID（file-first）

核心目的：对外只暴露稳定、可序列化的 id，减少对 `model3.json` 是否完整声明的依赖。

- expression 示例：
  - `expr/@name/<Name>`：按声明名
  - `expr/<file.exp3.json>`：按文件（兜底）
- motion 示例：
  - `motion/@group/<Group>/<Index>`：按组与序号
  - `motion/<file.motion3.json>`：按文件（兜底）

CLI 与 WS 均共用同一套 `list/play/stop/status` 逻辑，`list` 输出的 action id 可直接用于 `play`。

### 3. 新增：表情通用标签映射（`tag:`）

AI agent 通常只会说“开心/生气/难过/疑惑”等少量通用词，本项目支持把 `tag:<通用标签>` 映射到真实表情 action id。

- 映射文件：JSONC（支持 `//` 注释）
- 优先级：
  1) 与当前 `*.model3.json` 同目录：`expression-map.jsonc`（推荐每模型一份）
  2) 全局兜底：`public/live2d/expression-map.jsonc`
- value 规则：
  - 字符串：直接指定目标 action id
  - 字符串数组：随机选择一个候选
  - `null`：禁用该 tag

调用示例：

- WS：`{"op":"play","type":"expression","id":"tag:开心"}`
- CLI：`expr tag:开心`
- startup：也支持 `tag:`（例如 `/?startupExpr=tag:开心,tag:害羞`）

### 4. 变更：启动默认表情作为 pinned 底层

常见用法是把“去水印”表情设置为启动默认表情。本版本将启动默认表情视为 pinned（底层基础表情）：

- 后续执行 `expr <...>` / WS `mode:set` 只会清除非 pinned 的表情，不会把 pinned 覆盖掉
- 适合用来长期保持“去水印”等基础效果，再叠加其他临时表情

### 5. 优化：淡化触发更灵敏

针对“鼠标快速进入窗口时，偶发无法触发淡化”的情况：

- 增强 hover 兜底：通过主进程轮询“光标是否在窗口 bounds 内”判定进入/离开，降低 `pointerenter/pointerleave` 偶发丢失带来的影响

### 6. 优化：后端接口与转发性能

- WS `list` 支持可选 `type=expression|motion` 过滤，减少不必要的数据传输（不影响旧客户端）
- 主进程 `requestLive2DApi` 的超时计时器在收到响应后会及时清理，降低长期运行的定时器堆积风险

---

## V0.6.0（2026-05-02）

本版本聚焦于“无边框透明窗口的拖拽/缩放可用性”，并修正由 `-webkit-app-region: drag` 带来的交互吞事件问题。

### 1) 变更：移除 Windows 原生 thickFrame 边框

- 主窗口不再启用 `thickFrame`，避免窗口内容与外部之间出现一圈“系统边框/虚化边框”。
- 缩放能力改为完全依赖渲染层的透明热区 + 主进程 `setBounds` 手动缩放链路。

### 2) 优化：缩放热区显著加大（更容易点中）

- 四边与四角的缩放热区增大，降低“无边框 + 透明背景”导致的命中困难。
- 缩放热区强制 `no-drag`，避免被拖拽区域覆盖后无法触发。

### 3) 变更：拖拽区域收敛为中间 75%

- 仅在按住 Ctrl 进入可交互时启用拖拽。
- 拖拽区域限定为窗口中间 75%（上下左右各留边距），避免拖拽区干扰右上角按钮与角落缩放。

### 4) UI：右上角退出按钮改为红色“×”

- 退出按钮使用红色叉叉样式，并强制 `no-drag`，确保点击事件可达。

### 5) UI：字幕窗口（quip）文本自动换行

- quip 文本支持长句自动换行，并对长串无空格文本进行强制断行，避免文字超出窗口范围。

---

（下一版本从这里开始追加：例如 V0.5.7…）

---

## V0.6.5（2026-05-13）

本版本包含两部分：

1) AI Chat 富文本显示器（Markdown / KaTeX / 代码高亮）的依赖与渲染链路说明
2) 主窗口（透明无边框）在 Ctrl 交互态下的“整体窗口闪动/闪烁”与拖拽链路稳定性修复

### 1) 富文本显示器（AgentChat）更新

更新了什么：

- AI Chat 支持富文本输出：Markdown、KaTeX 数学公式、代码块语法高亮。
- 代码高亮使用 `highlight.js`，并明确“安装自动下载”的依赖方式。

怎么更新的：

- `highlight.js` 作为标准前端依赖声明在 `package.json`，锁定在 `pnpm-lock.yaml`，执行 `pnpm install` 会自动下载（不需要额外的下载脚本/配置）。
- 渲染侧（`src/components/AgentChat.vue`）使用 `highlight.js/lib/core` + 按需语言包注册，并引入主题 CSS（例如 `github-dark.css`）。

遇到的问题：

- 需求是“install 时直接下载下来”：最初容易以为要加“安装脚本”，但实际上只要作为依赖声明并锁定版本，包管理器就会在 install 阶段自动完成下载。

### 2) 整体窗口闪动（Ctrl 交互态 + 拖拽）更新

更新了什么：

- drag-zone（中间 75% 区域）不再使用 `-webkit-app-region: drag` 覆盖层，改为 renderer → main 的手动拖拽（IPC + `setBounds`）。
- 修复“按住 Ctrl 拖动窗口 → 松开 Ctrl 后窗口黏住鼠标”的问题，并在拖拽期间禁止淡出/点穿透，避免“露出网页”。
- 增加多处兜底 stop，确保任何情况下主进程拖拽定时器必停。

遇到的问题（根因）：

- 闪动/闪烁：透明无边框窗口中，`-webkit-app-region: drag` 覆盖层会干扰/吞掉 pointer 事件与 modifier（Ctrl）状态，导致 hover/Ctrl 判定抖动，从而触发交互层反复切换。
- 黏住鼠标 + 露出网页：拖拽中松开 Ctrl 触发交互态退出，拖拽层卸载导致 `pointerup` 丢失；主进程拖拽定时器持续 `setBounds`，表现为“窗口跟随鼠标”；同时渲染层淡出并启用点穿透后，会露出底层网页。

补充：窗口闪烁的另一个根因（cursor 轮询与 Ctrl 交互态打架）：

- `src/App.vue` 的 `startCursorPoll()` 会以约 80ms 频率轮询 `window:isCursorOver`（主进程基于 bounds 的兜底 hover 判断）。
- 在 Ctrl 按住的交互态下，`pointermove` 会持续把 `isHoveringWindow/isCtrlHeld` 维持为 `true`；但轮询偶发返回 `over=false` 时又会把 `isHoveringWindow=false`、`isCtrlHeld=false` 置回去。
- 于是 UI（边框提示/按钮）会在“poll → pointermove”之间来回翻转，表现为高频闪烁。

怎么更新的（实现方案）：

- Renderer（`src/App.vue`）：
  - drag-zone 用 `pointerdown/pointerup/pointercancel` 驱动开始/结束；`pointerdown` 中 `setPointerCapture` 并发送 `window:manualDragStart`，结束时发送 `window:manualDragEnd`。
  - 拖拽期间强制“不淡出/不点穿透”，并保证拖拽进行中 drag-zone 不会因为 Ctrl 松开而卸载（确保能收到结束事件）。
  - 全局兜底：捕获阶段监听 `pointerup/pointercancel/blur`，强制 stop（防止丢事件/失焦）。

- Main（`electron/main.ts`）：
  - `window:manualDragStart` 记录 `startBounds/startCursor`，`setInterval(16ms)` 读取 cursor delta 计算 `nextBounds` 并 `win.setBounds(nextBounds)`。
  - 拖拽开始时强制 `win.setIgnoreMouseEvents(false)`，防止拖拽过程中进入点穿透造成事件链中断。
  - `window:manualDragEnd` 与兜底 stop 会清理 interval 与状态，避免残留“窗口跟随鼠标”。

- Cursor 轮询优化（状态机层面）：
 - 闪烁根因：
 - `App.vue` 里 `startCursorPoll()` 会一直跑（80ms 级别轮询 `window:isCursorOver`）。
当你按住`Ctrl` 进入交互态时，`pointermove` 会不断把 `isHoveringWindow/isCtrlHeld` 维持为 `true`；但轮询偶发判定 `over=false` 时又会把 `isHoveringWindow=false`、`isCtrlHeld=false` 置回去。
于是 UI（角标/按钮）在 “`poll → pointermove`” 之间来回翻转，就表现为高频闪烁。
 - 修复思路：
  - 轮询只在“淡出/点穿透（`shouldFade=true`）”期间启用（因为这时可能收不到稳定的 `pointerleave`）。
  - Ctrl 按住的交互态（`shouldFade=false`）应完全依赖 pointer 事件，不让轮询参与，避免把 `isHoveringWindow/isCtrlHeld` 抖动回 `false`。
  - 修复思路： `syncCursorPollState()`，在每次 `syncPassthroughState()` 切换点穿透后同步 start/stop；并在 `startCursorPoll()` tick 中检测 `shouldFade` 变为 `false` 时立即 stop。
  - 具体实施：在 `App.vue` 新增 `syncCursorPollState()`：
`shouldFade=true` 才 `startCursorPoll()`
否则 `stopCursorPoll()`
`startCursorPoll()` 的 `tick` 里也加了保护：一旦 `shouldFade` 变为 `false` 立刻停止轮询。
`syncPassthroughState()` 每次切换点穿透状态后会同步轮询开关。
`onMounted` 不再无条件 `startCursorPoll()`，改为 `syncCursorPollState()`。

涉及文件：

- `src/components/AgentChat.vue`
- `src/App.vue`
- `electron/main.ts`
- `package.json` / `pnpm-lock.yaml`
