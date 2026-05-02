<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as PIXI from 'pixi.js'
import { getIpcRenderer } from './platform/electronIpc'
import Live2DConsole from './components/Live2DConsole.vue'
import AgentChat from './components/AgentChat.vue'
import { installLive2DFocusMouseTracking } from './mouseTracking'

(window as any).PIXI = PIXI

const DEFAULT_MODEL_JSON_PATH = 'live2d/pajamas_catcat/pajamas_catcat.model3.json'
//const DEFAULT_MODEL_JSON_PATH = 'live2d/mianfeimox/llny.model3.json'
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
const isMainLive2DMode = computed(() => !isCliMode.value && !isQuipMode.value && !isChatMode.value)

const quipText = ref('')

// Hover fade + click-through passthrough:
// - Hovering the window fades it and enables click-through to underlying apps.
// - Holding Ctrl while hovering keeps the window interactive (no fade, no click-through).
const isHoveringWindow = ref(false)
const isCtrlHeld = ref(false)
const isManualResizing = ref(false)
const shouldFade = computed(
  () => isHoveringWindow.value && !isCtrlHeld.value && !isCliMode.value && !isChatMode.value && !isManualResizing.value,
)
const isInteractive = computed(() => isHoveringWindow.value && isCtrlHeld.value && !isCliMode.value && !isChatMode.value)
const showCtrlResizeHint = computed(() => (isInteractive.value || isManualResizing.value) && isMainLive2DMode.value)
let lastIgnoreMouseEvents: boolean | null = null

let cursorPollTimer: number | null = null
let cursorPollInFlight = false

const CURSOR_POLL_FAST_MS = 80
const CURSOR_POLL_SLOW_MS = 260

let pixiApp: PIXI.Application | null = null
let disposed = false
let resizeHandler: (() => void) | null = null
let layoutRaf: number | null = null
let disposeMouseTracking: null | (() => void) = null

let currentModel: any = null
let currentModelSettingsUrl: string | null = null

type ExpressionTagMapFile = {
  version?: number
  map?: Record<string, string | string[] | null>
}

let cachedExpressionTagMap:
  | { sourceUrl: string; map: Record<string, string | string[] | null> }
  | null = null
let expressionTagMapPromise: Promise<{ sourceUrl: string; map: Record<string, string | string[] | null> } | null> | null = null

type Live2DAction = {
  id: string
  type: 'expression' | 'motion'
  label: string
}

type ModelMeta = {
  motions: Record<string, number>
  expressions: string[]
  motionFiles?: string[]
  expressionFiles?: string[]
}

let cachedMeta:
  | ModelMeta
  | null = null
let metaLoadPromise: Promise<ModelMeta | null> | null = null
let lastMetaError: string | null = null

// Multi-expression stacking (Cubism4/model3 only)
const activeExpressionHandles = new Map<string, any>()

// Pinned (startup) expressions:
// - They are treated as the base layer (e.g. watermark-removal expression).
// - Later `mode:set` expression operations must NOT fade them out.
const pinnedExpressionHandleKeys = new Set<string>()

let cubism4ModulePromise: Promise<any> | null = null
async function getCubism4Module(): Promise<any> {
  cubism4ModulePromise = cubism4ModulePromise ?? import('pixi-live2d-display/cubism4')
  return await cubism4ModulePromise
}

function isExpressionActionId(s: string): boolean {
  return s.startsWith('expr/') || s.startsWith('expr/@name/')
}

function isMotionActionId(s: string): boolean {
  return s.startsWith('motion/') || s.startsWith('motion/@group/')
}

function makeExpressionNameActionId(name: string): string {
  return `expr/@name/${encodeURIComponent(name)}`
}

function actionIdLabel(id: string): string {
  if (id.startsWith('expr/@name/')) return decodeURIComponent(id.slice('expr/@name/'.length))
  if (id.startsWith('expr/')) return id.slice('expr/'.length)
  if (id.startsWith('motion/')) return id.slice('motion/'.length)
  if (id.startsWith('motion/@group/')) {
    const rest = id.slice('motion/@group/'.length)
    const parts = rest.split('/')
    const group = decodeURIComponent(parts[0] ?? '')
    const idx = parts[1] ? parts[1] : ''
    return idx ? `${group}[${idx}]` : `${group}[*]`
  }
  return id
}

function looksLikeExpressionFile(arg: unknown): boolean {
  const s = typeof arg === 'string' ? arg.trim().toLowerCase() : ''
  return Boolean(s) && (s.endsWith('.exp3.json') || s.includes('.exp3.json?') || s.includes('.exp3.json#'))
}

function looksLikeMotionFile(arg: unknown): boolean {
  const s = typeof arg === 'string' ? arg.trim().toLowerCase() : ''
  return Boolean(s) && (s.endsWith('.motion3.json') || s.includes('.motion3.json?') || s.includes('.motion3.json#'))
}

function resolveModelRelativeUrl(fileOrUrl: string): string {
  const base = currentModelSettingsUrl ?? modelUrl.value
  if (!base) throw new Error('modelUrl is empty')
  const baseDir = new URL('.', base)
  return new URL(fileOrUrl, baseDir).toString()
}

async function fetchJsonObject(url: string): Promise<any> {
  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) throw new Error(`HTTP ${res.status} when fetching ${url}`)
  return await res.json()
}

function stripJsonComments(input: string): string {
  // Minimal JSONC support: remove // line comments.
  return input.replace(/^\s*\/\/.*$/gm, '')
}

function expressionActionIdToHandleKey(id: string): string | null {
  if (id.startsWith('expr/') && id.toLowerCase().includes('.exp3.json')) return `file:${id.slice('expr/'.length)}`
  if (id.startsWith('expr/@name/')) return id
  return null
}

function fadeOutAndRemoveExpressionHandle(key: string) {
  const mgr = getCubism4ExpressionPlaybackManager()
  if (!mgr) {
    activeExpressionHandles.delete(key)
    return
  }

  const handle = activeExpressionHandles.get(key)
  if (!handle) return

  const entry = mgr.queueManager?.getCubismMotionQueueEntry?.(handle)
  if (entry?.startFadeOut) {
    entry.startFadeOut(0.15, performance.now())
  } else if (entry?.release) {
    entry.release()
  }

  activeExpressionHandles.delete(key)
}

function exprClearNonPinned(): { ok: boolean; output: string } {
  const mgr = getCubism4ExpressionPlaybackManager()
  if (!mgr) return { ok: false, output: '当前模型不支持 Cubism4 多表情叠加（仅 model3 可用）' }

  const entries = [...activeExpressionHandles.keys()]
  for (const key of entries) {
    if (pinnedExpressionHandleKeys.has(key)) continue
    fadeOutAndRemoveExpressionHandle(key)
  }

  return { ok: true, output: 'expr cleared (non-pinned)' }
}

async function resolveStartupExpressionTokenToConcreteActionId(token: string): Promise<string | null> {
  const raw = token.trim()
  if (!raw) return null

  if (raw.toLowerCase().startsWith('tag:')) {
    const tag = raw.slice('tag:'.length)
    const resolved = await resolveExpressionTagToActionId(tag)
    return resolved.ok && resolved.id ? resolved.id : null
  }
  if (isExpressionActionId(raw)) return raw
  if (looksLikeExpressionFile(raw)) return `expr/${raw}`
  return makeExpressionNameActionId(raw)
}

async function fetchJsoncObject(url: string): Promise<any> {
  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) throw new Error(`HTTP ${res.status} when fetching ${url}`)
  const text = await res.text()
  const stripped = stripJsonComments(text)
  return JSON.parse(stripped)
}

async function tryLoadExpressionTagMapFromUrl(url: string): Promise<{ sourceUrl: string; map: Record<string, string | string[] | null> } | null> {
  try {
    const json = (await fetchJsoncObject(url)) as ExpressionTagMapFile
    const map = json?.map
    if (!map || typeof map !== 'object') return null
    return { sourceUrl: url, map }
  } catch {
    return null
  }
}

async function ensureExpressionTagMapLoaded(force = false) {
  if (cachedExpressionTagMap && !force) return cachedExpressionTagMap
  if (expressionTagMapPromise && !force) return await expressionTagMapPromise

  expressionTagMapPromise = (async () => {
    const base = currentModelSettingsUrl ?? modelUrl.value
    if (base) {
      const baseDir = new URL('.', base)
      const perModelUrl = new URL('expression-map.jsonc', baseDir).toString()
      const perModel = await tryLoadExpressionTagMapFromUrl(perModelUrl)
      if (perModel) {
        cachedExpressionTagMap = perModel
        return perModel
      }
    }

    const globalUrl = new URL('live2d/expression-map.jsonc', window.location.href).toString()
    const globalMap = await tryLoadExpressionTagMapFromUrl(globalUrl)
    if (globalMap) {
      cachedExpressionTagMap = globalMap
      return globalMap
    }

    return null
  })()

  try {
    return await expressionTagMapPromise
  } finally {
    expressionTagMapPromise = null
  }
}

function pickOne<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

async function resolveExpressionTagToActionId(tag: string): Promise<{ ok: boolean; id?: string; reason?: string }> {
  const rawTag = tag.trim()
  if (!rawTag) return { ok: false, reason: 'empty tag' }

  const loaded = await ensureExpressionTagMapLoaded(false)
  const map = loaded?.map
  if (!map) return { ok: false, reason: 'mapping file not found' }

  const v = map[rawTag]
  if (v == null) return { ok: false, reason: 'tag disabled or not mapped' }

  const pick = Array.isArray(v) ? (v.length ? pickOne(v) : '') : String(v)
  const id = (pick ?? '').trim()
  if (!id) return { ok: false, reason: 'empty mapping target' }

  // Accept shorthand targets:
  // - if looks like file => treat as expr/<file>
  // - if plain name => treat as expr/@name/<name>
  if (isExpressionActionId(id)) return { ok: true, id }
  if (looksLikeExpressionFile(id)) return { ok: true, id: `expr/${id}` }
  return { ok: true, id: makeExpressionNameActionId(id) }
}

async function playExpressionFromFile(
  fileArg: string,
  mode: 'add' | 'set' = 'set',
): Promise<{ ok: boolean; output: string }> {
  const mgr = await ensureCubism4ExpressionPlaybackManager()
  if (!mgr) {
    return {
      ok: false,
      output:
        '当前模型无法播放 Cubism4 表情文件（可能不是 Cubism4/model3，或 model3.json 未初始化 expressionManager）。',
    }
  }

  const fileKey = `file:${fileArg}`
  if (mode === 'add' && activeExpressionHandles.has(fileKey)) {
    return { ok: true, output: `已存在：${fileArg}` }
  }

  const fileUrl = resolveModelRelativeUrl(fileArg)
  const json = await fetchJsonObject(fileUrl)

  const cubism4 = (await getCubism4Module()) as any
  const ExpressionMotion = cubism4?.CubismExpressionMotion
  if (!ExpressionMotion || typeof ExpressionMotion.create !== 'function') {
    return { ok: false, output: '运行时缺少 CubismExpressionMotion.create，无法从 exp3.json 创建表情' }
  }

  // Keep pinned startup expressions alive:
  // - When `set`, only clear non-pinned expressions.
  // - Always start motions in a non-fade-out way when pinned exist.
  if (mode === 'set') {
    if (pinnedExpressionHandleKeys.size) {
      exprClearNonPinned()
      ensureExpressionStackingSupport(mgr)
    } else {
      mgr.queueManager?.stopAllMotions?.()
      activeExpressionHandles.clear()
    }
  } else {
    ensureExpressionStackingSupport(mgr)
  }

  const motion = ExpressionMotion.create(json)
  const stackStart = (mgr.queueManager as any).__stackStartMotion as undefined | ((m: any) => any)
  const handle =
    (mode === 'add' || (mode === 'set' && pinnedExpressionHandleKeys.size)) && stackStart
      ? stackStart(motion)
      : mgr.queueManager.startMotion(motion, false, performance.now())

  activeExpressionHandles.set(fileKey, handle)
  return { ok: true, output: `expr ${mode} ok: ${fileArg}` }
}

function removeExpressionFile(fileArg: string): { ok: boolean; output: string } {
  const mgr = getCubism4ExpressionPlaybackManager()
  if (!mgr) return { ok: false, output: '当前模型缺少 expressionManager，无法移除该文件表情' }

  const fileKey = `file:${fileArg}`
  const handle = activeExpressionHandles.get(fileKey)
  if (!handle) return { ok: true, output: `未启用：${fileArg}` }

  const entry = mgr.queueManager?.getCubismMotionQueueEntry?.(handle)
  if (entry?.startFadeOut) {
    entry.startFadeOut(0.15, performance.now())
  } else if (entry?.release) {
    entry.release()
  }

  activeExpressionHandles.delete(fileKey)
  return { ok: true, output: `expr removed: ${fileArg}` }
}

async function playMotionFromFile(fileArg: string): Promise<{ ok: boolean; output: string }> {
  const motionMgr = currentModel?.internalModel?.motionManager
  const qm = motionMgr?.queueManager
  if (!qm || typeof qm.startMotion !== 'function') return { ok: false, output: '当前模型不支持从 motion3.json 直接播放动作' }

  const fileUrl = resolveModelRelativeUrl(fileArg)
  const json = await fetchJsonObject(fileUrl)

  const cubism4 = (await getCubism4Module()) as any
  const CubismMotion = cubism4?.CubismMotion
  if (!CubismMotion || typeof CubismMotion.create !== 'function') {
    return { ok: false, output: '运行时缺少 CubismMotion.create，无法从 motion3.json 创建动作' }
  }

  const motion = CubismMotion.create(json)
  qm.startMotion(motion, true, performance.now())
  return { ok: true, output: `motion file started: ${fileArg}` }
}

function getCubism4ExpressionManager(): any | null {
  const mgr =
    currentModel?.internalModel?.motionManager?.expressionManager ??
    currentModel?.internalModel?.expressionManager ??
    null
  if (!mgr || !mgr.queueManager || typeof mgr.loadExpression !== 'function') return null
  return mgr
}

function getCubism4ExpressionPlaybackManager(): any | null {
  const mgr =
    currentModel?.internalModel?.motionManager?.expressionManager ??
    currentModel?.internalModel?.expressionManager ??
    null
  if (!mgr || !mgr.queueManager || typeof mgr.queueManager.startMotion !== 'function') return null
  return mgr
}

async function ensureCubism4ExpressionPlaybackManager(): Promise<any | null> {
  const existing = getCubism4ExpressionPlaybackManager()
  if (existing) return existing

  const motionMgr = currentModel?.internalModel?.motionManager
  if (!motionMgr || !motionMgr.settings) return null

  try {
    const cubism4 = (await getCubism4Module()) as any
    const ExpressionManagerCtor = cubism4?.Cubism4ExpressionManager
    if (typeof ExpressionManagerCtor !== 'function') return null

    const mgr = new ExpressionManagerCtor(motionMgr.settings)
    ;(motionMgr as any).expressionManager = mgr
    if (currentModel?.internalModel) {
      ;(currentModel.internalModel as any).expressionManager = mgr
    }
    return mgr
  } catch {
    return null
  }
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

async function resolveExpressionCliArgToActionId(idOrIndex: unknown): Promise<string | null> {
  const raw = typeof idOrIndex === 'string' ? idOrIndex.trim() : ''
  if (!raw) return null

  if (raw.toLowerCase().startsWith('tag:')) return raw
  if (isExpressionActionId(raw)) return raw
  if (looksLikeExpressionFile(raw)) return `expr/${raw}`

  // Try to resolve index/name to a canonical name (if definitions exist)
  const mgr = getCubism4ExpressionManager()
  const resolved = mgr ? resolveExpression(mgr, raw) : null
  const name = resolved?.name ?? raw
  return makeExpressionNameActionId(name)
}

function resolveMotionCliArgToActionId(groupOrFile: unknown, indexArg?: unknown): string | null {
  const raw = typeof groupOrFile === 'string' ? groupOrFile.trim() : ''
  if (!raw) return null

  if (isMotionActionId(raw)) return raw
  if (looksLikeMotionFile(raw)) return `motion/${raw}`

  const group = raw
  const idxRaw = typeof indexArg === 'string' ? indexArg.trim() : ''
  if (!idxRaw) return `motion/@group/${encodeURIComponent(group)}`
  const idx = Number.parseInt(idxRaw, 10)
  if (!Number.isFinite(idx)) return `motion/@group/${encodeURIComponent(group)}`
  return `motion/@group/${encodeURIComponent(group)}/${idx}`
}

async function exprAdd(idOrIndex: unknown): Promise<{ ok: boolean; output: string }> {
  const mgr = getCubism4ExpressionManager()
  if (!mgr) return { ok: false, output: '当前模型不支持 Cubism4 多表情叠加（仅 model3 可用）' }

  ensureExpressionStackingSupport(mgr)
  const resolved = resolveExpression(mgr, idOrIndex)
  if (!resolved) return { ok: false, output: '找不到表情（用 list expressions 查看）' }
  const key = makeExpressionNameActionId(resolved.name)
  if (activeExpressionHandles.has(key)) return { ok: true, output: `已存在：${resolved.name}` }

  const motion = await mgr.loadExpression(resolved.index)
  if (!motion) return { ok: false, output: `表情加载失败：${resolved.name}` }

  const stackStart = (mgr.queueManager as any).__stackStartMotion as undefined | ((m: any) => any)
  const handle = stackStart ? stackStart(motion) : mgr.queueManager.startMotion(motion, false, performance.now())
  activeExpressionHandles.set(key, handle)
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

  const key = makeExpressionNameActionId(resolved.name)
  const handle = activeExpressionHandles.get(key)
  if (!handle) return { ok: true, output: `未启用：${resolved.name}` }

  const entry = mgr.queueManager?.getCubismMotionQueueEntry?.(handle)
  if (entry?.startFadeOut) {
    entry.startFadeOut(0.15, performance.now())
  } else if (entry?.release) {
    entry.release()
  }

  activeExpressionHandles.delete(key)
  return { ok: true, output: `expr removed: ${resolved.name}` }
}

function getActiveExpressionsText(): string {
  const ids = [...activeExpressionHandles.keys()]
  if (!ids.length) return '(none)'
  return ids.map((id) => actionIdLabel(id)).join(', ')
}

function getStartupExpressionsFromConfig(): string[] {
  const params = new URLSearchParams(window.location.search)
  const fromUrl = params.get('startupExpr')
  const raw = (fromUrl ?? localStorage.getItem(STARTUP_EXPRESSIONS_STORAGE_KEY) ?? '').trim()
  if (!raw) return []

  // Backward compatible:
  // - Old values: comma-separated expression names
  // - New values: comma-separated action IDs (expr/...)
  return raw
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}

async function applyStartupExpressions() {
  if (!currentModel || isCliMode.value) return
  const list = getStartupExpressionsFromConfig()
  if (!list.length) return

  // Treat startup expressions as pinned base layer.
  pinnedExpressionHandleKeys.clear()

  // Resolve tokens to concrete action IDs. First successful one uses `set`, rest `add`.
  let didSet = false
  for (const token of list) {
    try {
      const id = await resolveStartupExpressionTokenToConcreteActionId(token)
      if (!id) continue
      const res = await playLive2DAction({ type: 'expression', id, mode: didSet ? 'add' : 'set' })
      if (res.ok) {
        didSet = true
        const key = expressionActionIdToHandleKey(id)
        if (key) pinnedExpressionHandleKeys.add(key)
      }
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
  if (isManualResizing.value) {
    setWindowClickThrough(false)
    return
  }
  setWindowClickThrough(shouldFade.value)
}

type ManualResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'
let manualResizePointerId: number | null = null

function startManualResize(dir: ManualResizeDir, e: PointerEvent) {
  if (!ipcRenderer?.send) return
  // Only allow resizing when interactive (Ctrl-held) to keep the original click-through UX.
  if (!isInteractive.value) return
  e.preventDefault()
  e.stopPropagation()

  isManualResizing.value = true
  syncPassthroughState()

  manualResizePointerId = typeof e.pointerId === 'number' ? e.pointerId : null
  try {
    ;(e.currentTarget as any)?.setPointerCapture?.(e.pointerId)
  } catch {
    // ignore
  }

  ipcRenderer.send('window:manualResizeStart', { dir })
}

function stopManualResize(e?: PointerEvent) {
  if (!ipcRenderer?.send) return
  if (!isManualResizing.value) return

  e?.preventDefault?.()
  e?.stopPropagation?.()

  try {
    if (manualResizePointerId != null) {
      ;(e?.currentTarget as any)?.releasePointerCapture?.(manualResizePointerId)
    }
  } catch {
    // ignore
  }
  manualResizePointerId = null

  ipcRenderer.send('window:manualResizeEnd')
  isManualResizing.value = false
  syncPassthroughState()
}

function stopCursorPoll() {
  if (cursorPollTimer != null) {
    window.clearTimeout(cursorPollTimer)
    cursorPollTimer = null
  }
}

function startCursorPoll() {
  if (cursorPollTimer != null) return
  if (!ipcRenderer) return
  const rawInvoke = (ipcRenderer as any).invoke as unknown
  if (typeof rawInvoke !== 'function') return
  const invoke = rawInvoke.bind(ipcRenderer) as (channel: string, ...args: any[]) => Promise<any>

  const tick = async () => {
    if (disposed) return

    // Persistent fallback hover detection:
    // - Pointerenter/pointerleave can be flaky on transparent frameless windows,
    //   especially when we toggle click-through.
    // - Poll main process bounds to detect enter/leave reliably.
    // Adaptive frequency: fast when hovering/faded, slower otherwise to reduce IPC load.
    const nextDelay = shouldFade.value || isHoveringWindow.value ? CURSOR_POLL_FAST_MS : CURSOR_POLL_SLOW_MS

    cursorPollTimer = window.setTimeout(() => {
      cursorPollTimer = null
      void tick()
    }, nextDelay)

    if (cursorPollInFlight) return
    cursorPollInFlight = true
    try {
      const over = await invoke('window:isCursorOver')
      if (over && !isHoveringWindow.value) {
        isHoveringWindow.value = true
        // ctrl state may be unknown until we get a move event; keep current value.
        syncPassthroughState()
      } else if (!over && isHoveringWindow.value) {
        isHoveringWindow.value = false
        isCtrlHeld.value = false
        syncPassthroughState()
      }
    } catch {
      // ignore
    } finally {
      cursorPollInFlight = false
    }
  }

  void tick()
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

  // Compatibility: some models keep exp/motion as separate files but do not declare them in model3.json.
  // In Electron (nodeIntegration enabled), we can ask main process to list sidecar files in the same folder.
  let expressionFiles: string[] | undefined
  let motionFiles: string[] | undefined
  try {
    const invoke = (ipcRenderer as any)?.invoke as undefined | ((channel: string, ...args: any[]) => Promise<any>)
    if (typeof invoke === 'function') {
      const resp = await invoke('live2d:listSidecarFiles', settingsUrl)
      if (resp?.ok) {
        expressionFiles = Array.isArray(resp.expressions) ? resp.expressions.filter((s: any) => typeof s === 'string') : undefined
        motionFiles = Array.isArray(resp.motions) ? resp.motions.filter((s: any) => typeof s === 'string') : undefined
      }
    }
  } catch {
    // ignore
  }

  return { motions, expressions, expressionFiles, motionFiles }
}

async function ensureMetaLoaded(force = false) {
  const settingsUrl = currentModelSettingsUrl ?? modelUrl.value
  if (!settingsUrl) return null
  if (cachedMeta && !force) return cachedMeta

  if (metaLoadPromise && !force) return await metaLoadPromise

  lastMetaError = null
  metaLoadPromise = (async () => {
    try {
      const meta = await fetchModel3Meta(settingsUrl)
      cachedMeta = meta
      return meta
    } catch (e) {
      const msg = String(e ?? '')
      lastMetaError = msg
      return null
    } finally {
      metaLoadPromise = null
    }
  })()

  return await metaLoadPromise
}

function buildLive2DActionCatalog(): {
  ok: boolean
  error?: string
  modelUrl?: string
  expressions: Live2DAction[]
  motions: Live2DAction[]
} {
  if (!currentModel) {
    return { ok: false, error: '模型尚未加载完成（currentModel is null）', expressions: [], motions: [] }
  }

  const expressions: Live2DAction[] = []
  const motions: Live2DAction[] = []
  const seen = new Set<string>()

  const meta = cachedMeta

  // Expressions: prefer runtime definitions, then sidecar files.
  const exprMgr = getCubism4ExpressionPlaybackManager()
  const exprDefs = Array.isArray(exprMgr?.definitions) ? (exprMgr.definitions as any[]) : []
  for (const d of exprDefs) {
    const name = typeof d?.Name === 'string' ? d.Name : ''
    const file = typeof d?.File === 'string' ? d.File : ''
    const id = file && file.toLowerCase().includes('.exp3.json') ? `expr/${file}` : name ? `expr/@name/${encodeURIComponent(name)}` : ''
    if (!id || seen.has(id)) continue
    seen.add(id)
    expressions.push({ id, type: 'expression', label: name || file || id })
  }

  const exprFiles = Array.isArray(meta?.expressionFiles) ? meta!.expressionFiles! : []
  for (const f of exprFiles) {
    const file = typeof f === 'string' ? f : ''
    if (!file) continue
    const id = `expr/${file}`
    if (seen.has(id)) continue
    seen.add(id)
    expressions.push({ id, type: 'expression', label: file })
  }

  // Motions: prefer runtime definitions, then sidecar files.
  const motionMgr = currentModel?.internalModel?.motionManager
  const defs = motionMgr?.definitions
  if (defs && typeof defs === 'object') {
    for (const [group, list] of Object.entries(defs as Record<string, any[]>)) {
      if (!Array.isArray(list)) continue
      for (let i = 0; i < list.length; i++) {
        const d = list[i]
        const file = typeof d?.File === 'string' ? d.File : ''
        const id = file && file.toLowerCase().includes('.motion3.json') ? `motion/${file}` : `motion/@group/${encodeURIComponent(group)}/${i}`
        if (seen.has(id)) continue
        seen.add(id)
        const label = file ? `${group}[${i}] ${file}` : `${group}[${i}]`
        motions.push({ id, type: 'motion', label })
      }
    }
  }

  const motionFiles = Array.isArray(meta?.motionFiles) ? meta!.motionFiles! : []
  for (const f of motionFiles) {
    const file = typeof f === 'string' ? f : ''
    if (!file) continue
    const id = `motion/${file}`
    if (seen.has(id)) continue
    seen.add(id)
    motions.push({ id, type: 'motion', label: file })
  }

  return {
    ok: true,
    modelUrl: currentModelSettingsUrl ?? modelUrl.value,
    expressions,
    motions,
  }
}

function stopAllLive2D(): { ok: boolean; output: string } {
  const motionMgr = currentModel?.internalModel?.motionManager
  motionMgr?.stopAllMotions?.()
  const exprMgr = getCubism4ExpressionPlaybackManager()
  exprMgr?.queueManager?.stopAllMotions?.()
  activeExpressionHandles.clear()
  return { ok: true, output: 'stopped' }
}

async function playLive2DAction(payload: {
  type: 'expression' | 'motion'
  id: string
  mode?: 'set' | 'add'
}): Promise<{ ok: boolean; output: string }> {
  if (!currentModel) return { ok: false, output: '模型尚未加载完成（currentModel is null）' }

  const type = payload.type
  const id = String(payload.id ?? '')
  const mode = payload.mode === 'add' ? 'add' : 'set'

  if (type === 'expression') {
    if (id.startsWith('tag:')) {
      const tag = id.slice('tag:'.length)
      const resolved = await resolveExpressionTagToActionId(tag)
      if (!resolved.ok || !resolved.id) {
        return { ok: false, output: `tag 映射失败：${tag}（${resolved.reason ?? 'unknown'}）` }
      }
      return await playLive2DAction({ type: 'expression', id: resolved.id, mode })
    }
    if (id.startsWith('expr/') && id.toLowerCase().includes('.exp3.json')) {
      const file = id.slice('expr/'.length)
      return await playExpressionFromFile(file, mode)
    }
    if (id.startsWith('expr/@name/')) {
      const name = decodeURIComponent(id.slice('expr/@name/'.length))
      if (mode === 'set') {
        if (pinnedExpressionHandleKeys.size) exprClearNonPinned()
        else exprClear()
      }
      return await exprAdd(name)
    }
    // Fallback: treat as name.
    if (mode === 'set') {
      if (pinnedExpressionHandleKeys.size) exprClearNonPinned()
      else exprClear()
    }
    return await exprAdd(id)
  }

  if (type === 'motion') {
    if (id.startsWith('motion/') && id.toLowerCase().includes('.motion3.json')) {
      const file = id.slice('motion/'.length)
      return await playMotionFromFile(file)
    }
    if (id.startsWith('motion/@group/')) {
      const rest = id.slice('motion/@group/'.length)
      const parts = rest.split('/')
      const group = decodeURIComponent(parts[0] ?? '')
      const idx = Number.parseInt(parts[1] ?? '', 10)
      if (!group) return { ok: false, output: 'motion id 缺少 group' }
      const ok = await currentModel.motion(group, Number.isFinite(idx) ? idx : undefined)
      return { ok: Boolean(ok), output: ok ? 'motion started' : 'motion failed' }
    }

    // Fallback: treat as group.
    const ok = await currentModel.motion(id)
    return { ok: Boolean(ok), output: ok ? 'motion started' : 'motion failed' }
  }

  return { ok: false, output: `unknown type: ${type}` }
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
        `- motion <file.motion3.json>（按文件播放动作）\n` +
        `- expr <name|index>       （设置为仅该表情）\n` +
        `- expr <file.exp3.json>    （按文件设置表情）\n` +
        `- expr add <name|index>   （叠加一个表情）\n` +
        `- expr add <file.exp3.json>（按文件叠加表情）\n` +
        `- expr remove <name|index>（移除一个表情）\n` +
        `- expr remove <file.exp3.json>（移除按文件叠加的表情）\n` +
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
    if (!meta) {
      return {
        ok: false,
        output:
          '未加载模型元数据。' +
          (lastMetaError ? `\n原因：${lastMetaError}` : '') +
          `\nmodelUrl=${currentModelSettingsUrl ?? modelUrl.value ?? '(none)'}`,
      }
    }
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
    void ensureMetaLoaded(false)

    if (target === 'motions') {
      const cat = buildLive2DActionCatalog()
      if (!cat.ok) return { ok: false, output: cat.error ?? 'list failed' }
      if (!cat.motions.length) return { ok: true, output: '(none)' }
      return {
        ok: true,
        output: cat.motions.map((a) => `${a.id}  # ${a.label}`).join('\n'),
      }
    }
    if (target === 'expressions') {
      const cat = buildLive2DActionCatalog()
      if (!cat.ok) return { ok: false, output: cat.error ?? 'list failed' }
      if (!cat.expressions.length) return { ok: true, output: '(none)' }
      return {
        ok: true,
        output: cat.expressions.map((a) => `${a.id}  # ${a.label}`).join('\n'),
      }
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
    const id = resolveMotionCliArgToActionId(args[1], args[2])
    if (!id) return { ok: false, output: '用法：motion <group> [index] | motion <file.motion3.json>' }
    const res = await playLive2DAction({ type: 'motion', id })
    return { ok: res.ok, output: res.output }
  }

  if (head === 'expr' || head === 'expression') {
    const sub = (args[1] ?? '').toLowerCase()
    const rest = args.slice(2)

    // Cubism4 stacking commands
    if (sub === 'active') return { ok: true, output: `active: ${getActiveExpressionsText()}` }
    if (sub === 'clear' || sub === 'reset') return exprClear()

    if (sub === 'add') {
      const id = rest[0]
      if (!id) return { ok: false, output: '用法：expr add <name|index> | expr add <file.exp3.json>' }
      const actionId = await resolveExpressionCliArgToActionId(id)
      if (!actionId) return { ok: false, output: '无效表情参数' }
      const res = await playLive2DAction({ type: 'expression', id: actionId, mode: 'add' })
      return { ok: res.ok, output: res.output }
    }

    if (sub === 'remove' || sub === 'rm' || sub === 'del') {
      const id = rest[0]
      if (!id) return { ok: false, output: '用法：expr remove <name|index> | expr remove <file.exp3.json>' }
      const actionId = await resolveExpressionCliArgToActionId(id)
      if (!actionId) return { ok: false, output: '无效表情参数' }

      if (actionId.toLowerCase().startsWith('tag:')) {
        const tag = actionId.slice('tag:'.length)
        const resolved = await resolveExpressionTagToActionId(tag)
        if (!resolved.ok || !resolved.id) return { ok: false, output: `tag 映射失败：${tag}` }
        // Remove the resolved concrete action
        if (resolved.id.startsWith('expr/') && resolved.id.toLowerCase().includes('.exp3.json')) {
          const file = resolved.id.slice('expr/'.length)
          return removeExpressionFile(file)
        }
        if (resolved.id.startsWith('expr/@name/')) {
          const name = decodeURIComponent(resolved.id.slice('expr/@name/'.length))
          return exprRemove(name)
        }
        return { ok: false, output: '不支持的 tag 映射结果' }
      }

      if (actionId.startsWith('expr/') && actionId.toLowerCase().includes('.exp3.json')) {
        const file = actionId.slice('expr/'.length)
        return removeExpressionFile(file)
      }
      if (actionId.startsWith('expr/@name/')) {
        const name = decodeURIComponent(actionId.slice('expr/@name/'.length))
        return exprRemove(name)
      }
      return { ok: false, output: '不支持的 expr remove 参数' }
    }

    if (sub === 'set' || sub === 'only') {
      const id = rest[0]
      if (!id) return { ok: false, output: '用法：expr set <name|index> | expr set <file.exp3.json>' }
      const actionId = await resolveExpressionCliArgToActionId(id)
      if (!actionId) return { ok: false, output: '无效表情参数' }
      const res = await playLive2DAction({ type: 'expression', id: actionId, mode: 'set' })
      return { ok: res.ok, output: res.output }
    }

    // Backward compatible: `expr <id>` means set-only.
    const id = args[1]
    if (id == null || String(id).trim() === '') {
      return { ok: false, output: '用法：expr <name|index> | expr add/remove/clear/active' }
    }

    // Allow `expr tag:开心`
    if (typeof id === 'string' && id.trim().toLowerCase().startsWith('tag:')) {
      const res = await playLive2DAction({ type: 'expression', id: id.trim(), mode: 'set' })
      return { ok: res.ok, output: res.output }
    }

    const actionId = await resolveExpressionCliArgToActionId(id)
    if (!actionId) return { ok: false, output: '无效表情参数' }
    const res = await playLive2DAction({ type: 'expression', id: actionId, mode: 'set' })
    // Keep Cubism2 fallback behavior when model.expression exists and action isn't a file.
    if (!res.ok && typeof currentModel.expression === 'function' && !actionId.toLowerCase().includes('.exp3.json')) {
      const raw = typeof id === 'string' ? id.trim() : ''
      const idNum = raw && /^\d+$/.test(raw) ? Number.parseInt(raw, 10) : undefined
      const ok = await currentModel.expression(idNum ?? raw)
      return { ok: Boolean(ok), output: ok ? 'expression set' : 'expression failed' }
    }
    return { ok: res.ok, output: res.output }
  }

  if (head === 'startup') {
    const sub = (args[1] ?? '').toLowerCase()
    if (!sub || sub === 'show') {
      const v = localStorage.getItem(STARTUP_EXPRESSIONS_STORAGE_KEY) ?? ''
      return { ok: true, output: v ? `startupExpr=${v}` : 'startupExpr=(none)' }
    }
    if (sub === 'clear') {
      localStorage.removeItem(STARTUP_EXPRESSIONS_STORAGE_KEY)

      // Also unpin in current session.
      for (const key of [...pinnedExpressionHandleKeys]) {
        fadeOutAndRemoveExpressionHandle(key)
      }
      pinnedExpressionHandleKeys.clear()

      return { ok: true, output: 'startupExpr cleared' }
    }
    if (sub === 'expr') {
      const raw = (args[2] ?? '').trim()
      if (!raw) return { ok: false, output: '用法：startup expr <a,b,c>' }

      // Normalize into action IDs for better portability.
      const tokens = raw
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0)

      const ids: string[] = []
      for (const t of tokens) {
        if (t.toLowerCase().startsWith('tag:')) {
          ids.push(t)
        } else if (isExpressionActionId(t)) {
          ids.push(t)
        } else if (looksLikeExpressionFile(t)) {
          ids.push(`expr/${t}`)
        } else {
          ids.push(makeExpressionNameActionId(t))
        }
      }

      const saved = ids.join(',')
      localStorage.setItem(STARTUP_EXPRESSIONS_STORAGE_KEY, saved)

      // Apply immediately in current session (so the pinned base takes effect right away).
      // Do NOT clear existing non-pinned expressions; just reconcile pinned set.
      const newPinned = new Set<string>()
      for (const t of ids) {
        const concreteId = await resolveStartupExpressionTokenToConcreteActionId(t)
        if (!concreteId) continue
        const key = expressionActionIdToHandleKey(concreteId)
        if (!key) continue
        newPinned.add(key)
        // Ensure it's active (add mode to avoid wiping user's current overlays).
        await playLive2DAction({ type: 'expression', id: concreteId, mode: 'add' })
      }

      // Remove expressions that were pinned but no longer pinned.
      for (const oldKey of [...pinnedExpressionHandleKeys]) {
        if (!newPinned.has(oldKey)) {
          fadeOutAndRemoveExpressionHandle(oldKey)
        }
      }

      pinnedExpressionHandleKeys.clear()
      for (const k of newPinned) pinnedExpressionHandleKeys.add(k)

      return { ok: true, output: `startupExpr saved (pinned): ${saved}` }
    }
    return { ok: false, output: '用法：startup expr <a,b,c> | startup clear | startup show' }
  }

  if (head === 'stop') {
    const r = stopAllLive2D()
    return { ok: r.ok, output: r.output }
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
  disposeMouseTracking = installLive2DFocusMouseTracking({
    ipcRenderer,
    getModel: () => currentModel,
    enabled: isMainLive2DMode.value,
  })

  // Hover fade + click-through behavior.
  // Use pointer events so we can read e.ctrlKey even when the window isn't focused.
  const rootEl = rootRef.value
  if (rootEl && !isCliMode.value && !isChatMode.value) {
    const onEnter = (e: PointerEvent) => {
      isHoveringWindow.value = true
      isCtrlHeld.value = Boolean(e.ctrlKey)
      syncPassthroughState()
    }
    const onMove = (e: PointerEvent) => {
      // If pointerenter is missed (rare), pointermove still means we are inside.
      if (!isHoveringWindow.value) {
        isHoveringWindow.value = true
        syncPassthroughState()
      }
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
    }

    rootEl.addEventListener('pointerenter', onEnter)
    rootEl.addEventListener('pointermove', onMove)
    rootEl.addEventListener('pointerleave', onLeave)

    onBeforeUnmount(() => {
      rootEl.removeEventListener('pointerenter', onEnter)
      rootEl.removeEventListener('pointermove', onMove)
      rootEl.removeEventListener('pointerleave', onLeave)
    })

    // Start polling immediately as a reliable fallback.
    startCursorPoll()
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
      ? await getCubism4Module()
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
  // Ensure any in-progress manual resize is stopped.
  try {
    ipcRenderer?.send?.('window:manualResizeEnd')
  } catch {
    // ignore
  }
  stopCursorPoll()
  disposeMouseTracking?.()
  disposeMouseTracking = null
  // Ensure window is interactive again when leaving.
  setWindowClickThrough(false)
  if (resizeHandler) window.removeEventListener('resize', resizeHandler)
  resizeHandler = null
  if (layoutRaf != null) cancelAnimationFrame(layoutRaf)
  layoutRaf = null
  currentModel = null
  currentModelSettingsUrl = null
  cachedMeta = null
  cachedExpressionTagMap = null
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

  ipcRenderer.on('live2d:apiRequest', async (_evt: any, msg: any) => {
    const id = msg?.id
    const payload = msg?.payload
    if (typeof id !== 'string' || !payload || typeof payload?.op !== 'string') return

    try {
      const op = payload.op
      if (op === 'status') {
        ipcRenderer.send('live2d:apiResponse', {
          id,
          ok: true,
          data: {
            loaded: Boolean(currentModel),
            modelUrl: currentModelSettingsUrl ?? modelUrl.value ?? null,
            type: isModel3.value ? 'model3' : 'model',
          },
        })
        return
      }
      if (op === 'list') {
        // Ensure metadata is warmed up but don't fail listing just because meta missing.
        void ensureMetaLoaded(false)
        const cat = buildLive2DActionCatalog()
        const only = payload?.type === 'expression' || payload?.type === 'motion' ? payload.type : null
        if (only === 'expression') {
          ipcRenderer.send('live2d:apiResponse', {
            id,
            ok: cat.ok,
            data: { ...cat, motions: [] },
            error: cat.error,
          })
        } else if (only === 'motion') {
          ipcRenderer.send('live2d:apiResponse', {
            id,
            ok: cat.ok,
            data: { ...cat, expressions: [] },
            error: cat.error,
          })
        } else {
          ipcRenderer.send('live2d:apiResponse', { id, ok: cat.ok, data: cat, error: cat.error })
        }
        return
      }
      if (op === 'stop') {
        const r = stopAllLive2D()
        ipcRenderer.send('live2d:apiResponse', { id, ok: r.ok, data: r })
        return
      }
      if (op === 'play') {
        const type = payload?.type
        const actionId = payload?.id
        const mode = payload?.mode
        if ((type !== 'expression' && type !== 'motion') || typeof actionId !== 'string') {
          ipcRenderer.send('live2d:apiResponse', { id, ok: false, error: 'missing type/id' })
          return
        }
        const res = await playLive2DAction({ type, id: actionId, mode })
        ipcRenderer.send('live2d:apiResponse', { id, ok: res.ok, data: res })
        return
      }

      ipcRenderer.send('live2d:apiResponse', { id, ok: false, error: `unknown op: ${op}` })
    } catch (e) {
      ipcRenderer.send('live2d:apiResponse', { id, ok: false, error: String(e) })
    }
  })
}
</script>

<template>
  <div ref="rootRef" class="root" :class="{ faded: shouldFade, interactive: isInteractive }">
    <template v-if="showCtrlResizeHint">
      <div class="corner-hint corner-hint-left" aria-hidden="true" />
      <div class="corner-hint corner-hint-right" aria-hidden="true" />
    </template>

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

        <!-- Drag only in the middle 75% area while interactive (Ctrl held). -->
        <div v-if="ipcRenderer && isInteractive && !isManualResizing" class="drag-zone" aria-hidden="true" />

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
  -webkit-app-region: drag;
  user-select: none;
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
  overflow-wrap: anywhere;
  word-break: break-word;
  max-width: 100%;
  max-height: 100%;
  overflow: hidden;
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
