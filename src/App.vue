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

// Constants
const DEFAULT_MODEL_JSON_PATH = 'live2d/mianfeimox/llny.model3.json'

// Template refs
const rootRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)

// Platform
const ipcRenderer = getIpcRenderer()

// URL/mode computed properties
const modelUrl = computed(() => new URL(DEFAULT_MODEL_JSON_PATH, window.location.href).toString())
const isModel3 = computed(() => DEFAULT_MODEL_JSON_PATH.toLowerCase().endsWith('.model3.json'))
const isCliMode = computed(() => new URLSearchParams(window.location.search).get('mode') === 'cli')
const isChatMode = computed(() => new URLSearchParams(window.location.search).get('mode') === 'chat')

// Composables
const model = useLive2DModel({ defaultModelPath: DEFAULT_MODEL_JSON_PATH, modelUrl, isModel3, isCliMode })
const interaction = useWindowInteraction({ ipcRenderer, isCliMode, isChatMode })
const controls = useAppControls(ipcRenderer)

// Wire commands — map model's API to the interface expected by useLive2DCommands
const commands = useLive2DCommands({
  getCurrentModel: model.currentModel,
  getCurrentModelSettingsUrl: model.currentModelSettingsUrl,
  getIsModel3: () => isModel3.value,
  getCachedMeta: model.cachedMeta,
  getLastMetaError: model.getLastMetaError,
  ensureMetaLoaded: model.ensureMetaLoaded,
  buildLive2DActionCatalog: model.buildLive2DActionCatalog,
  playLive2DAction: model.playLive2DAction,
  stopAllLive2D: model.stopAllLive2D,
  resolveMotionCliArgToActionId: model.resolveMotionCliArgToActionId,
  resolveExpressionCliArgToActionId: model.resolveExpressionCliArgToActionId,
  playExpressionFromFile: model.playExpressionFromFile,
  removeExpressionFile: model.removeExpressionFile,
  exprAdd: model.exprAdd,
  exprClear: model.exprClear,
  exprClearNonPinned: model.exprClearNonPinned,
  exprRemove: model.exprRemove,
  getActiveExpressionsText: model.getActiveExpressionsText,
  resolveExpressionTagToActionId: model.resolveExpressionTagToActionId,
  resolveStartupExpressionTokenToConcreteActionId: model.resolveStartupExpressionTokenToConcreteActionId,
  expressionActionIdToHandleKey: model.expressionActionIdToHandleKey,
  isExpressionActionId: model.isExpressionActionId,
  looksLikeExpressionFile: model.looksLikeExpressionFile,
  makeExpressionNameActionId: model.makeExpressionNameActionId,
  fadeOutAndRemoveExpressionHandle: model.fadeOutAndRemoveExpressionHandle,
  getPinnedExpressionHandleKeys: model.getPinnedExpressionHandleKeys,
})

// Destructure for template access
const { loadState, errorText } = model
const { shouldFade, isInteractive, showCtrlResizeHint, showCtrlTopButtons, isHoveringWindow, isCtrlHeld, isManualResizing, isManualDragging } = interaction
const { startManualResize, startManualDrag, stopManualDrag, stopManualResize } = interaction
const { closeApp, openLive2DConsole, openAIChat, toggleDevTools } = controls

// Module-level cleanup state (shared between onMounted and onBeforeUnmount)
let disposed = false
let resizeHandler: (() => void) | null = null
let layoutRaf: number | null = null
let disposeMouseTracking: null | (() => void) = null

onMounted(async () => {
  // Main-window IPC listeners (live2d:command / agent:expression / live2d:apiRequest).
  // Registered here so they can be removed in onBeforeUnmount (no leak on remount).
  bindMainWindowIpcListeners()

  disposeMouseTracking = installLive2DFocusMouseTracking({
    ipcRenderer,
    getModel: () => model.currentModel(),
    enabled: interaction.isMainLive2DMode.value,
  })

  // Hover fade + click-through behavior.
  // Use pointer events so we can read e.ctrlKey even when the window isn't focused.
  const rootEl = rootRef.value
  if (rootEl && !isCliMode.value && !isChatMode.value) {
    const onEnter = (e: PointerEvent) => {
      isHoveringWindow.value = true
      isCtrlHeld.value = Boolean(e.ctrlKey)
      interaction.syncPassthroughState()
    }
    const onMove = (e: PointerEvent) => {
      // If pointerenter is missed (rare), pointermove still means we are inside.
      if (!isHoveringWindow.value) {
        isHoveringWindow.value = true
        interaction.syncPassthroughState()
      }
      const nextCtrl = Boolean(e.ctrlKey)
      if (isCtrlHeld.value !== nextCtrl) {
        isCtrlHeld.value = nextCtrl
        interaction.syncPassthroughState()
      }
    }
    const onLeave = () => {
      isHoveringWindow.value = false
      isCtrlHeld.value = false
      interaction.syncPassthroughState()
    }

    rootEl.addEventListener('pointerenter', onEnter)
    rootEl.addEventListener('pointermove', onMove)
    rootEl.addEventListener('pointerleave', onLeave)

    // Safety: if the drag-zone is unmounted (e.g. Ctrl released) or focus changes,
    // ensure we always stop manual operations so the window won't "stick" to cursor.
    const onGlobalPointerUp = (e: PointerEvent) => {
      interaction.stopManualDrag(e)
      interaction.stopManualResize(e)
    }
    const onGlobalPointerCancel = (e: PointerEvent) => {
      interaction.stopManualDrag(e)
      interaction.stopManualResize(e)
    }
    const onGlobalBlur = () => {
      interaction.stopManualDrag()
      interaction.stopManualResize()
    }

    window.addEventListener('pointerup', onGlobalPointerUp, true)
    window.addEventListener('pointercancel', onGlobalPointerCancel, true)
    window.addEventListener('blur', onGlobalBlur)

    onBeforeUnmount(() => {
      rootEl.removeEventListener('pointerenter', onEnter)
      rootEl.removeEventListener('pointermove', onMove)
      rootEl.removeEventListener('pointerleave', onLeave)

      window.removeEventListener('pointerup', onGlobalPointerUp, true)
      window.removeEventListener('pointercancel', onGlobalPointerCancel, true)
      window.removeEventListener('blur', onGlobalBlur)
    })

    // Start polling immediately as a reliable fallback.
    interaction.startCursorPoll()
  }

  if (isCliMode.value) {
    loadState.value = 'ready'
    return
  }

  if (isChatMode.value) {
    loadState.value = 'ready'
    return
  }

  const canvas = canvasRef.value
  if (!canvas) return

  disposed = false
  loadState.value = 'loading'
  errorText.value = ''

  let pixiApp: PIXI.Application | null = null

  try {
    pixiApp = new PIXI.Application({
      view: canvas,
      autoStart: true,
      backgroundAlpha: 0,
      resizeTo: window,
      resolution: window.devicePixelRatio || 1,
    } as any)
  } catch (err) {
    try {
      pixiApp = new PIXI.Application({
        view: canvas,
        autoStart: true,
        backgroundAlpha: 0,
        resizeTo: window,
        resolution: window.devicePixelRatio || 1,
        forceCanvas: true,
      } as any)
      errorText.value = `WebGL 初始化失败，已降级为 Canvas（Live2D 可能不可用）：${String(err)}`
    } catch (err2) {
      loadState.value = 'error'
      errorText.value = `PIXI 初始化失败：${String(err2)}`
      return
    }
  }

  // Register pixiApp with the composable so it can be accessed during cleanup/IPC.
  model.setPixiApp(pixiApp)

  let live2dModel: any = null
  const layoutModel = () => {
    if (!live2dModel || !pixiApp) return

    const viewportW = pixiApp.renderer.screen.width
    const viewportH = pixiApp.renderer.screen.height

    const bounds = typeof live2dModel.getLocalBounds === 'function' ? live2dModel.getLocalBounds() : null
    if (!bounds || !Number.isFinite(bounds.width) || !Number.isFinite(bounds.height)) return
    if (bounds.width <= 0 || bounds.height <= 0) return

    // Center model using pivot so motion/scale changes are more stable.
    live2dModel.pivot.set(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)

    // Make the character occupy more of the window.
    // Keep a tiny margin so it doesn't touch edges, and clamp position to avoid clipping.
    const marginRatio = 0.018
    const safeW = viewportW * (1 - marginRatio * 2)
    const safeH = viewportH * (1 - marginRatio * 2)

    const scale = Math.min(safeW / bounds.width, safeH / bounds.height)
    if (!Number.isFinite(scale) || scale <= 0) return
    live2dModel.scale.set(scale)

    // Slightly lower than center to match typical portrait framing.
    const desiredX = viewportW / 2
    const desiredY = viewportH / 2 + viewportH * 0.1

    const halfW = (bounds.width / 2) * scale
    const halfH = (bounds.height / 2) * scale

    const xMin = halfW
    const xMax = viewportW - halfW
    const yMin = halfH
    const yMax = viewportH - halfH

    const x = xMin <= xMax ? Math.min(Math.max(desiredX, xMin), xMax) : desiredX
    const y = yMin <= yMax ? Math.min(Math.max(desiredY, yMin), yMax) : desiredY
    live2dModel.position.set(x, y)
  }

  const scheduleLayout = () => {
    if (layoutRaf != null) cancelAnimationFrame(layoutRaf)
    layoutRaf = requestAnimationFrame(() => {
      layoutRaf = null
      layoutModel()
    })
  }

  resizeHandler = () => {
    if (disposed) return
    scheduleLayout()
  }
  window.addEventListener('resize', resizeHandler)

  try {
    await model.ensureRuntimeLoaded()

    const live2d = isModel3.value
      ? await model.getCubism4Module()
      : await import('pixi-live2d-display/cubism2')
    const Live2DModel = (live2d as any).Live2DModel as { from: (url: string) => Promise<any> }
    live2dModel = await Live2DModel.from(modelUrl.value)
    // Sync the composable's internal state after successful model load.
    model.setCurrentModel(live2dModel)
    model.setCurrentModelSettingsUrl(modelUrl.value)
    model.resetCachedMeta()
    void model.ensureMetaLoaded(false)

    if (disposed) {
      live2dModel?.destroy?.()
      live2dModel = null
      return
    }

    pixiApp.stage.addChild(live2dModel as any)
    // Layout immediately and again on next tick to avoid occasional bounds instability.
    scheduleLayout()
    pixiApp.ticker.addOnce(() => scheduleLayout())
    pixiApp.ticker.addOnce(() => {
      void model.applyStartupExpressions()
    })
    loadState.value = 'ready'
  } catch (err) {
    if (disposed) return
    // Surface the real error in console (useful when running under Electron with terminal logs).
    console.error('[Live2D] load failed', err)
    loadState.value = 'error'

    const errText = String(err ?? '')
    const isMocVersionMismatch =
      /moc3 ver is \[5\]/i.test(errText) ||
      /unsupport\s+later\s+than\s+moc3\s+ver:\[4\]/i.test(errText)

    if (isMocVersionMismatch) {
      errorText.value =
        `Live2D 模型加载失败：该模型是 moc3 v5（Cubism 5 系列导出），但当前加载的 Cubism Core 仅支持 moc3 v4。\n` +
        `解决办法：替换 public/live2d/live2dcubismcore.min.js 为 Cubism Core 5.x（支持 moc3 v5）的版本。\n` +
        `注意：本项目在 pnpm dev/build 时会从 node_modules 同步 core（目前是 4.x）。你可以：\n` +
        `- 设置环境变量 LIVE2D_CUBISM_CORE_SRC 指向你的 core5 的 live2dcubismcore.min.js\n` +
        `- 或设置 LIVE2D_CUBISM_CORE_NO_SYNC=1 关闭 core 同步（自己管理 public/live2d/ 下的 core 文件）`
      return
    }

    errorText.value =
      `Live2D 模型加载失败：${errText}\n` +
      `请确认存在 ${DEFAULT_MODEL_JSON_PATH}（位于 public/ 下），并且能被访问：${modelUrl.value}`
  }
})

onBeforeUnmount(() => {
  disposed = true
  unbindMainWindowIpcListeners()
  interaction.markDisposed()
  // Ensure any in-progress manual resize is stopped.
  try {
    ipcRenderer?.send?.('window:manualResizeEnd')
  } catch {
    // ignore
  }
  interaction.stopCursorPoll()
  disposeMouseTracking?.()
  disposeMouseTracking = null
  // Ensure window is interactive again when leaving.
  interaction.setWindowClickThrough(false)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  resizeHandler = null
  if (layoutRaf != null) cancelAnimationFrame(layoutRaf)
  layoutRaf = null
  // Clean up composable's internal state.
  model.setCurrentModel(null)
  model.setCurrentModelSettingsUrl(null)
  model.resetCachedMeta()
  model.pixiApp()?.destroy(true)
})

// ---- Main window command executor handlers (called by Electron main via IPC) ----
// Registered in onMounted via bindMainWindowIpcListeners(), removed in onBeforeUnmount.

async function onLive2DCommand(_evt: any, payload: any) {
  const id = payload?.id
  const cmd = payload?.cmd
  if (typeof id !== 'string' || typeof cmd !== 'string') return

  try {
    const res = await commands.executeLive2DCommand(cmd)
    ipcRenderer?.send('live2d:commandResult', { id, ok: res.ok, output: res.output })
  } catch (e) {
    ipcRenderer?.send('live2d:commandResult', { id, ok: false, output: String(e) })
  }
}

async function onAgentExpression(_evt: any, data: any) {
  const expression = data?.expression
  if (typeof expression !== 'string' || !expression.trim()) return

  try {
    const res = await model.playLive2DAction({ type: 'expression', id: `tag:${expression}`, mode: 'set' })
    console.log('[agent:expression] 已切换表情:', expression, res.ok ? '成功' : '失败', res.output)
  } catch (e) {
    console.error('[agent:expression] 切换表情异常:', e)
  }
}

async function onLive2DApiRequest(_evt: any, msg: any) {
  const id = msg?.id
  const payload = msg?.payload
  if (typeof id !== 'string' || !payload || typeof payload?.op !== 'string') return

  try {
    const op = payload.op
    if (op === 'status') {
      ipcRenderer?.send('live2d:apiResponse', {
        id,
        ok: true,
        data: {
          loaded: Boolean(model.currentModel()),
          modelUrl: model.currentModelSettingsUrl() ?? modelUrl.value ?? null,
          type: isModel3.value ? 'model3' : 'model',
        },
      })
      return
    }
    if (op === 'list') {
      // Ensure metadata is warmed up but don't fail listing just because meta missing.
      void model.ensureMetaLoaded(false)
      const cat = model.buildLive2DActionCatalog()
      const only = payload?.type === 'expression' || payload?.type === 'motion' ? payload.type : null
      if (only === 'expression') {
        ipcRenderer?.send('live2d:apiResponse', {
          id,
          ok: cat.ok,
          data: { ...cat, motions: [] },
          error: cat.error,
        })
      } else if (only === 'motion') {
        ipcRenderer?.send('live2d:apiResponse', {
          id,
          ok: cat.ok,
          data: { ...cat, expressions: [] },
          error: cat.error,
        })
      } else {
        ipcRenderer?.send('live2d:apiResponse', { id, ok: cat.ok, data: cat, error: cat.error })
      }
      return
    }
    if (op === 'stop') {
      const r = model.stopAllLive2D()
      ipcRenderer?.send('live2d:apiResponse', { id, ok: r.ok, data: r })
      return
    }
    if (op === 'play') {
      const type = payload?.type
      const actionId = payload?.id
      const mode = payload?.mode
      if ((type !== 'expression' && type !== 'motion') || typeof actionId !== 'string') {
        ipcRenderer?.send('live2d:apiResponse', { id, ok: false, error: 'missing type-id' })
        return
      }
      const res = await model.playLive2DAction({ type, id: actionId, mode })
      ipcRenderer?.send('live2d:apiResponse', { id, ok: res.ok, data: res })
      return
    }

    ipcRenderer?.send('live2d:apiResponse', { id, ok: false, error: `unknown op: ${op}` })
  } catch (e) {
    ipcRenderer?.send('live2d:apiResponse', { id, ok: false, error: String(e) })
  }
}

// ---- Main window IPC listener registration / cleanup ----

let mainWindowIpcBound = false

function bindMainWindowIpcListeners() {
  // Same guard as before: only when ipcRenderer.on exists and not CLI/chat mode.
  if (!ipcRenderer?.on || isCliMode.value || isChatMode.value) return
  if (mainWindowIpcBound) return
  mainWindowIpcBound = true
  ipcRenderer.on('live2d:command', onLive2DCommand)
  ipcRenderer.on('agent:expression', onAgentExpression)
  ipcRenderer.on('live2d:apiRequest', onLive2DApiRequest)
}

function unbindMainWindowIpcListeners() {
  if (!mainWindowIpcBound) return
  mainWindowIpcBound = false
  ipcRenderer?.removeListener?.('live2d:command', onLive2DCommand)
  ipcRenderer?.removeListener?.('agent:expression', onAgentExpression)
  ipcRenderer?.removeListener?.('live2d:apiRequest', onLive2DApiRequest)
}
</script>

<template>
  <div ref="rootRef" class="root" :class="{ faded: shouldFade, interactive: isInteractive }">
    <template v-if="showCtrlResizeHint">
      <div class="corner-hint corner-hint-left" aria-hidden="true" />
      <div class="corner-hint corner-hint-right" aria-hidden="true" />
    </template>

    <div v-if="ipcRenderer && showCtrlTopButtons" class="ctrl-top-buttons" style="-webkit-app-region: no-drag">
      <button class="ctrl-round" type="button" title="打开 Live2D 控制台" @click="openLive2DConsole">
        <svg viewBox="0 0 24 24" aria-hidden="true" class="ctrl-icon">
          <path
            fill="currentColor"
            d="M4 6.25A3.25 3.25 0 0 1 7.25 3h9.5A3.25 3.25 0 0 1 20 6.25v11.5A3.25 3.25 0 0 1 16.75 21h-9.5A3.25 3.25 0 0 1 4 17.75V6.25Zm3.25-.75a.75.75 0 0 0-.75.75v11.5c0 .414.336.75.75.75h9.5a.75.75 0 0 0 .75-.75V6.25a.75.75 0 0 0-.75-.75h-9.5Zm1.08 4.03a1 1 0 0 1 1.41-.1l2.24 1.86a1 1 0 0 1 0 1.54l-2.24 1.86a1 1 0 1 1-1.28-1.54l1.31-1.09-1.31-1.09a1 1 0 0 1-.13-1.41ZM13.3 15.25a1 1 0 0 1 1-1h2.55a1 1 0 1 1 0 2H14.3a1 1 0 0 1-1-1Z"
          />
        </svg>
      </button>

      <button class="ctrl-round" type="button" title="打开 AI Chat" @click="openAIChat">
        <svg viewBox="0 0 24 24" aria-hidden="true" class="ctrl-icon">
          <path
            fill="currentColor"
            d="M6.5 4A4.5 4.5 0 0 0 2 8.5v4A4.5 4.5 0 0 0 6.5 17H7v2.2c0 .72.84 1.12 1.4.66L11 17h6.5A4.5 4.5 0 0 0 22 12.5v-4A4.5 4.5 0 0 0 17.5 4h-11Zm-2 4.5A2.5 2.5 0 0 1 7 6h11a2.5 2.5 0 0 1 2.5 2.5v4A2.5 2.5 0 0 1 18 15h-7.5a1 1 0 0 0-.64.23L9 15.95V16a1 1 0 0 1-1 1H6.5A2.5 2.5 0 0 1 4 14.5v-6Z"
          />
        </svg>
      </button>

      <button class="ctrl-round" type="button" title="打开/关闭 DevTools" @click="toggleDevTools">
        <svg viewBox="0 0 24 24" aria-hidden="true" class="ctrl-icon">
          <path
            fill="currentColor"
            d="M20.7 11.3a1 1 0 0 1 0 1.4l-4.3 4.3a1 1 0 0 1-1.4-1.4l.55-.55-1.65-1.65-2.5 2.5a1 1 0 0 1-.7.29H7a1 1 0 0 1-.7-.29l-3-3a1 1 0 0 1 0-1.4l4.3-4.3a1 1 0 1 1 1.4 1.4l-.55.55 1.65 1.65 2.5-2.5A1 1 0 0 1 14.1 7H17a1 1 0 0 1 .7.29l3 3ZM16.6 9h-2.1l-2.3 2.3a1 1 0 0 1-1.4 0L8 8.5 6.5 10l2.8 2.8a1 1 0 0 1 0 1.4L7.5 16H9.9l2.6-2.6a1 1 0 0 1 1.4 0l2.4 2.4 1.5-1.5-2.8-2.8a1 1 0 0 1 0-1.4L16.6 9Z"
          />
        </svg>
      </button>
    </div>

    <AgentChat v-if="isChatMode" />


    <template v-else-if="!isChatMode">
      <div class="titlebar">
        <button
          v-if="ipcRenderer && isInteractive"
          class="close-btn"
          style="-webkit-app-region: no-drag"
          @click="closeApp"
        >
          ×
        </button>
      </div>

      <Live2DConsole v-if="isCliMode" />

      <template v-else>
        <div v-if="loadState === 'loading'" class="toast">
          正在加载 Live2D...
        </div>

        <div v-if="loadState === 'error'" class="toast toast-error">
          {{ errorText }}
        </div>

        <canvas ref="canvasRef" class="stage" />

        <QuipOverlay />

        <!-- Drag only in the middle 75% area while interactive (Ctrl held). -->
        <div
          v-if="ipcRenderer && (isInteractive || isManualDragging) && !isManualResizing"
          class="drag-zone"
          aria-hidden="true"
          @pointerdown="startManualDrag"
          @pointerup="stopManualDrag"
          @pointercancel="stopManualDrag"
        />

        <!-- Larger manual resize hit areas (Windows frameless + transparent makes native border hard to grab). -->
        <template v-if="ipcRenderer && (isInteractive || isManualResizing)">
          <div class="resize-handle n" @pointerdown="(e) => startManualResize('n', e)" @pointerup="stopManualResize" @pointercancel="stopManualResize" />
          <div class="resize-handle s" @pointerdown="(e) => startManualResize('s', e)" @pointerup="stopManualResize" @pointercancel="stopManualResize" />
          <div class="resize-handle e" @pointerdown="(e) => startManualResize('e', e)" @pointerup="stopManualResize" @pointercancel="stopManualResize" />
          <div class="resize-handle w" @pointerdown="(e) => startManualResize('w', e)" @pointerup="stopManualResize" @pointercancel="stopManualResize" />
          <div class="resize-handle ne" @pointerdown="(e) => startManualResize('ne', e)" @pointerup="stopManualResize" @pointercancel="stopManualResize" />
          <div class="resize-handle nw" @pointerdown="(e) => startManualResize('nw', e)" @pointerup="stopManualResize" @pointercancel="stopManualResize" />
          <div class="resize-handle se" @pointerdown="(e) => startManualResize('se', e)" @pointerup="stopManualResize" @pointercancel="stopManualResize" />
          <div class="resize-handle sw" @pointerdown="(e) => startManualResize('sw', e)" @pointerup="stopManualResize" @pointercancel="stopManualResize" />
        </template>
      </template>
    </template>
  </div>
</template>

<style scoped>
.root {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
  pointer-events: auto;
  opacity: 1;
  transition: opacity 260ms ease;
}

.root.faded {
  opacity: 0.06;
}

.stage {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.drag-zone {
  position: absolute;
  top: 12.5%;
  left: 12.5%;
  width: 75%;
  height: 75%;
  z-index: 997;
  background: transparent;
  user-select: none;
  cursor: move;
}


.corner-hint {
  position: absolute;
  top: 10px;
  z-index: 1003;
  width: 22px;
  height: 22px;
  pointer-events: none;
  opacity: 0.9;
}

.corner-hint-left {
  left: 10px;
  border-left: 3px solid rgba(255, 255, 255, 0.85);
  border-top: 3px solid rgba(255, 255, 255, 0.85);
  border-top-left-radius: 4px;
}

.corner-hint-right {
  right: 10px;
  border-right: 3px solid rgba(255, 255, 255, 0.85);
  border-top: 3px solid rgba(255, 255, 255, 0.85);
  border-top-right-radius: 4px;
}

.ctrl-top-buttons {
  position: absolute;
  top: 44px;
  left: 10px;
  z-index: 1004;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: auto;
}

.ctrl-round {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.92);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
}

.ctrl-round:hover {
  background: rgba(255, 255, 255, 0.16);
  border-color: rgba(255, 255, 255, 0.26);
}

.ctrl-round:active {
  transform: translateY(1px);
}

.ctrl-icon {
  width: 18px;
  height: 18px;
}

.titlebar {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1006;
  pointer-events: none;
}

.close-btn {
  cursor: pointer;
  width: 28px;
  height: 28px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: rgba(255, 70, 70, 0.95);
  font-weight: 900;
  font-size: 22px;
  line-height: 28px;
  text-align: center;
  -webkit-app-region: no-drag;
  pointer-events: auto;
}

.close-btn:hover {
  background-color: rgba(255, 70, 70, 0.14);
}

.resize-handle {
  position: absolute;
  z-index: 999;
  background: transparent;
  /* prevent text selection / scroll while dragging */
  user-select: none;
  touch-action: none;
  pointer-events: auto;
  -webkit-app-region: no-drag;
}

.resize-handle.n {
  top: 0;
  left: 0;
  right: 0;
  height: 28px;
  cursor: ns-resize;
}

.resize-handle.s {
  bottom: 0;
  left: 0;
  right: 0;
  height: 28px;
  cursor: ns-resize;
}

.resize-handle.e {
  top: 0;
  right: 0;
  bottom: 0;
  width: 28px;
  cursor: ew-resize;
}

.resize-handle.w {
  top: 0;
  left: 0;
  bottom: 0;
  width: 28px;
  cursor: ew-resize;
}

.resize-handle.ne {
  top: 0;
  right: 0;
  width: 56px;
  height: 56px;
  cursor: nesw-resize;
}

.resize-handle.nw {
  top: 0;
  left: 0;
  width: 56px;
  height: 56px;
  cursor: nwse-resize;
}

.resize-handle.se {
  right: 0;
  bottom: 0;
  width: 56px;
  height: 56px;
  cursor: nwse-resize;
}

.resize-handle.sw {
  left: 0;
  bottom: 0;
  width: 56px;
  height: 56px;
  cursor: nesw-resize;
}

.toast {
  position: absolute;
  left: 0;
  bottom: 0;
  z-index: 1002;
  pointer-events: none;
  padding: 8px 12px;
  color: #fff;
  font-size: 12px;
  white-space: pre-wrap;
  background-color: rgba(0, 0, 0, 0.35);
}

.toast-error {
  pointer-events: auto;
  background-color: rgba(0, 0, 0, 0.55);
}


</style>
