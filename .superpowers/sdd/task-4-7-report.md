# Task 4-7 Report: Electron Module Extraction

## Summary

Extracted 4 focused modules from `electron/main.ts` (1417 lines) as pure structural decomposition with zero logic changes. The shared types in `electron/types.ts` were already in place from Task 3.

## Build Verification

- `vue-tsc -b`: passed (no type errors)
- `vite build`: passed (client + electron bundles built successfully)
- `electron/main.ts` was NOT modified (deferred to a later rewiring task)

## Task 4: `electron/windows.ts`

| Field        | Value                                    |
|-------------|------------------------------------------|
| Status      | DONE                                     |
| File        | `electron/windows.ts`                    |
| Lines       | 161                                      |
| Commit      | `66c34d9`                                |
| Message     | `refactor(electron): extract window creation to electron/windows.ts` |

**Exported:**
- `WindowSet` type — `{ mainWindow, consoleWindow, chatWindow }` all `BrowserWindow | null`
- `showAndFocus(win)` — unchanged signature
- `createMainWindow(set)` — renamed from `createWindow`; assigns to `set.mainWindow`
- `createConsoleWindow(set)` — assigns to `set.consoleWindow`; `closed` handler sets `set.consoleWindow = null`
- `createChatWindow(set)` — assigns to `set.chatWindow`; `closed` handler sets `set.chatWindow = null`

**Notes:**
- `mouseTrackDebug` env var and `did-fail-load` handler moved with `createMainWindow`
- All `mainWindow`/`consoleWindow`/`chatWindow` references replaced with `set.*` equivalents

## Task 5: `electron/backend-bridge.ts`

| Field        | Value                                    |
|-------------|------------------------------------------|
| Status      | DONE                                     |
| File        | `electron/backend-bridge.ts`             |
| Lines       | 288                                      |
| Commit      | `b400084`                                |
| Message     | `refactor(electron): extract backend bridge to electron/backend-bridge.ts` |

**Exported:**
- `getConfiguredAgentEndpoint()`, `resolveAgentBaseUrl()`, `resolveAgentMessagesEndpoint()`
- `fetchBackendWorkspace()`, `syncBackendWorkspace(path)`
- `resolveAgentMessageChannel(message)`, `dispatchAgentMessage(message, windows)`
- `toAgentMessageEnvelope(value)`
- `startBackendMessageBridge(windows)`, `stopBackendMessageBridge()`

**Non-exported (private):**
- `normalizeBaseUrl`, `parsePositiveIntegerEnv`
- Bridge state: `backendBridgeTimer`, `backendBridgeInFlight`, `backendBridgeSinceId`, `backendBridgeLastError`, `backendBridgeEndpoint`
- Workspace persistence: `WorkspaceState`, `resolveWorkspaceStatePath`, `loadWorkspacePath`, `saveWorkspacePath`

**Notes:**
- `dispatchAgentMessage` takes `(message, windows: WindowSet)` instead of closing over module-level window vars
- `pollBackendMessagesOnce` and `startBackendMessageBridge` also take `(windows: WindowSet)` and pass it through
- Workspace persistence functions (lines 873-903 of original) co-located here since they are part of the backend integration surface

## Task 6: `electron/window-manipulation.ts`

| Field        | Value                                    |
|-------------|------------------------------------------|
| Status      | DONE                                     |
| File        | `electron/window-manipulation.ts`        |
| Lines       | 187                                      |
| Commit      | `58f9e77`                                |
| Message     | `refactor(electron): extract window manipulation to electron/window-manipulation.ts` |

**Exported:**
- `stopManualResizeByWinId(winId)`, `stopManualDragByWinId(winId)`
- `handleManualResizeStart(event, payload)` — wraps IPC `window:manualResizeStart` body
- `handleManualResizeEnd(event)` — wraps IPC `window:manualResizeEnd` body
- `handleManualDragStart(event)` — wraps IPC `window:manualDragStart` body
- `handleManualDragEnd(event)` — wraps IPC `window:manualDragEnd` body

**Non-exported (private):**
- `manualResizeDirs` Set, `manualResizeStateByWinId` Map, `manualDragStateByWinId` Map
- `computeResizedBounds()` helper

## Task 7: `electron/vision.ts`

| Field        | Value                                    |
|-------------|------------------------------------------|
| Status      | DONE                                     |
| File        | `electron/vision.ts`                     |
| Lines       | 62                                       |
| Commit      | `d8cbb88`                                |
| Message     | `refactor(electron): extract vision screenshot to electron/vision.ts` |

**Exported:**
- `startVisionScreenshotLoop()`
- `stopVisionScreenshotLoop()`

**Non-exported (private):**
- `VISION_SCREENSHOT_INTERVAL_MS`, `VISION_SCREENSHOT_PATH`, `_visionScreenshotTimer`
- `captureAndSaveScreenshot()` async helper

## Totals

| Metric             | Value  |
|--------------------|--------|
| Total new lines    | 698    |
| Files created      | 4      |
| Commits            | 4      |
| main.ts modified   | NO     |

## Concerns

1. **Workspace persistence co-located in `backend-bridge.ts`**: The workspace state functions (`loadWorkspacePath`, `saveWorkspacePath`, `resolveWorkspaceStatePath`, and `WorkspaceState` type) from lines 873-903 of `main.ts` were included in `backend-bridge.ts` because they are logically part of the backend integration surface. In the rewiring phase, `main.ts` will need to import these (or they can be further extracted to a dedicated module).

2. **New files not yet type-checked by project tsconfig**: Since `main.ts` has not been modified to import these modules, they are not currently compiled by `vite-plugin-electron` or checked by `vue-tsc`. They will be type-checked once `main.ts` is rewired to import them in a subsequent task. The code was copied verbatim from the already-compiling `main.ts`, so no type issues are expected.

3. **`Electron.Rectangle` and `Electron.IpcMainEvent` references**: `window-manipulation.ts` uses `Electron.Rectangle` (in `computeResizedBounds` signature) and `Electron.IpcMainEvent` (in handler signatures) via the global Electron namespace. These types are available globally when the `electron` package is installed and its global declarations are loaded.

DONE
