# Project Health Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all project health issues: repo pollution, .gitignore gaps, and monolithic frontend file refactoring.

**Architecture:** Three phases — (1) clean up repo pollution and fix .gitignore, (2) decompose `electron/main.ts` (1417 lines) into 5 focused modules, (3) decompose `src/App.vue` (2052 lines) into 4 composables, (4) decompose `src/components/AgentChat.vue` (1698 lines) into 3 composables + 2 sub-components. Each extraction is verified by running `pnpm build` after each task.

**Tech Stack:** Vue 3 Composition API, Vite 8, Electron 41, TypeScript 6, PixiJS 6, pnpm

> **Refactoring note:** Code blocks with `// ... (from App.vue line N)` mean "copy the exact existing code verbatim from the specified location". This is a pure structural decomposition — no logic changes, no new features, no bug fixes.

## Global Constraints

- Package manager: `pnpm` (never npm/yarn)
- Build verification: `pnpm build` must pass after each task (runs `vue-tsc -b && vite build`)
- No functional changes during refactoring — pure structural decomposition
- Conventional commits format: `type(scope): description`
- All new files use TypeScript strict mode (inherit from `tsconfig.app.json`)
- Composables follow Vue 3 `use`-prefix naming convention
- Electron main-process modules are plain `.ts` files (not Vue)
- Keep all existing behavior byte-identical after refactoring

---

## File Structure

### Phase 1: Repo Cleanup
| Action | File | Reason |
|--------|------|--------|
| Delete | `$null` | PowerShell redirect artifact |
| Delete | `scripts/tmp_create_ports.py` | Empty temp file |
| Delete | `package-lock.json` | Stale npm lock (project uses pnpm) |
| Modify | `.gitignore` | Add LaTeX artifacts, global `__pycache__/`, paper outputs |

### Phase 2: Electron Main Process Decomposition
| Action | File | Responsibility |
|--------|------|----------------|
| Create | `electron/types.ts` | All shared types and interfaces |
| Create | `electron/windows.ts` | Window creation (main, console, chat) + showAndFocus |
| Create | `electron/backend-bridge.ts` | Agent endpoint resolution, workspace sync, message polling, dispatch |
| Create | `electron/window-manipulation.ts` | Manual resize/drag state management, bounds computation |
| Create | `electron/vision.ts` | Screenshot capture loop |
| Modify | `electron/main.ts` | Slim orchestrator: imports modules, registers IPC, manages lifecycle |

### Phase 3: App.vue Decomposition
| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/composables/useLive2DModel.ts` | Model loading, PixiJS app, Cubism runtime, expression/motion playback, metadata |
| Create | `src/composables/useLive2DCommands.ts` | CLI command parser + executor (`executeLive2DCommand` and helpers) |
| Create | `src/composables/useWindowInteraction.ts` | Hover fade, click-through, manual resize/drag (renderer side), cursor polling |
| Create | `src/composables/useAppControls.ts` | closeApp, openLive2DConsole, openAIChat, toggleDevTools |
| Modify | `src/App.vue` | Thin shell: imports composables, template, styles |

### Phase 4: AgentChat.vue Decomposition
| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/composables/useMarkdownRenderer.ts` | hljs setup, MarkdownIt config, LaTeX normalization, render functions |
| Create | `src/composables/useAgentMessages.ts` | IPC message handlers (chat/error/status/quip/expression), throttling |
| Create | `src/composables/useChatOperations.ts` | Session management, send prompt, submit, workspace, history |
| Create | `src/components/ChatMessageList.vue` | Message rendering template (bubble, file action card, typewriter) |
| Create | `src/components/ChatInputArea.vue` | Auto-resize textarea, history navigation, keyboard shortcuts |
| Modify | `src/components/AgentChat.vue` | Thin shell: imports composables + sub-components, header layout |

---

## Phase 1: Repo Cleanup

### Task 1: Remove Pollution Files

**Files:**
- Delete: `$null`
- Delete: `scripts/tmp_create_ports.py`
- Delete: `package-lock.json`

- [ ] **Step 1: Verify the files exist**

```bash
ls -la '$null' scripts/tmp_create_ports.py package-lock.json
```

Expected: all three files listed with sizes.

- [ ] **Step 2: Delete the files**

```bash
rm '$null'
rm scripts/tmp_create_ports.py
rm package-lock.json
```

- [ ] **Step 3: Verify deletion**

```bash
ls '$null' 2>/dev/null; ls scripts/tmp_create_ports.py 2>/dev/null; ls package-lock.json 2>/dev/null
echo "exit: $?"
```

Expected: no output, exit code 0 (files gone).

- [ ] **Step 4: Verify pnpm still works without package-lock.json**

```bash
pnpm install --frozen-lockfile
```

Expected: installs from `pnpm-lock.yaml` without errors. If it complains about frozen-lockfile, run `pnpm install` instead to verify the lock is intact.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove repo pollution (null artifact, temp script, stale npm lock)"
```

---

### Task 2: Fix .gitignore

**Files:**
- Modify: `.gitignore`

Current `.gitignore` already covers: `node_modules`, `dist`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `workspace/`, `dist-electron/`.

Missing rules to add:
- LaTeX build artifacts (`*.aux`, `*.bbl`, `*.blg`, `*.log`, `*.out`)
- `paper/output/*.pptx` (presentation build outputs)
- Global `__pycache__/` (already present but verify scope)
- `paper/scripts/__pycache__/` (covered by global rule)
- Root-level junk (`$null`)

- [ ] **Step 1: Read current .gitignore**

```bash
cat .gitignore
```

- [ ] **Step 2: Append new rules**

Add the following block at the end of `.gitignore`:

```gitignore
# LaTeX build artifacts (paper/)
paper/**/*.aux
paper/**/*.bbl
paper/**/*.blg
paper/**/*.log
paper/**/*.out
paper/**/*.toc
paper/**/*.lof
paper/**/*.lot
paper/**/*.fls
paper/**/*.fdb_latexmk
paper/**/*.synctex.gz
paper/main.pdf

# Presentation build outputs
paper/output/*.pptx

# Python bytecode (global)
__pycache__/
*.pyc

# PowerShell artifacts
$null
```

- [ ] **Step 3: Verify gitignore takes effect**

```bash
git check-ignore -v paper/main.aux paper/main.pdf paper/output/presentation_v3.pptx '$null'
```

Expected: each file matched by one of the new rules.

- [ ] **Step 4: Check that no tracked files are accidentally ignored**

```bash
git ls-files --cached | git check-ignore --stdin
```

Expected: empty output (no tracked files match new rules).

- [ ] **Step 5: Commit**

```bash
git add .gitignore
git commit -m "chore: expand .gitignore for LaTeX artifacts, paper outputs, PS junk"
```

---

## Phase 2: Electron Main Process Decomposition

The current `electron/main.ts` (1417 lines) will be split into 5 new modules + a slim orchestrator.

Dependency graph (arrows = "imports from"):

```
main.ts → types.ts
       → windows.ts → types.ts
       → backend-bridge.ts → types.ts
       → window-manipulation.ts
       → vision.ts
```

### Task 3: Extract Shared Types (`electron/types.ts`)

**Files:**
- Create: `electron/types.ts`
- No modifications to `electron/main.ts` yet (types will be re-exported from main.ts initially)

This task extracts all type definitions that other modules will import.

- [ ] **Step 1: Create `electron/types.ts`**

```typescript
// electron/types.ts

// --- Agent message types ---

export type QuipMessage = {
  type: 'quip'
  content: string
  node_name: string
  timestamp: string
  event_type?: string
  event_source?: string
  event_stage?: string
  metadata?: {
    priority: 'low' | 'medium' | 'high'
    duration?: number
    node_label?: string
    phase?: string
    runtime_event?: string
  }
}

export type ExpressionMessage = {
  type: 'expression'
  expression: string
  intensity?: number
  node_name: string
  timestamp: string
  metadata?: {
    duration?: number
    transition?: 'smooth' | 'instant'
  }
}

export type ChatMessage = {
  type: 'chat'
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  metadata?: {
    is_partial: boolean
    sequence_id?: number
    total_parts?: number
    node_name?: string
  }
}

export type ErrorMessage = {
  type: 'error'
  code: string
  message: string
  details?: any
  timestamp: string
  node_name?: string
}

export type StatusUpdate = {
  type: 'status'
  status: 'idle' | 'running' | 'paused' | 'done' | 'error' | 'cancelled'
  progress?: number
  node_name?: string
  timestamp: string
  event_type?: string
  event_source?: string
  event_stage?: string
  metadata?: {
    node_label?: string
    phase?: string
    runtime_event?: string
    action_name?: string
    action_label?: string
    action_status?: 'started' | 'completed' | 'failed'
    action_category?: string
    safety_level?: string
    requires_confirmation?: boolean
  }
}

export type AgentMessage = QuipMessage | ExpressionMessage | ChatMessage | ErrorMessage | StatusUpdate

export type AgentMessageEnvelope = AgentMessage & {
  _id?: string
  _channel?: string
  _timestamp?: string
}

export type BackendMessagesResponse = {
  ok?: boolean
  messages?: unknown[]
  count?: number
}

// --- Live2D API types ---

export type Live2DCommandResponse = { ok: boolean; output: string }

export type Live2DApiRequest =
  | { op: 'status' }
  | { op: 'list'; type?: 'expression' | 'motion' }
  | { op: 'stop' }
  | { op: 'play'; type: 'expression' | 'motion'; id: string; mode?: 'set' | 'add' }

export type Live2DApiResponse = { ok: boolean; data?: any; error?: string }

// --- Agent chat types ---

export type AgentChatRequest = {
  prompt: string
  context?: string
  sessionId?: string
}

export type AgentChatResponse = {
  ok: boolean
  output: string
  error?: string
  run_id?: string | null
  session_id?: string
  content_type?: 'plain_text' | 'markdown'
  render_mode?: 'plain_text' | 'rich_text'
}

// --- Sidecar types ---

export type SidecarFilesResponse = {
  ok: boolean
  expressions: string[]
  motions: string[]
  error?: string
}

// --- Window manipulation types ---

export type ManualResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

export type ManualResizeState = {
  dir: ManualResizeDir
  startBounds: Electron.Rectangle
  startCursor: { x: number; y: number }
  minW: number
  minH: number
  timer: NodeJS.Timeout
  lastBoundsKey: string
}

export type ManualDragState = {
  startBounds: Electron.Rectangle
  startCursor: { x: number; y: number }
  timer: NodeJS.Timeout
  lastBoundsKey: string
}

// --- Workspace state ---

export type WorkspaceState = { path: string }
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
npx tsc --noEmit electron/types.ts --target ES2022 --module ESNext --moduleResolution bundler --skipLibCheck 2>&1 | head -5
```

Expected: no errors (or only errors about `Electron.Rectangle` which is fine since it needs the electron types at build time).

- [ ] **Step 3: Commit**

```bash
git add electron/types.ts
git commit -m "refactor(electron): extract shared types to electron/types.ts"
```

---

### Task 4: Extract Window Creation (`electron/windows.ts`)

**Files:**
- Create: `electron/windows.ts`
- Test: `pnpm build` succeeds

This module encapsulates the three BrowserWindow factory functions. They currently share mutable references (`mainWindow`, `consoleWindow`, `chatWindow`) which are passed in via a `WindowSet` object.

- [ ] **Step 1: Create `electron/windows.ts`**

Extract from `electron/main.ts` lines 254–400 (`createWindow`, `showAndFocus`, `createConsoleWindow`, `createChatWindow`).

```typescript
// electron/windows.ts
import { app, BrowserWindow } from 'electron'
import path from 'node:path'

export type WindowSet = {
  mainWindow: BrowserWindow | null
  consoleWindow: BrowserWindow | null
  chatWindow: BrowserWindow | null
}

export function showAndFocus(win: BrowserWindow) {
  if (win.isDestroyed()) return
  if (!win.isVisible()) win.show()
  if (win.isMinimized()) win.restore()
  win.focus()
}

export function createMainWindow(set: WindowSet): void {
  // ... (copy body of createWindow from main.ts lines 254–315)
  // Assign to set.mainWindow instead of module-level variable
}

export function createConsoleWindow(set: WindowSet): void {
  // ... (copy body from main.ts lines 324–361)
  // Assign to set.consoleWindow instead of module-level variable
}

export function createChatWindow(set: WindowSet): void {
  // ... (copy body from main.ts lines 363–400)
  // Assign to set.chatWindow instead of module-level variable
}
```

Key changes from original:
- Replace module-level `mainWindow`/`consoleWindow`/`chatWindow` references with `set.mainWindow`/`set.consoleWindow`/`set.chatWindow`
- The `mouseTrackDebug` flag and `did-fail-load` handler move with `createMainWindow`
- The `consoleWindow.on('closed')` and `chatWindow.on('closed')` callbacks set `set.consoleWindow = null` / `set.chatWindow = null`

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add electron/windows.ts
git commit -m "refactor(electron): extract window creation to electron/windows.ts"
```

---

### Task 5: Extract Backend Bridge (`electron/backend-bridge.ts`)

**Files:**
- Create: `electron/backend-bridge.ts`

This module encapsulates all backend integration: endpoint resolution, workspace sync, message polling/dispatch, and the polling bridge lifecycle.

- [ ] **Step 1: Create `electron/backend-bridge.ts`**

Extract from `electron/main.ts`:
- Lines 716–806: `getConfiguredAgentEndpoint`, `normalizeBaseUrl`, `resolveAgentBaseUrl`, `resolveAgentMessagesEndpoint`, `fetchBackendWorkspace`, `syncBackendWorkspace`, `parsePositiveIntegerEnv`
- Lines 808–870: `resolveAgentMessageChannel`, `dispatchAgentMessage`, `toAgentMessageEnvelope`
- Lines 867–992: `pollBackendMessagesOnce`, `startBackendMessageBridge`, `stopBackendMessageBridge`

```typescript
// electron/backend-bridge.ts
import type { AgentMessageEnvelope, BackendMessagesResponse, WindowSet } from './types'

export function getConfiguredAgentEndpoint(): string | null {
  // ... (from main.ts line 716)
}

export function normalizeBaseUrl(value: string): string {
  return value.replace(/\/+$/, '')
}

export function resolveAgentBaseUrl(): string | null {
  // ... (from main.ts line 725)
}

export function resolveAgentMessagesEndpoint(): string | null {
  // ... (from main.ts line 746)
}

export async function fetchBackendWorkspace(): Promise<string | null> {
  // ... (from main.ts line 761)
}

export async function syncBackendWorkspace(workspacePath: string): Promise<void> {
  // ... (from main.ts line 778)
}

function parsePositiveIntegerEnv(name: string, fallback: number): number {
  // ... (from main.ts line 801)
}

export function resolveAgentMessageChannel(message: AgentMessageEnvelope): string | null {
  // ... (from main.ts line 808)
}

export function dispatchAgentMessage(message: AgentMessageEnvelope, windows: WindowSet): void {
  // ... (from main.ts line 818)
  // NOTE: takes `windows` parameter instead of closing over module-level vars
}

export function toAgentMessageEnvelope(value: unknown): AgentMessageEnvelope | null {
  // ... (from main.ts line 860)
}

// --- Bridge state ---
let backendBridgeTimer: NodeJS.Timeout | null = null
let backendBridgeInFlight = false
let backendBridgeSinceId: string | null = null
let backendBridgeLastError: string | null = null
let backendBridgeEndpoint: string | null = null

async function pollBackendMessagesOnce(windows: WindowSet): Promise<void> {
  // ... (from main.ts line 905)
  // Uses dispatchAgentMessage(msg, windows)
}

export function startBackendMessageBridge(windows: WindowSet): void {
  // ... (from main.ts line 966)
}

export function stopBackendMessageBridge(): void {
  // ... (from main.ts line 983)
}
```

Key design decision: `dispatchAgentMessage` and `pollBackendMessagesOnce` take a `WindowSet` parameter instead of closing over module-level window variables. This keeps the module decoupled from window lifecycle.

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add electron/backend-bridge.ts
git commit -m "refactor(electron): extract backend bridge to electron/backend-bridge.ts"
```

---

### Task 6: Extract Window Manipulation (`electron/window-manipulation.ts`)

**Files:**
- Create: `electron/window-manipulation.ts`

- [ ] **Step 1: Create `electron/window-manipulation.ts`**

Extract from `electron/main.ts` lines 1219–1417: manual resize/drag state management and bounds computation.

```typescript
// electron/window-manipulation.ts
import { BrowserWindow, screen } from 'electron'
import type { ManualResizeDir, ManualResizeState, ManualDragState } from './types'

const manualResizeDirs = new Set<ManualResizeDir>(['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'])

const manualResizeStateByWinId = new Map<number, ManualResizeState>()
const manualDragStateByWinId = new Map<number, ManualDragState>()

export function stopManualResizeByWinId(winId: number): void {
  // ... (from main.ts line 1242)
}

export function stopManualDragByWinId(winId: number): void {
  // ... (from main.ts line 1249)
}

export function computeResizedBounds(
  start: Electron.Rectangle,
  dir: ManualResizeDir,
  dx: number,
  dy: number,
  minW: number,
  minH: number,
): Electron.Rectangle {
  // ... (from main.ts line 1256)
}

export function handleManualResizeStart(event: Electron.IpcMainEvent, payload: any): void {
  // ... (from main.ts line 1308, the ipcMain.on handler body)
}

export function handleManualResizeEnd(event: Electron.IpcMainEvent): void {
  // ... (from main.ts line 1357)
}

export function handleManualDragStart(event: Electron.IpcMainEvent): void {
  // ... (from main.ts line 1363)
}

export function handleManualDragEnd(event: Electron.IpcMainEvent): void {
  // ... (from main.ts line 1413)
}
```

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

- [ ] **Step 3: Commit**

```bash
git add electron/window-manipulation.ts
git commit -m "refactor(electron): extract window manipulation to electron/window-manipulation.ts"
```

---

### Task 7: Extract Vision Screenshot (`electron/vision.ts`)

**Files:**
- Create: `electron/vision.ts`

- [ ] **Step 1: Create `electron/vision.ts`**

Extract from `electron/main.ts` lines 1030–1088.

```typescript
// electron/vision.ts
import { desktopCapturer } from 'electron'
import path from 'node:path'
import fs from 'node:fs'

const VISION_SCREENSHOT_INTERVAL_MS = parseInt(process.env.VISION_INTERVAL_MS ?? '30000', 10)
const VISION_SCREENSHOT_PATH = path.join(process.cwd(), 'backend', '.tmp_cache', 'vision_screenshots', 'screenshot_latest.png')
let _visionScreenshotTimer: ReturnType<typeof setInterval> | null = null

export function startVisionScreenshotLoop(): void {
  // ... (from main.ts line 1038)
}

export function stopVisionScreenshotLoop(): void {
  // ... (from main.ts line 1051)
}

async function captureAndSaveScreenshot(): Promise<void> {
  // ... (from main.ts line 1059)
}
```

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

- [ ] **Step 3: Commit**

```bash
git add electron/vision.ts
git commit -m "refactor(electron): extract vision screenshot to electron/vision.ts"
```

---

### Task 8: Rewire `electron/main.ts` to Use Extracted Modules

**Files:**
- Modify: `electron/main.ts`

This is the key integration task. Replace the inlined implementations with imports from the new modules.

- [ ] **Step 1: Replace type definitions with imports**

Replace the inline type definitions (lines 30–127) with:

```typescript
import type {
  QuipMessage, ExpressionMessage, ChatMessage, ErrorMessage, StatusUpdate,
  AgentMessage, AgentMessageEnvelope, BackendMessagesResponse,
  Live2DCommandResponse, Live2DApiRequest, Live2DApiResponse,
  AgentChatRequest, AgentChatResponse, SidecarFilesResponse,
  WorkspaceState,
} from './types'
```

- [ ] **Step 2: Replace window creation with imports**

Replace `createWindow`, `createConsoleWindow`, `createChatWindow`, `showAndFocus` (lines 254–400) with:

```typescript
import { createMainWindow, createConsoleWindow, createChatWindow, showAndFocus, type WindowSet } from './windows'
```

Update call sites in `app.whenReady()` and IPC handlers:
- `createWindow()` → `createMainWindow(windows)` where `windows = { mainWindow, consoleWindow, chatWindow }`

- [ ] **Step 3: Replace backend bridge with imports**

Replace lines 716–992 with:

```typescript
import {
  resolveAgentBaseUrl, fetchBackendWorkspace, syncBackendWorkspace,
  dispatchAgentMessage, toAgentMessageEnvelope,
  startBackendMessageBridge, stopBackendMessageBridge,
} from './backend-bridge'
```

- [ ] **Step 4: Replace window manipulation with imports**

Replace lines 1219–1417 with:

```typescript
import {
  stopManualResizeByWinId, stopManualDragByWinId,
  handleManualResizeStart, handleManualResizeEnd,
  handleManualDragStart, handleManualDragEnd,
} from './window-manipulation'
```

Register IPC handlers:

```typescript
ipcMain.on('window:manualResizeStart', (event, payload) => handleManualResizeStart(event, payload))
ipcMain.on('window:manualResizeEnd', (event) => handleManualResizeEnd(event))
ipcMain.on('window:manualDragStart', (event) => handleManualDragStart(event))
ipcMain.on('window:manualDragEnd', (event) => handleManualDragEnd(event))
```

- [ ] **Step 5: Replace vision with imports**

Replace lines 1030–1088 with:

```typescript
import { startVisionScreenshotLoop, stopVisionScreenshotLoop } from './vision'
```

- [ ] **Step 6: Verify `electron/main.ts` line count is significantly reduced**

```bash
wc -l electron/main.ts
```

Expected: ~500-600 lines (down from 1417).

- [ ] **Step 7: Full build verification**

```bash
pnpm build
```

Expected: no errors.

- [ ] **Step 8: Manual smoke test**

```bash
pnpm dev
```

Verify:
- Main window (Live2D) opens and renders
- Console window opens and accepts commands
- Chat window opens and can send/receive messages
- Window resize/drag works via Ctrl+hover
- Close app via X button

- [ ] **Step 9: Commit**

```bash
git add electron/main.ts
git commit -m "refactor(electron): rewire main.ts to use extracted modules"
```

---

## Phase 3: App.vue Decomposition

The current `src/App.vue` (2052 lines) will be decomposed into 4 composables + a slim shell.

Dependency graph:

```
App.vue → useLive2DModel.ts (model, expressions, motions, meta)
       → useLive2DCommands.ts → useLive2DModel.ts (command executor)
       → useWindowInteraction.ts (hover, resize, drag)
       → useAppControls.ts (close, open windows, devtools)
```

### Task 9: Extract Live2D Model Composable (`src/composables/useLive2DModel.ts`)

**Files:**
- Create: `src/composables/useLive2DModel.ts`

This is the largest extraction — the core Live2D model management. Extracts ~700 lines of functions related to:
- Model loading and PixiJS app lifecycle
- Cubism 2/4 runtime loading
- Expression tag maps
- Expression playback (Cubism 4 stacking)
- Motion playback
- Model metadata

- [ ] **Step 1: Create the composable**

```typescript
// src/composables/useLive2DModel.ts
import { computed, ref, type Ref } from 'vue'
import * as PIXI from 'pixi.js'

export type ExpressionTagMapFile = {
  version?: number
  map?: Record<string, string | string[] | null>
}

export type Live2DAction = {
  id: string
  type: 'expression' | 'motion'
  label: string
}

export type ModelMeta = {
  motions: Record<string, number>
  expressions: string[]
  motionFiles?: string[]
  expressionFiles?: string[]
}

export function useLive2DModel(options: {
  defaultModelPath: string
  modelUrl: Ref<string>
  isModel3: Ref<boolean>
}) {
  // --- State ---
  const loadState = ref<'loading' | 'ready' | 'error'>('loading')
  const errorText = ref('')
  let currentModel: any = null
  let currentModelSettingsUrl: string | null = null
  let pixiApp: PIXI.Application | null = null
  let cachedMeta: ModelMeta | null = null
  let metaLoadPromise: Promise<ModelMeta | null> | null = null
  let lastMetaError: string | null = null
  const activeExpressionHandles = new Map<string, any>()
  const pinnedExpressionHandleKeys = new Set<string>()
  let cachedExpressionTagMap: { sourceUrl: string; map: Record<string, string | string[] | null> } | null = null

  // --- All functions from App.vue lines 110-970 ---
  // getCubism4Module, isExpressionActionId, isMotionActionId,
  // makeExpressionNameActionId, actionIdLabel, looksLikeExpressionFile,
  // looksLikeMotionFile, resolveModelRelativeUrl, fetchJsonObject,
  // stripJsonComments, expressionActionIdToHandleKey,
  // fadeOutAndRemoveExpressionHandle, exprClearNonPinned, ...
  // ensureMetaLoaded, buildLive2DActionCatalog, stopAllLive2D,
  // playLive2DAction, loadScriptOnce, ensureRuntimeLoaded,
  // waitForCubismCoreReady, hasCubism4CoreExports

  // --- Returned interface ---
  return {
    loadState,
    errorText,
    currentModel: computed(() => currentModel),
    currentModelSettingsUrl: computed(() => currentModelSettingsUrl),
    activeExpressionHandles,
    pinnedExpressionHandleKeys,
    pixiApp: computed(() => pixiApp),

    // Model lifecycle
    initPixiApp: (canvas: HTMLCanvasElement) => { /* ... */ },
    loadModel: () => { /* ... */ },
    dispose: () => { /* ... */ },

    // Expression/motion
    playLive2DAction: (payload: { type: 'expression' | 'motion'; id: string; mode?: 'set' | 'add' }) => { /* ... */ },
    stopAllLive2D: () => { /* ... */ },
    buildLive2DActionCatalog: () => { /* ... */ },

    // Metadata
    ensureMetaLoaded: (force?: boolean) => { /* ... */ },
    cachedMeta: computed(() => cachedMeta),

    // Runtime
    ensureRuntimeLoaded: () => { /* ... */ },
  }
}
```

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

Expected: no errors (the composable is created but not yet imported by App.vue).

- [ ] **Step 3: Commit**

```bash
git add src/composables/useLive2DModel.ts
git commit -m "refactor(app): extract useLive2DModel composable"
```

---

### Task 10: Extract Live2D Commands Composable (`src/composables/useLive2DCommands.ts`)

**Files:**
- Create: `src/composables/useLive2DCommands.ts`

Extracts `executeLive2DCommand` (lines 1039–1322) and its direct helpers. Depends on `useLive2DModel`.

- [ ] **Step 1: Create the composable**

```typescript
// src/composables/useLive2DCommands.ts
import type { useLive2DModel } from './useLive2DModel'

type Live2DModelHandle = ReturnType<typeof useLive2DModel>

export function useLive2DCommands(model: Live2DModelHandle) {
  // tokenizeCommand (line 819)
  // executeLive2DCommand (line 1039)
  // All CLI sub-command handlers within executeLive2DCommand

  return {
    executeLive2DCommand: async (commandLine: string): Promise<{ ok: boolean; output: string }> => {
      // ... (copy from App.vue line 1039)
    },
  }
}
```

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

- [ ] **Step 3: Commit**

```bash
git add src/composables/useLive2DCommands.ts
git commit -m "refactor(app): extract useLive2DCommands composable"
```

---

### Task 11: Extract Window Interaction Composable (`src/composables/useWindowInteraction.ts`)

**Files:**
- Create: `src/composables/useWindowInteraction.ts`

Extracts hover fade, click-through, manual resize/drag, and cursor polling (lines 38–55, 619–800).

- [ ] **Step 1: Create the composable**

```typescript
// src/composables/useWindowInteraction.ts
import { computed, ref, type Ref } from 'vue'
import type { IpcRendererLike } from '../platform/electronIpc'

export function useWindowInteraction(options: {
  ipcRenderer: IpcRendererLike | null
  isCliMode: Ref<boolean>
  isChatMode: Ref<boolean>
}) {
  const isHoveringWindow = ref(false)
  const isCtrlHeld = ref(false)
  const isManualResizing = ref(false)
  const isManualDragging = ref(false)

  const isMainLive2DMode = computed(() => !options.isCliMode.value && !options.isChatMode.value)
  const shouldFade = computed(() =>
    isHoveringWindow.value && !isCtrlHeld.value && !options.isCliMode.value &&
    !options.isChatMode.value && !isManualResizing.value && !isManualDragging.value
  )
  const isInteractive = computed(() => isHoveringWindow.value && isCtrlHeld.value && !options.isCliMode.value && !options.isChatMode.value)
  const showCtrlResizeHint = computed(() => (isInteractive.value || isManualResizing.value) && isMainLive2DMode.value)
  const showCtrlTopButtons = computed(() => isMainLive2DMode.value && isHoveringWindow.value && isCtrlHeld.value && !isManualResizing.value)

  // setWindowClickThrough, syncPassthroughState, syncCursorPollState
  // startManualResize, startManualDrag, stopManualDrag, stopManualResize
  // stopCursorPoll, startCursorPoll

  return {
    isHoveringWindow, isCtrlHeld, isManualResizing, isManualDragging,
    shouldFade, isInteractive, showCtrlResizeHint, showCtrlTopButtons,
    setWindowClickThrough, syncPassthroughState,
    startManualResize, startManualDrag, stopManualDrag, stopManualResize,
    stopCursorPoll, startCursorPoll,
  }
}
```

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

- [ ] **Step 3: Commit**

```bash
git add src/composables/useWindowInteraction.ts
git commit -m "refactor(app): extract useWindowInteraction composable"
```

---

### Task 12: Extract App Controls Composable (`src/composables/useAppControls.ts`)

**Files:**
- Create: `src/composables/useAppControls.ts`

Small composable for the top-right button actions.

- [ ] **Step 1: Create the composable**

```typescript
// src/composables/useAppControls.ts
import type { IpcRendererLike } from '../platform/electronIpc'

export function useAppControls(ipcRenderer: IpcRendererLike | null) {
  function closeApp() {
    ipcRenderer?.send?.('close-app')
  }

  function openLive2DConsole() {
    ipcRenderer?.send?.('ui:openConsole')
  }

  function openAIChat() {
    ipcRenderer?.send?.('ui:openChat')
  }

  function toggleDevTools() {
    ipcRenderer?.send?.('ui:toggleDevTools')
  }

  return { closeApp, openLive2DConsole, openAIChat, toggleDevTools }
}
```

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

- [ ] **Step 3: Commit**

```bash
git add src/composables/useAppControls.ts
git commit -m "refactor(app): extract useAppControls composable"
```

---

### Task 13: Rewire `src/App.vue` to Use Composables

**Files:**
- Modify: `src/App.vue`

Replace inlined function definitions with composable imports. Keep template and styles unchanged.

- [ ] **Step 1: Replace `<script setup>` imports and initialization**

Replace the first ~100 lines of App.vue (imports, constants, refs, computed properties) with:

```typescript
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as PIXI from 'pixi.js'
import { getIpcRenderer } from './platform/electronIpc'
import Live2DConsole from './components/Live2DConsole.vue'
import AgentChat from './components/AgentChat.vue'
import QuipOverlay from './components/QuipOverlay.vue'
import { installLive2DFocusMouseTracking } from './mouseTracking'
import { useLive2DModel } from './composables/useLive2DModel'
import { useLive2DCommands } from './composables/useLive2DCommands'
import { useWindowInteraction } from './composables/useWindowInteraction'
import { useAppControls } from './composables/useAppControls'

(window as any).PIXI = PIXI

const DEFAULT_MODEL_JSON_PATH = 'live2d/mianfeimox/llny.model3.json'
// ... (keep path constants)

const rootRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const ipcRenderer = getIpcRenderer()
const modelUrl = computed(() => new URL(DEFAULT_MODEL_JSON_PATH, window.location.href).toString())
const isModel3 = computed(() => DEFAULT_MODEL_JSON_PATH.toLowerCase().endsWith('.model3.json'))
const isCliMode = computed(() => new URLSearchParams(window.location.search).get('mode') === 'cli')
const isChatMode = computed(() => new URLSearchParams(window.location.search).get('mode') === 'chat')

// Composables
const model = useLive2DModel({ defaultModelPath: DEFAULT_MODEL_JSON_PATH, modelUrl, isModel3 })
const commands = useLive2DCommands(model)
const interaction = useWindowInteraction({ ipcRenderer, isCliMode, isChatMode })
const controls = useAppControls(ipcRenderer)

// Re-export for template
const { loadState, errorText } = model
const { shouldFade, isInteractive, showCtrlResizeHint, showCtrlTopButtons } = interaction
const { closeApp, openLive2DConsole, openAIChat, toggleDevTools } = controls
```

- [ ] **Step 2: Remove inlined function bodies**

Delete all the functions that are now in composables (lines ~110–1391). Keep:
- `onMounted` block (lines 1393–1614) — calls composable methods
- `onBeforeUnmount` block (lines 1616–1639) — calls composable `dispose()`
- IPC handler registration (lines 1642–1734) — calls `commands.executeLive2DCommand`

- [ ] **Step 3: Verify build**

```bash
pnpm build
```

Expected: no errors.

- [ ] **Step 4: Verify line count reduction**

```bash
wc -l src/App.vue
```

Expected: ~400-500 lines (down from 2052).

- [ ] **Step 5: Manual smoke test**

```bash
pnpm dev
```

Verify:
- Live2D model loads and renders
- CLI commands work (motion, expr, status)
- Window hover fade + click-through works
- Ctrl+hover resize/drag works
- Top buttons (console, chat, devtools) work
- Close button works

- [ ] **Step 6: Commit**

```bash
git add src/App.vue
git commit -m "refactor(app): rewire App.vue to use extracted composables"
```

---

## Phase 4: AgentChat.vue Decomposition

The current `src/components/AgentChat.vue` (1698 lines) will be decomposed into 3 composables + 2 sub-components.

### Task 14: Extract Markdown Renderer (`src/composables/useMarkdownRenderer.ts`)

**Files:**
- Create: `src/composables/useMarkdownRenderer.ts`

Extracts hljs setup, MarkdownIt configuration, and all LaTeX normalization functions (lines 33–366).

- [ ] **Step 1: Create the composable**

```typescript
// src/composables/useMarkdownRenderer.ts
import hljs from 'highlight.js/lib/core'
// ... (all hljs language imports)
import 'highlight.js/styles/github-dark.css'
import MarkdownIt from 'markdown-it'
import markdownItKatex from 'markdown-it-katex'
import 'katex/dist/katex.min.css'

// Constants
const FENCE_LINE_PATTERN = /^\s*(```|~~~)/
const LATEX_WORD_COMMANDS = [/* ... */].join('|')
const LATEX_COMMAND_PATTERN = new RegExp(/* ... */)
// ... (all pattern constants)

// Functions
function escapeHtml(text: string): string { /* ... */ }
function highlightCodeBlock(code: string, language: string): string { /* ... */ }
function normalizeLatexBackslashes(text: string): string { /* ... */ }
function looksLikeStandaloneLatex(line: string): boolean { /* ... */ }
function wrapInlineLatex(text: string): string { /* ... */ }
function normalizeMathMarkdownLine(line: string): string { /* ... */ }
function normalizeRichTextMarkdown(text: string): string { /* ... */ }

const markdownRenderer = new MarkdownIt({
  breaks: true,
  highlight: highlightCodeBlock,
  html: false,
  linkify: true,
  typographer: true,
}).use(markdownItKatex)

export function useMarkdownRenderer() {
  function renderAssistantText(text: string): string {
    // ... (from AgentChat.vue line 467)
  }

  function normalizeAssistantContent(text: string): string {
    // ... (from AgentChat.vue line 484)
  }

  function shouldRenderRichMessage(line: { contentType?: string; renderMode?: string; role?: string }): boolean {
    // ... (from AgentChat.vue line 471)
  }

  return { renderAssistantText, normalizeAssistantContent, shouldRenderRichMessage, markdownRenderer }
}
```

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

- [ ] **Step 3: Commit**

```bash
git add src/composables/useMarkdownRenderer.ts
git commit -m "refactor(chat): extract useMarkdownRenderer composable"
```

---

### Task 15: Extract Agent Message Handlers (`src/composables/useAgentMessages.ts`)

**Files:**
- Create: `src/composables/useAgentMessages.ts`

Extracts all IPC message handler functions and their supporting utilities (lines 86–770).

- [ ] **Step 1: Create the composable**

```typescript
// src/composables/useAgentMessages.ts
import { ref } from 'vue'
import type { IpcRendererLike } from '../platform/electronIpc'

// Message types (ChatMessage, ExpressionMessage, ErrorMessage, StatusUpdate, QuipMessage)
// ... (copy from AgentChat.vue lines 87-186)

export type ChatLine = {
  role: 'user' | 'assistant' | 'system' | 'err'
  text: string
  contentType?: 'plain_text' | 'markdown'
  renderMode?: 'plain_text' | 'rich_text'
  fileAction?: FileActionCard
}

export type FileActionCard = {
  title: string
  status: 'completed' | 'failed'
  actionName?: string
  target?: string
  source?: string
  result?: string
  query?: string
  matchCount?: number
  tool?: string
  error?: string
}

export function useAgentMessages(options: {
  ipcRenderer: IpcRendererLike | null
  push: (role: ChatLine['role'], text: string, extra?: Omit<ChatLine, 'role' | 'text'>) => void
  startTypewriter: (text: string, renderMode?: 'rich_text' | 'plain_text') => void
}) {
  const currentStatus = ref('idle')
  const currentProgress = ref(0)
  const currentNode = ref('')
  const currentNodeLabel = ref('')

  // Throttle state
  const STATUS_LOG_THROTTLE_MS = 850
  const QUIP_LOG_THROTTLE_MS = 850
  let lastStatusLogAt = 0
  let lastStatusLogKey = ''
  let lastQuipLogAt = 0
  let lastQuipLogKey = ''

  // Utility functions
  function stringField(value: unknown): string { /* ... */ }
  function numberField(value: unknown): number | undefined { /* ... */ }
  function getDisplayNodeName(data: any): string { /* ... */ }
  function getActionStatusText(data: any): string | null { /* ... */ }
  function getStatusMetadata(data: any): Record<string, unknown> { /* ... */ }
  function buildFileActionCard(data: any): FileActionCard | null { /* ... */ }
  function shouldLogTransientEvent(opts: any): boolean { /* ... */ }

  // IPC handlers
  function handleChat(_event: any, data: ChatMessage): void { /* ... */ }
  function handleError(_event: any, data: ErrorMessage): void { /* ... */ }
  function handleQuip(_event: any, data: QuipMessage): void { /* ... */ }
  function handleStatus(_event: any, data: StatusUpdate): void { /* ... */ }
  function handleExpression(_event: any, data: ExpressionMessage): void { /* ... */ }

  // IPC registration
  function registerIpcListeners(): void {
    const ipc = options.ipcRenderer
    if (!ipc?.on) return
    ipc.on('agent:chat', handleChat)
    ipc.on('agent:error', handleError)
    ipc.on('agent:quip', handleQuip)
    ipc.on('agent:status', handleStatus)
    ipc.on('agent:expression', handleExpression)
  }

  function unregisterIpcListeners(): void {
    const ipc = options.ipcRenderer
    if (!ipc?.removeListener) return
    ipc.removeListener('agent:chat', handleChat)
    ipc.removeListener('agent:error', handleError)
    ipc.removeListener('agent:quip', handleQuip)
    ipc.removeListener('agent:status', handleStatus)
    ipc.removeListener('agent:expression', handleExpression)
  }

  return {
    currentStatus, currentProgress, currentNode, currentNodeLabel,
    registerIpcListeners, unregisterIpcListeners,
  }
}
```

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

- [ ] **Step 3: Commit**

```bash
git add src/composables/useAgentMessages.ts
git commit -m "refactor(chat): extract useAgentMessages composable"
```

---

### Task 16: Extract Chat Operations (`src/composables/useChatOperations.ts`)

**Files:**
- Create: `src/composables/useChatOperations.ts`

Extracts session management, prompt sending, submission, history, workspace (lines 368–960).

- [ ] **Step 1: Create the composable**

```typescript
// src/composables/useChatOperations.ts
import { ref } from 'vue'
import type { IpcRendererLike } from '../platform/electronIpc'
import type { ChatLine } from './useAgentMessages'

export function useChatOperations(options: {
  ipcRenderer: IpcRendererLike | null
  lines: { value: ChatLine[] }
  push: (role: ChatLine['role'], text: string, extra?: Omit<ChatLine, 'role' | 'text'>) => void
  clearScreen: () => void
  startTypewriter: (text: string, renderMode?: 'rich_text' | 'plain_text') => void
  focusInputSoon: () => void
  buildContext: (maxChars?: number) => string
}) {
  const input = ref('')
  const inputHistory = ref<string[]>([])
  const historyIndex = ref(-1)
  const isSending = ref(false)
  const currentSessionId = ref('')

  // Session management
  async function switchSession(sessionId: string): Promise<void> { /* ... */ }
  function createNewSession(): void { /* ... */ }

  // Workspace
  function updateWorkspace(path: string): void { /* ... */ }

  // Prompt sending
  async function sendPrompt(prompt: string): Promise<void> { /* ... */ }
  function submit(): void { /* ... */ }

  // History
  function applyHistory(delta: number): void { /* ... */ }

  // Keyboard
  function onKeydown(e: KeyboardEvent): void { /* ... */ }

  // Backend activity
  function onBackendActivity(): void { /* ... */ }

  // Desktop export confirmation
  function needsDesktopExportConfirmation(prompt: string): boolean { /* ... */ }
  async function confirmDesktopExportRequest(prompt: string): Promise<boolean> { /* ... */ }
  function resolveDesktopExportConfirmation(confirmed: boolean): void { /* ... */ }

  // Code copy
  function hasCodeBlocks(text: string): boolean { /* ... */ }
  async function copyLastCodeBlock(text: string): Promise<void> { /* ... */ }

  // Auto-resize input
  function autoResizeInput(): void { /* ... */ }

  return {
    input, inputHistory, historyIndex, isSending, currentSessionId,
    switchSession, createNewSession, updateWorkspace,
    sendPrompt, submit, applyHistory, onKeydown,
    onBackendActivity,
    hasCodeBlocks, copyLastCodeBlock, autoResizeInput,
    needsDesktopExportConfirmation, confirmDesktopExportRequest, resolveDesktopExportConfirmation,
  }
}
```

- [ ] **Step 2: Verify build**

```bash
pnpm build
```

- [ ] **Step 3: Commit**

```bash
git add src/composables/useChatOperations.ts
git commit -m "refactor(chat): extract useChatOperations composable"
```

---

### Task 17: Extract ChatMessageList Component (`src/components/ChatMessageList.vue`)

**Files:**
- Create: `src/components/ChatMessageList.vue`

Extracts the message rendering template from AgentChat.vue (lines 1002–1090 in `<template>` section).

- [ ] **Step 1: Create the component**

```vue
<!-- src/components/ChatMessageList.vue -->
<script setup lang="ts">
import type { ChatLine } from '../composables/useAgentMessages'

defineProps<{
  lines: ChatLine[]
  shouldRenderRichMessage: (line: ChatLine) => boolean
  renderAssistantText: (text: string) => string
  hasCodeBlocks: (text: string) => boolean
  copyLastCodeBlock: (text: string) => Promise<void>
  copyMessage: (text: string) => void
}>()
</script>

<template>
  <div ref="outputRef" class="msg-list" role="log" aria-live="polite">
    <div v-for="(l, i) in lines" :key="i" class="msg-row" :class="l.role">
      <!-- Assistant rich text -->
      <div v-if="shouldRenderRichMessage(l)" class="msg-bubble assistant">
        <button class="msg-copy-btn" @click="copyMessage(l.text)" title="复制">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        </button>
        <div class="msg-content rich" v-html="renderAssistantText(l.text)" />
        <div class="msg-copy-row" v-if="hasCodeBlocks(l.text)">
          <button class="copy-code-btn" @click="copyLastCodeBlock(l.text)">复制代码</button>
        </div>
      </div>
      <!-- File action card -->
      <div v-else-if="l.fileAction" class="msg-bubble assistant">
        <!-- ... (copy from AgentChat.vue template) -->
      </div>
      <!-- User message -->
      <div v-else-if="l.role === 'user'" class="msg-bubble user">
        <div class="msg-content">{{ l.text }}</div>
      </div>
      <!-- System/error -->
      <div v-else class="msg-bubble system">
        <div class="msg-content">{{ l.text }}</div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Move relevant styles**

Copy the `.msg-list`, `.msg-row`, `.msg-bubble`, `.msg-content`, `.msg-copy-btn`, `.file-action-card`, and related styles from AgentChat.vue into ChatMessageList.vue's `<style scoped>` block.

- [ ] **Step 3: Verify build**

```bash
pnpm build
```

- [ ] **Step 4: Commit**

```bash
git add src/components/ChatMessageList.vue
git commit -m "refactor(chat): extract ChatMessageList component"
```

---

### Task 18: Extract ChatInputArea Component (`src/components/ChatInputArea.vue`)

**Files:**
- Create: `src/components/ChatInputArea.vue`

Extracts the input area template and keyboard handling.

- [ ] **Step 1: Create the component**

```vue
<!-- src/components/ChatInputArea.vue -->
<script setup lang="ts">
const props = defineProps<{
  input: string
  isSending: boolean
  onKeydown: (e: KeyboardEvent) => void
  onInput: (value: string) => void
  onSubmit: () => void
  autoResizeInput: () => void
}>()

const inputRef = defineModel<HTMLTextAreaElement | null>('inputEl', { default: null })
</script>

<template>
  <div class="input-area">
    <textarea
      ref="inputRef"
      :value="input"
      :disabled="isSending"
      class="chat-input"
      rows="1"
      placeholder="输入消息... (Enter 发送, Shift+Enter 换行, ↑↓ 历史)"
      @input="(e) => { onInput((e.target as HTMLTextAreaElement).value); autoResizeInput() }"
      @keydown="onKeydown"
    />
    <button class="send-btn" :disabled="isSending || !input.trim()" @click="onSubmit">
      <!-- send icon SVG -->
    </button>
  </div>
</template>
```

- [ ] **Step 2: Move relevant styles**

Copy `.input-area`, `.chat-input`, `.send-btn` styles from AgentChat.vue.

- [ ] **Step 3: Verify build**

```bash
pnpm build
```

- [ ] **Step 4: Commit**

```bash
git add src/components/ChatInputArea.vue
git commit -m "refactor(chat): extract ChatInputArea component"
```

---

### Task 19: Rewire `AgentChat.vue` to Use Composables + Components

**Files:**
- Modify: `src/components/AgentChat.vue`

- [ ] **Step 1: Replace `<script setup>` with composable imports**

```typescript
<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { getIpcRenderer } from '../platform/electronIpc'
import { useMarkdownRenderer } from '../composables/useMarkdownRenderer'
import { useAgentMessages, type ChatLine } from '../composables/useAgentMessages'
import { useChatOperations } from '../composables/useChatOperations'
import BackendIndicator from './BackendIndicator.vue'
import PixelPet from './PixelPet.vue'
import StatusTicker from './StatusTicker.vue'
import PixelLoading from './PixelLoading.vue'
import ChatHistoryPanel from './ChatHistoryPanel.vue'
import WorkspaceSelector from './WorkspaceSelector.vue'
import ChatMessageList from './ChatMessageList.vue'
import ChatInputArea from './ChatInputArea.vue'

const ipcRenderer = getIpcRenderer()

// Theme
const theme = ref<'light' | 'dark'>('light')
function toggleTheme() { /* ... */ }
function copyMessage(text: string) { /* ... */ }
// Init theme from localStorage

// Composables
const { renderAssistantText, normalizeAssistantContent, shouldRenderRichMessage } = useMarkdownRenderer()

const lines = ref<ChatLine[]>([])
function push(role: ChatLine['role'], text: string, extra: Omit<ChatLine, 'role' | 'text'> = {}) { /* ... */ }
function clearScreen() { /* ... */ }
function focusInputSoon() { /* ... */ }

// Typewriter state
function flushTypewriter(finishLine = true) { /* ... */ }
function startTypewriter(text: string, renderMode?: 'rich_text' | 'plain_text') { /* ... */ }

const messages = useAgentMessages({ ipcRenderer, push, startTypewriter })
const chat = useChatOperations({
  ipcRenderer, lines, push, clearScreen, startTypewriter, focusInputSoon,
  buildContext: (maxChars = 4000) => { /* ... */ },
})

// Register IPC on mount
onMounted(() => {
  messages.registerIpcListeners()
})
onUnmounted(() => {
  messages.unregisterIpcListeners()
})
</script>
```

- [ ] **Step 2: Simplify `<template>`**

Replace the inline message list and input area with sub-components:

```vue
<template>
  <div class="chat-root">
    <header class="chat-header">
      <!-- ... (header stays in AgentChat.vue, ~40 lines) -->
    </header>

    <ChatMessageList
      :lines="lines"
      :shouldRenderRichMessage="shouldRenderRichMessage"
      :renderAssistantText="renderAssistantText"
      :hasCodeBlocks="chat.hasCodeBlocks"
      :copyLastCodeBlock="chat.copyLastCodeBlock"
      :copyMessage="copyMessage"
    />

    <ChatInputArea
      :input="chat.input.value"
      :isSending="chat.isSending.value"
      :onKeydown="chat.onKeydown"
      :onInput="(v) => chat.input.value = v"
      :onSubmit="chat.submit"
      :autoResizeInput="chat.autoResizeInput"
    />
  </div>
</template>
```

- [ ] **Step 3: Verify line count reduction**

```bash
wc -l src/components/AgentChat.vue
```

Expected: ~300-400 lines (down from 1698).

- [ ] **Step 4: Full build verification**

```bash
pnpm build
```

Expected: no errors.

- [ ] **Step 5: Manual smoke test**

```bash
pnpm dev
```

Verify:
- Chat window opens
- Can type and send messages
- Markdown renders correctly (code blocks, LaTeX)
- Theme toggle works
- Session history switching works
- File action cards render
- Typewriter animation works
- Status ticker updates

- [ ] **Step 6: Commit**

```bash
git add src/components/AgentChat.vue
git commit -m "refactor(chat): rewire AgentChat.vue to use composables and sub-components"
```

---

## Phase 5: Final Verification

### Task 20: Full Project Verification

- [ ] **Step 1: Run full build**

```bash
pnpm build
```

Expected: no errors.

- [ ] **Step 2: Run backend tests**

```bash
cd backend && python -m pytest tests/ -v
```

Expected: all tests pass (refactoring was frontend-only, but verify no regressions).

- [ ] **Step 3: Verify file sizes**

```bash
wc -l src/App.vue src/components/AgentChat.vue electron/main.ts
```

Expected:
- `src/App.vue`: ~400-500 lines (was 2052)
- `src/components/AgentChat.vue`: ~300-400 lines (was 1698)
- `electron/main.ts`: ~500-600 lines (was 1417)

- [ ] **Step 4: Verify no loose files remain**

```bash
ls '$null' scripts/tmp_create_ports.py package-lock.json 2>&1
```

Expected: "No such file" for all three.

- [ ] **Step 5: Verify .gitignore coverage**

```bash
git status --short
```

Expected: clean or only intentionally untracked files (`.agents/`, `.claude/skills/`, competition docx).

- [ ] **Step 6: Final commit with summary**

```bash
git log --oneline -10
```

Verify all commits follow conventional commits format.
