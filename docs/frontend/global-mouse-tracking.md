# 全局鼠标追踪（跨窗口/跨应用）让人物头部跟随鼠标：方案与修改思路

目标：让 Live2D 主窗口中的人物头部/视线跟随鼠标移动，即使鼠标在其他窗口、甚至在其他应用上。

本项目现状（简述）：

- 渲染进程（`src/App.vue`）目前通过 `focus <x> <y>` 命令可调用 `currentModel.focus(x, y, instant)`。
- 主进程（`electron/main.ts`）已有 `window:isCursorOver`，能在点穿透状态下用 `screen.getCursorScreenPoint()` + `win.getBounds()` 做兜底。

因此，“全局鼠标追踪”最稳的落点是在 **Electron 主进程**：持续读取全局鼠标坐标，然后通过 IPC 推送到主窗口渲染进程，由渲染进程把屏幕坐标映射为 `focus(-1..1)`。

---

## 1. 关键难点与约束

### 1.1 跨应用的“全局鼠标坐标”

- Electron 在主进程可以直接拿到全局鼠标：`screen.getCursorScreenPoint()`。
- 这不依赖窗口焦点，也不依赖是否点穿透。

### 1.2 坐标系映射

主进程拿到的是 **屏幕像素坐标**（多显示器/缩放/DPI 相关）。
渲染进程 `Live2DModel.focus(x, y)` 期望的是 **归一化范围**：$x,y \in [-1, 1]$。

映射思路：

1) 在主进程拿到主窗口 bounds：`win.getBounds()`（屏幕坐标系下的矩形）。
2) 用鼠标屏幕坐标转成窗口内归一化：

- 先得到窗口内像素坐标：
  - `localX = cursorX - bounds.x`
  - `localY = cursorY - bounds.y`
- 再映射到 `[-1, 1]`：
  - `x = (localX / bounds.width) * 2 - 1`
  - `y = (localY / bounds.height) * 2 - 1`
- Live2D 通常希望“向上为正”，但屏幕坐标是向下为正：
  - `y = -y`

3) 鼠标在窗口外的情况：

- 方案 A（更自然）：仍然计算，但对 `x/y` 做 clamp 到 `[-1, 1]`，让视线在边缘“跟着窗外方向”。
- 方案 B（更保守）：鼠标不在窗口内就停止更新或缓慢回正。

建议默认用 A（体验更像“跟随外界”）。

### 1.3 性能与抖动

- 主进程轮询频率不宜太高，建议 30~60Hz。
- 渲染进程不要每次都 `focus(..., instant=false)` 造成过度插值抖动；可以：
  - 主进程节流（例如 30Hz）
  - 渲染端再做一层低通滤波/lerp（可选）

### 1.4 与现有“点穿透/悬停淡出”共存

- 当前项目在淡出时启用 `setIgnoreMouseEvents(true, { forward: true })`。
- 全局鼠标追踪不依赖 DOM `pointermove`，因此不会被点穿透打断。

---

## 2. 推荐方案（主进程轮询 + IPC 推送）

### 2.1 主进程：新增一个“全局鼠标追踪服务”

在 `electron/main.ts`：

- 新增状态：
  - `let trackingTimer: NodeJS.Timeout | null = null`
  - `let trackingEnabled = false`
- 新增 IPC 控制：
  - `ipcMain.on('mouseTrack:setEnabled', (event, enabled:boolean) => ...)`
- 轮询逻辑（核心 API）：
  - `screen.getCursorScreenPoint()`
  - `mainWindow.getBounds()`
  - 计算 `x/y` 并发送给主窗口：
    - `mainWindow.webContents.send('mouseTrack:point', { x, y, inWindow, screenX, screenY })`

频率建议：`33ms`（约 30fps）起步。

### 2.2 渲染进程：接收并驱动 Live2D focus

在 `src/App.vue`（主窗口模式）中：

- 监听事件：
  - `ipcRenderer.on('mouseTrack:point', (_evt, payload) => { ... })`
- 当 `currentModel` ready 后：
  - `currentModel.focus(payload.x, payload.y, false)`

注意：

- 仅在 Live2D 主窗口启用（`mode` 不是 `cli/chat/quip`）。
- 可以加开关：例如 URL `?trackMouse=1` 或 localStorage。

---

## 3. 替代方案（不推荐 / 有额外代价）

### 3.1 OS 级低层 Hook（Windows API）

- 需要 native module（Node-API / node-gyp）或第三方库，构建复杂、签名/杀软误报风险更高。
- Electron 自带的 `screen.getCursorScreenPoint()` 已经能拿到全局鼠标，因此通常没必要。

### 3.2 仅在窗口内跟随（渲染端 pointermove）

- 简单，但无法满足“鼠标在其他窗口也跟随”。

---

## 4. 具体修改点清单（落地指南）

### 4.1 `electron/main.ts`

新增：

- `mouseTrack:setEnabled`（开关追踪）
- 轮询 timer（30Hz）
- 推送事件：`mouseTrack:point`

输出 payload 建议：

```ts
type MouseTrackPoint = {
  x: number // [-1,1]
  y: number // [-1,1]
  inWindow: boolean
  screenX: number
  screenY: number
}
```

### 4.2 `src/App.vue`

新增：

- `isMainLive2DMode` 判断（排除 cli/chat/quip）
- `ipcRenderer.on('mouseTrack:point', ...)`
- 对 `x/y` 做 clamp & 可选平滑

建议顺序：

- 模型加载完成后再开始处理事件（避免 `currentModel` 为空）。

---

## 5. 可选增强（体验更像“头跟鼠标”）

1) **回正策略**：鼠标长时间不动或离开窗口很远时，慢慢回正（`x/y` → 0）。
2) **速度限制**：限制每帧最大变化量，避免瞬移。
3) **只驱动头/眼**：如果库支持更细粒度参数（如 ParamAngleX/Y、ParamEyeBallX/Y），可以更拟真。
   - 但这会失去“通用性”（不同模型参数命名可能不同）。

---

## 6. 风险与验证

- 多显示器/高 DPI：`screen.getCursorScreenPoint()` 与 `win.getBounds()` 都在同一屏幕坐标系，通常可直接相减；但建议实际在多显示器环境跑一次。
- 频率过高导致 CPU 占用：先 30Hz，必要时再提高。

自测清单：

1) `pnpm dev` 启动后，鼠标移到其他应用窗口上，人物头部仍会跟随方向变化。
2) 调整主窗口大小、移动到不同显示器，跟随仍正常。
3) 点穿透/淡出状态下仍能跟随（不依赖 DOM 事件）。

---

## 7. 建议的最小可用实现（MVP）

- 主进程 30Hz 轮询 `screen.getCursorScreenPoint()`
- 用主窗口 bounds 映射 `focus(-1..1)`
- IPC 推送到渲染端，渲染端直接 `currentModel.focus(x, y, false)`

MVP 先跑通后再做平滑/回正等体验优化。
