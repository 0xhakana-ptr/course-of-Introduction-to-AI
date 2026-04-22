<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as PIXI from 'pixi.js'
import { getIpcRenderer } from './platform/electronIpc'
import Live2DConsole from './components/Live2DConsole.vue'
import AgentChat from './components/AgentChat.vue'

(window as any).PIXI = PIXI

const DEFAULT_MODEL_JSON_PATH = 'live2d/mianfeimox/llny.model3.json'
const CUBISM2_RUNTIME_PATH = 'live2d/live2d.min.js'
const CUBISM4_CORE_PATH = 'live2d/live2dcubismcore.min.js'
const CUBISM4_WASM_PATH = 'live2d/_em_module.wasm'
const CUBISM4_WASM_FALLBACK_PATH = 'live2d/live2dcubismcore.wasm'

const STARTUP_EXPRESSIONS_STORAGE_KEY = 'live2d.startupExpressions'

const rootRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const loadState = ref<'loading' | 'ready' | 'error'>('loading')
const errorText = ref('')

const ipcRenderer = getIpcRenderer()
const modelUrl = computed(() => new URL(DEFAULT_MODEL_JSON_PATH, window.location.href).toString())
const isModel3 = computed(() => DEFAULT_MODEL_JSON_PATH.toLowerCase().endsWith('.model3.json'))
const isCliMode = computed(() => new URLSearchParams(window.location.search).get('mode') === 'cli')
const isQuipMode = computed(() => new URLSearchParams(window.location.search).get('mode') === 'quip')
const isChatMode = computed(() => new URLSearchParams(window.location.search).get('mode') === 'chat')

const quipText = ref('')

// Hover fade + click-through passthrough:
// - Hovering the window fades it and enables click-through to underlying apps.
// - Holding Ctrl while hovering keeps the window interactive (no fade, no click-through).
const isHoveringWindow = ref(false)
const isCtrlHeld = ref(false)
const shouldFade = computed(() => isHoveringWindow.value && !isCtrlHeld.value && !isCliMode.value && !isChatMode.value)
const isInteractive = computed(() => isHoveringWindow.value && isCtrlHeld.value && !isCliMode.value && !isChatMode.value)
let lastIgnoreMouseEvents: boolean | null = null

let cursorPollTimer: number | null = null
let cursorPollInFlight = false

let pixiApp: PIXI.Application | null = null
let disposed = false
let resizeHandler: (() => void) | null = null
let layoutRaf: number | null = null

let currentModel: any = null
let currentModelSettingsUrl: string | null = null
let cachedMeta:
  | {
      motions: Record<string, number>
      expressions: string[]
    }
  | null = null

// Multi-expression stacking (Cubism4/model3 only)
const activeExpressionHandles = new Map<string, any>()

function getCubism4ExpressionManager(): any | null {
  const mgr =
    currentModel?.internalModel?.motionManager?.expressionManager ??
    currentModel?.internalModel?.expressionManager ??
    null
  if (!mgr || !mgr.queueManager || typeof mgr.loadExpression !== 'function') return null
  return mgr
}

function getExpressionDefinitions(mgr: any): Array<{ Name: string; File?: string }> {
  const defs = mgr?.definitions
  return Array.isArray(defs) ? (defs as any) : []
}

function resolveExpression(mgr: any, idOrIndex: unknown): { index: number; name: string } | null {
  const defs = getExpressionDefinitions(mgr)
  if (!defs.length) return null

  if (typeof idOrIndex === 'number' && Number.isFinite(idOrIndex)) {
    const idx = Math.trunc(idOrIndex)
    if (idx < 0 || idx >= defs.length) return null
    const name = String(defs[idx]?.Name ?? '')
    if (!name) return null
    return { index: idx, name }
  }

  const raw = typeof idOrIndex === 'string' ? idOrIndex.trim() : ''
  if (!raw) return null
  if (/^\d+$/.test(raw)) {
    const idx = Number.parseInt(raw, 10)
    return resolveExpression(mgr, idx)
  }

  const exactIdx = typeof mgr.getExpressionIndex === 'function' ? mgr.getExpressionIndex(raw) : -1
  if (typeof exactIdx === 'number' && exactIdx >= 0 && exactIdx < defs.length) {
    return { index: exactIdx, name: defs[exactIdx].Name }
  }

  const lower = raw.toLowerCase()
  const idx2 = defs.findIndex((d) => String(d?.Name ?? '').toLowerCase() === lower)
  if (idx2 >= 0) return { index: idx2, name: defs[idx2].Name }
  return null
}

function ensureExpressionStackingSupport(mgr: any) {
  const qm = mgr?.queueManager
  if (!qm || typeof qm.startMotion !== 'function') return
  if ((qm as any).__stackStartMotion) return

  const originalStartMotion = qm.startMotion.bind(qm)
  ;(qm as any).__stackStartMotion = (motion: any) => {
    const entries: any[] = Array.isArray((qm as any)._motions) ? (qm as any)._motions.filter(Boolean) : []
    const originals = entries.map((e) => e.setFadeOut)
    try {
      // Prevent startMotion from fading out existing motions.
      for (const e of entries) {
        if (e && typeof e.setFadeOut === 'function') e.setFadeOut = () => {}
      }
      // Follow library behavior (it uses performance.now() directly for expressions).
      return originalStartMotion(motion, false, performance.now())
    } finally {
      for (let i = 0; i < entries.length; i++) {
        if (entries[i]) entries[i].setFadeOut = originals[i]
      }
    }
  }
}

async function exprAdd(idOrIndex: unknown): Promise<{ ok: boolean; output: string }> {
  const mgr = getCubism4ExpressionManager()
  if (!mgr) return { ok: false, output: '当前模型不支持 Cubism4 多表情叠加（仅 model3 可用）' }

  ensureExpressionStackingSupport(mgr)
  const resolved = resolveExpression(mgr, idOrIndex)
  if (!resolved) return { ok: false, output: '找不到表情（用 list expressions 查看）' }
  if (activeExpressionHandles.has(resolved.name)) return { ok: true, output: `已存在：${resolved.name}` }

  const motion = await mgr.loadExpression(resolved.index)
  if (!motion) return { ok: false, output: `表情加载失败：${resolved.name}` }

  const stackStart = (mgr.queueManager as any).__stackStartMotion as undefined | ((m: any) => any)
  const handle = stackStart ? stackStart(motion) : mgr.queueManager.startMotion(motion, false, performance.now())
  activeExpressionHandles.set(resolved.name, handle)
  return { ok: true, output: `expr add ok: ${resolved.name}` }
}

function exprClear(): { ok: boolean; output: string } {
  const mgr = getCubism4ExpressionManager()
  if (!mgr) return { ok: false, output: '当前模型不支持 Cubism4 多表情叠加（仅 model3 可用）' }
  mgr.queueManager?.stopAllMotions?.()
  activeExpressionHandles.clear()
  return { ok: true, output: 'expr cleared' }
}

function exprRemove(idOrIndex: unknown): { ok: boolean; output: string } {
  const mgr = getCubism4ExpressionManager()
  if (!mgr) return { ok: false, output: '当前模型不支持 Cubism4 多表情叠加（仅 model3 可用）' }

  const resolved = resolveExpression(mgr, idOrIndex)
  if (!resolved) return { ok: false, output: '找不到表情（用 list expressions 查看）' }

  const handle = activeExpressionHandles.get(resolved.name)
  if (!handle) return { ok: true, output: `未启用：${resolved.name}` }

  const entry = mgr.queueManager?.getCubismMotionQueueEntry?.(handle)
  if (entry?.startFadeOut) {
    entry.startFadeOut(0.15, performance.now())
  } else if (entry?.release) {
    entry.release()
  }

  activeExpressionHandles.delete(resolved.name)
  return { ok: true, output: `expr removed: ${resolved.name}` }
}

function getActiveExpressionsText(): string {
  const names = [...activeExpressionHandles.keys()]
  if (!names.length) return '(none)'
  return names.join(', ')
}

function getStartupExpressionsFromConfig(): string[] {
  const params = new URLSearchParams(window.location.search)
  const fromUrl = params.get('startupExpr')
  const raw = (fromUrl ?? localStorage.getItem(STARTUP_EXPRESSIONS_STORAGE_KEY) ?? '').trim()
  if (!raw) return []
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}

async function applyStartupExpressions() {
  if (!currentModel || isCliMode.value) return
  const list = getStartupExpressionsFromConfig()
  if (!list.length) return

  exprClear()
  for (const e of list) {
    try {
      await exprAdd(e)
    } catch {
      // ignore
    }
  }
}

function closeApp() {
  ipcRenderer?.send('close-app')
}

function minimizeSelf() {
  ipcRenderer?.send('quip:minimize')
}

function setWindowClickThrough(ignore: boolean) {
  if (!ipcRenderer?.send) return
  if (lastIgnoreMouseEvents === ignore) return
  lastIgnoreMouseEvents = ignore
  ipcRenderer.send('window:setIgnoreMouseEvents', ignore)
}

function syncPassthroughState() {
  // When faded we want true click-through; otherwise interactive.
  setWindowClickThrough(shouldFade.value)
}

function stopCursorPoll() {
  if (cursorPollTimer != null) {
    window.clearInterval(cursorPollTimer)
    cursorPollTimer = null
  }
}

function startCursorPoll() {
  if (cursorPollTimer != null) return
  if (!ipcRenderer) return
  const rawInvoke = (ipcRenderer as any).invoke as unknown
  if (typeof rawInvoke !== 'function') return
  const invoke = rawInvoke.bind(ipcRenderer) as (channel: string, ...args: any[]) => Promise<any>
  cursorPollTimer = window.setInterval(async () => {
    if (cursorPollInFlight) return
    if (!isHoveringWindow.value) {
      stopCursorPoll()
      return
    }

    cursorPollInFlight = true
    try {
      const over = await invoke('window:isCursorOver')
      if (!over) {
        isHoveringWindow.value = false
        isCtrlHeld.value = false
        syncPassthroughState()
        stopCursorPoll()
      }
    } catch {
      // ignore
    } finally {
      cursorPollInFlight = false
    }
  }, 120)
}

function loadScriptOnce(srcUrl: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-src="${srcUrl}"]`) as HTMLScriptElement | null
    if (existing?.dataset.loaded === 'true') return resolve()
    if (existing) {
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', () => reject(new Error(`Failed to load ${srcUrl}`)))
      return
    }

    const s = document.createElement('script')
    s.async = true
    s.src = srcUrl
    s.dataset.src = srcUrl
    s.addEventListener('load', () => {
      s.dataset.loaded = 'true'
      resolve()
    })
    s.addEventListener('error', () => reject(new Error(`Failed to load ${srcUrl}`)))
    document.head.appendChild(s)
  })
}

function tokenizeCommand(input: string): string[] {
  const tokens: string[] = []
  const re = /"([^"]*)"|'([^']*)'|(\S+)/g
  let match: RegExpExecArray | null
  while ((match = re.exec(input))) {
    tokens.push(match[1] ?? match[2] ?? match[3])
  }
  return tokens
}

async function fetchModel3Meta(settingsUrl: string) {
  const res = await fetch(settingsUrl, { cache: 'no-store' })
  if (!res.ok) throw new Error(`无法读取模型设置：${res.status} ${res.statusText}`)
  const json = (await res.json()) as any

  const motionsRaw = json?.FileReferences?.Motions
  const motions: Record<string, number> = {}
  if (motionsRaw && typeof motionsRaw === 'object') {
    for (const [group, arr] of Object.entries(motionsRaw)) {
      motions[group] = Array.isArray(arr) ? arr.length : 0
    }
  }

  const expressionsRaw = json?.FileReferences?.Expressions
  const expressions = Array.isArray(expressionsRaw)
    ? expressionsRaw.map((e: any) => e?.Name).filter((x: any) => typeof x === 'string' && x.length > 0)
    : []

  return { motions, expressions }
}

async function ensureMetaLoaded(force = false) {
  if (!currentModelSettingsUrl) return null
  if (cachedMeta && !force) return cachedMeta
  cachedMeta = await fetchModel3Meta(currentModelSettingsUrl)
  return cachedMeta
}

async function executeLive2DCommand(commandLine: string): Promise<{ ok: boolean; output: string }> {
  const cmd = commandLine.trim()
  const args = tokenizeCommand(cmd)
  const head = (args[0] ?? '').toLowerCase()

  if (!head || head === 'help' || head === '?') {
    return {
      ok: true,
      output:
        `可用命令：\n` +
        `- help\n` +
        `- status\n` +
        `- meta [reload]\n` +
        `- list motions\n` +
        `- list expressions\n` +
        `- motion <group> [index]  （index 省略=随机）\n` +
        `- expr <name|index>       （设置为仅该表情）\n` +
        `- expr add <name|index>   （叠加一个表情）\n` +
        `- expr remove <name|index>（移除一个表情）\n` +
        `- expr clear              （清空所有叠加表情）\n` +
        `- expr active             （查看当前已叠加表情）\n` +
        `- startup expr <a,b,c>    （设置启动默认表情，逗号分隔）\n` +
        `- startup clear           （清除启动默认表情）\n` +
        `- startup show            （查看启动默认表情）\n` +
        `- quip <text>             （更新字幕窗口的打趣话语）\n` +
        `- stop                   （停止所有动作）\n` +
        `- focus <x> <y> [instant]（x/y: -1..1）\n` +
        `- tap <x> <y>            （x/y: 屏幕坐标，像素）\n`,
    }
  }

  if (head === 'status') {
    const loaded = Boolean(currentModel)
    return {
      ok: true,
      output:
        `loaded=${loaded}\n` +
        `modelUrl=${currentModelSettingsUrl ?? '(none)'}\n` +
        `type=${isModel3.value ? 'model3' : 'model'}\n`,
    }
  }

  if (head === 'meta') {
    const force = (args[1] ?? '').toLowerCase() === 'reload'
    const meta = await ensureMetaLoaded(force)
    if (!meta) return { ok: false, output: '未加载模型元数据（modelUrl missing）' }
    const motionGroups = Object.keys(meta.motions)
    return {
      ok: true,
      output:
        `motions: ${motionGroups.length} groups\n` +
        (motionGroups.length ? motionGroups.map((g) => `- ${g}: ${meta.motions[g]}`).join('\n') + '\n' : '') +
        `expressions: ${meta.expressions.length}\n` +
        (meta.expressions.length ? meta.expressions.map((e) => `- ${e}`).join('\n') + '\n' : ''),
    }
  }

  if (head === 'list') {
    const target = (args[1] ?? '').toLowerCase()
    const meta = await ensureMetaLoaded(false)
    if (!meta) return { ok: false, output: '未加载模型元数据（modelUrl missing）' }

    if (target === 'motions') {
      const groups = Object.keys(meta.motions)
      if (!groups.length) return { ok: true, output: '该模型未声明 Motions（FileReferences.Motions 为空）' }
      return { ok: true, output: groups.map((g) => `${g} (${meta.motions[g]})`).join('\n') }
    }
    if (target === 'expressions') {
      const mgr = getCubism4ExpressionManager()
      const defs = mgr ? getExpressionDefinitions(mgr) : []
      const names = defs.length ? defs.map((d) => d.Name) : meta.expressions
      if (!names.length) return { ok: true, output: '该模型未声明 Expressions（FileReferences.Expressions 为空）' }
      return { ok: true, output: names.map((n, i) => `${i}: ${n}`).join('\n') }
    }

    return { ok: false, output: '用法：list motions | list expressions' }
  }

  if (head === 'quip' || head === 'say') {
    const text = args.slice(1).join(' ').trim()
    if (!text) return { ok: false, output: '用法：quip <text>' }
    ipcRenderer?.send('quip:setText', text)
    return { ok: true, output: 'quip updated' }
  }

  if (!currentModel) return { ok: false, output: '模型尚未加载完成（currentModel is null）' }

  if (head === 'motion') {
    const group = args[1]
    if (!group) return { ok: false, output: '用法：motion <group> [index]' }
    const idxRaw = args[2]
    const index = idxRaw == null ? undefined : Number.parseInt(idxRaw, 10)
    const ok = await currentModel.motion(group, Number.isFinite(index as any) ? index : undefined)
    return { ok: Boolean(ok), output: ok ? 'motion started' : 'motion failed' }
  }

  if (head === 'expr' || head === 'expression') {
    const sub = (args[1] ?? '').toLowerCase()
    const rest = args.slice(2)

    // Cubism4 stacking commands
    if (sub === 'active') return { ok: true, output: `active: ${getActiveExpressionsText()}` }
    if (sub === 'clear' || sub === 'reset') return exprClear()

    if (sub === 'add') {
      const id = rest[0]
      if (!id) return { ok: false, output: '用法：expr add <name|index>' }
      return await exprAdd(id)
    }

    if (sub === 'remove' || sub === 'rm' || sub === 'del') {
      const id = rest[0]
      if (!id) return { ok: false, output: '用法：expr remove <name|index>' }
      return exprRemove(id)
    }

    if (sub === 'set' || sub === 'only') {
      const id = rest[0]
      if (!id) return { ok: false, output: '用法：expr set <name|index>' }
      exprClear()
      return await exprAdd(id)
    }

    // Backward compatible: `expr <id>` means set-only.
    const id = args[1]
    if (id == null || String(id).trim() === '') {
      return { ok: false, output: '用法：expr <name|index> | expr add/remove/clear/active' }
    }
    exprClear()
    const res = await exprAdd(id)
    // Fallback for non-model3 models: keep old behavior.
    if (!res.ok && typeof currentModel.expression === 'function') {
      const idNum = typeof id === 'string' && /^\d+$/.test(id) ? Number.parseInt(id, 10) : undefined
      const ok = await currentModel.expression(idNum ?? id)
      return { ok: Boolean(ok), output: ok ? 'expression set' : 'expression failed' }
    }
    return res
  }

  if (head === 'startup') {
    const sub = (args[1] ?? '').toLowerCase()
    if (!sub || sub === 'show') {
      const v = localStorage.getItem(STARTUP_EXPRESSIONS_STORAGE_KEY) ?? ''
      return { ok: true, output: v ? `startupExpr=${v}` : 'startupExpr=(none)' }
    }
    if (sub === 'clear') {
      localStorage.removeItem(STARTUP_EXPRESSIONS_STORAGE_KEY)
      return { ok: true, output: 'startupExpr cleared' }
    }
    if (sub === 'expr') {
      const raw = (args[2] ?? '').trim()
      if (!raw) return { ok: false, output: '用法：startup expr <a,b,c>' }
      localStorage.setItem(STARTUP_EXPRESSIONS_STORAGE_KEY, raw)
      return { ok: true, output: `startupExpr saved: ${raw}` }
    }
    return { ok: false, output: '用法：startup expr <a,b,c> | startup clear | startup show' }
  }

  if (head === 'stop') {
    const mgr = currentModel?.internalModel?.motionManager
    if (mgr?.stopAllMotions) {
      mgr.stopAllMotions()
      return { ok: true, output: 'stopped all motions' }
    }
    return { ok: false, output: '当前模型不支持 stopAllMotions' }
  }

  if (head === 'focus') {
    const x = Number.parseFloat(args[1] ?? '')
    const y = Number.parseFloat(args[2] ?? '')
    const instant = (args[3] ?? '').toLowerCase() === 'instant'
    if (!Number.isFinite(x) || !Number.isFinite(y)) return { ok: false, output: '用法：focus <x> <y> [instant]' }
    currentModel.focus(x, y, instant)
    return { ok: true, output: 'ok' }
  }

  if (head === 'tap') {
    const x = Number.parseFloat(args[1] ?? '')
    const y = Number.parseFloat(args[2] ?? '')
    if (!Number.isFinite(x) || !Number.isFinite(y)) return { ok: false, output: '用法：tap <x> <y>' }
    currentModel.tap(x, y)
    return { ok: true, output: 'ok' }
  }

  return { ok: false, output: `未知命令：${head}（输入 help 查看）` }
}

function waitForCubismCoreReady(): Promise<void> {
  const w = window as any
  const core = w.Live2DCubismCore
  const mod = core?._em_module ?? core

  if (mod && typeof mod.then === 'function') {
    return new Promise((resolve, reject) => {
      mod.then(() => resolve(), (err: any) => reject(err))
    })
  }

  return Promise.resolve()
}

function hasCubism4CoreExports(): boolean {
  const w = window as any
  const core = w.Live2DCubismCore
  if (!core) return false

  // Common Cubism4 core wrappers expose these symbols.
  return Boolean(core.Moc && core.Model && core.Version)
}

async function ensureRuntimeLoaded() {
  if (isModel3.value) {
    const w = window as any
    if (hasCubism4CoreExports()) return

    w.Live2DCubismCore = w.Live2DCubismCore ?? {}

    // Some Cubism4 cores are JS-only (no wasm). Others require fetching a wasm file.
    // We avoid hard-failing before loading core JS so both variants can work.
    if (!w.Live2DCubismCore.locateFile) {
      w.Live2DCubismCore.locateFile = (file: string) => {
        if (!file.endsWith('.wasm')) return file
        if (file.endsWith('_em_module.wasm')) {
          return new URL(CUBISM4_WASM_PATH, window.location.href).toString()
        }
        if (file.endsWith('live2dcubismcore.wasm')) {
          return new URL(CUBISM4_WASM_FALLBACK_PATH, window.location.href).toString()
        }
        return new URL(CUBISM4_WASM_PATH, window.location.href).toString()
      }
    }

    const coreUrl = new URL(CUBISM4_CORE_PATH, window.location.href).toString()
    await loadScriptOnce(coreUrl)
    await waitForCubismCoreReady()
    if (!hasCubism4CoreExports()) {
      throw new Error(
        `Cubism4 Core 初始化失败。\n` +
          `请确认以下文件都存在于 public/ 下并可访问：\n` +
          `- public/${CUBISM4_CORE_PATH}  (${coreUrl})\n` +
          `- （如果你的 core 需要 wasm）public/${CUBISM4_WASM_PATH} 或 public/${CUBISM4_WASM_FALLBACK_PATH}`,
      )
    }
    return
  }

  const w = window as any
  if (w.Live2D) return
  const runtimeUrl = new URL(CUBISM2_RUNTIME_PATH, window.location.href).toString()
  await loadScriptOnce(runtimeUrl)
  if (!w.Live2D) {
    throw new Error(
      `缺少 Cubism2 runtime：请将 live2d.min.js 放到 public/${CUBISM2_RUNTIME_PATH}，并确保可访问：${runtimeUrl}`,
    )
  }
}

onMounted(async () => {
  // Hover fade + click-through behavior.
  // Use pointer events so we can read e.ctrlKey even when the window isn't focused.
  const rootEl = rootRef.value
  if (rootEl && !isCliMode.value && !isChatMode.value) {
    const onEnter = (e: PointerEvent) => {
      isHoveringWindow.value = true
      isCtrlHeld.value = Boolean(e.ctrlKey)
      syncPassthroughState()
      startCursorPoll()
    }
    const onMove = (e: PointerEvent) => {
      const nextCtrl = Boolean(e.ctrlKey)
      if (isCtrlHeld.value !== nextCtrl) {
        isCtrlHeld.value = nextCtrl
        syncPassthroughState()
      }
    }
    const onLeave = () => {
      isHoveringWindow.value = false
      isCtrlHeld.value = false
      syncPassthroughState()
      stopCursorPoll()
    }

    rootEl.addEventListener('pointerenter', onEnter)
    rootEl.addEventListener('pointermove', onMove)
    rootEl.addEventListener('pointerleave', onLeave)

    onBeforeUnmount(() => {
      rootEl.removeEventListener('pointerenter', onEnter)
      rootEl.removeEventListener('pointermove', onMove)
      rootEl.removeEventListener('pointerleave', onLeave)
    })
  }

  if (isCliMode.value) {
    loadState.value = 'ready'
    return
  }

  if (isChatMode.value) {
    loadState.value = 'ready'
    return
  }

  if (isQuipMode.value) {
    loadState.value = 'ready'
    // Receive quip text updates.
    if (ipcRenderer?.on) {
      const handler = (_evt: any, text: any) => {
        quipText.value = typeof text === 'string' ? text : String(text ?? '')
      }
      ipcRenderer.on('quip:text', handler)
      onBeforeUnmount(() => {
        ipcRenderer.removeListener?.('quip:text', handler)
      })
    }
    return
  }

  const canvas = canvasRef.value
  if (!canvas) return

  disposed = false
  loadState.value = 'loading'
  errorText.value = ''

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

  let model: any = null
  const layoutModel = () => {
    if (!model || !pixiApp) return

    const viewportW = pixiApp.renderer.screen.width
    const viewportH = pixiApp.renderer.screen.height

    const bounds = typeof model.getLocalBounds === 'function' ? model.getLocalBounds() : null
    if (!bounds || !Number.isFinite(bounds.width) || !Number.isFinite(bounds.height)) return
    if (bounds.width <= 0 || bounds.height <= 0) return

    // Center model using pivot so motion/scale changes are more stable.
    model.pivot.set(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)

    // Make the character occupy more of the window.
    // Keep a tiny margin so it doesn't touch edges, and clamp position to avoid clipping.
    const marginRatio = 0.018
    const safeW = viewportW * (1 - marginRatio * 2)
    const safeH = viewportH * (1 - marginRatio * 2)

    const scale = Math.min(safeW / bounds.width, safeH / bounds.height)
    if (!Number.isFinite(scale) || scale <= 0) return
    model.scale.set(scale)

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
    model.position.set(x, y)
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
    await ensureRuntimeLoaded()

    const live2d = isModel3.value
      ? await import('pixi-live2d-display/cubism4')
      : await import('pixi-live2d-display/cubism2')
    const Live2DModel = (live2d as any).Live2DModel as { from: (url: string) => Promise<any> }
    model = await Live2DModel.from(modelUrl.value)
    currentModel = model
    currentModelSettingsUrl = modelUrl.value
    cachedMeta = null
    void ensureMetaLoaded(false)

    if (disposed) {
      model?.destroy?.()
      model = null
      return
    }

    pixiApp.stage.addChild(model as any)
    // Layout immediately and again on next tick to avoid occasional bounds instability.
    scheduleLayout()
    pixiApp.ticker.addOnce(() => scheduleLayout())
    pixiApp.ticker.addOnce(() => {
      void applyStartupExpressions()
    })
    loadState.value = 'ready'
  } catch (err) {
    if (disposed) return
    loadState.value = 'error'
    errorText.value =
      `Live2D 模型加载失败：${String(err)}\n` +
      `请确认存在 ${DEFAULT_MODEL_JSON_PATH}（位于 public/ 下），并且能被访问：${modelUrl.value}`
  }
})

onBeforeUnmount(() => {
  disposed = true
  stopCursorPoll()
  // Ensure window is interactive again when leaving.
  setWindowClickThrough(false)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  resizeHandler = null
  if (layoutRaf != null) cancelAnimationFrame(layoutRaf)
  layoutRaf = null
  currentModel = null
  currentModelSettingsUrl = null
  cachedMeta = null
  pixiApp?.destroy(true)
  pixiApp = null
})

// Main window command executor (called by Electron main via IPC)
if (ipcRenderer?.on && !isCliMode.value && !isQuipMode.value && !isChatMode.value) {
  ipcRenderer.on('live2d:command', async (_evt: any, payload: any) => {
    const id = payload?.id
    const cmd = payload?.cmd
    if (typeof id !== 'string' || typeof cmd !== 'string') return

    try {
      const res = await executeLive2DCommand(cmd)
      ipcRenderer.send('live2d:commandResult', { id, ok: res.ok, output: res.output })
    } catch (e) {
      ipcRenderer.send('live2d:commandResult', { id, ok: false, output: String(e) })
    }
  })
}
</script>

<template>
  <div ref="rootRef" class="root" :class="{ faded: shouldFade, interactive: isInteractive }">
    <div v-if="!isQuipMode && !isChatMode" class="test-badge">TEST</div>

    <AgentChat v-if="isChatMode" />

    <template v-if="isQuipMode">
      <div class="quip" :style="isInteractive ? '-webkit-app-region: drag' : '-webkit-app-region: no-drag'">
        <button
          v-if="ipcRenderer"
          class="minimize-btn"
          style="-webkit-app-region: no-drag"
          @click="minimizeSelf"
        >
          -
        </button>
        <div class="quip-text">{{ quipText || '...' }}</div>
      </div>
    </template>

    <template v-else-if="!isChatMode">
      <div class="titlebar" :style="isInteractive ? '-webkit-app-region: drag' : '-webkit-app-region: no-drag'">
        <button
          v-if="ipcRenderer && isInteractive"
          class="close-btn"
          style="-webkit-app-region: no-drag"
          @click="closeApp"
        >
          X 退出
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

.test-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 1001;
  pointer-events: none;
  padding: 4px 8px;
  border-radius: 6px;
  background-color: rgba(255, 0, 0, 0.85);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.titlebar {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 50px;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 20px;
  box-sizing: border-box;
  pointer-events: none;
}

.root.interactive .titlebar {
  pointer-events: auto;
}

.close-btn {
  cursor: pointer;
  padding: 5px 15px;
  background-color: rgba(255, 100, 100, 0.8);
  border: none;
  border-radius: 5px;
  color: #fff;
  font-weight: 700;
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

.quip {
  position: absolute;
  inset: 0;
  padding: 14px 18px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
}

.quip-text {
  color: rgba(255, 255, 255, 0.96);
  font-size: 20px;
  line-height: 1.25;
  text-align: center;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.55);
  user-select: none;
  pointer-events: none;
  white-space: pre-wrap;
}

.minimize-btn {
  position: absolute;
  top: 8px;
  right: 10px;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  border: none;
  background-color: rgba(160, 160, 160, 0.35);
  color: rgba(255, 255, 255, 0.9);
  font-size: 18px;
  line-height: 18px;
  cursor: pointer;
}

.minimize-btn:hover {
  background-color: rgba(160, 160, 160, 0.5);
}
</style>
