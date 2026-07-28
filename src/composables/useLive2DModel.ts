import { ref, type Ref } from 'vue'
import * as PIXI from 'pixi.js'
import { getIpcRenderer } from '../platform/electronIpc'

// Constants (duplicated from App.vue for composable independence)
const CUBISM2_RUNTIME_PATH = 'live2d/live2d.min.js'
const CUBISM4_CORE_PATH = 'live2d/live2dcubismcore.min.js'
const CUBISM4_WASM_PATH = 'live2d/_em_module.wasm'
const CUBISM4_WASM_FALLBACK_PATH = 'live2d/live2dcubismcore.wasm'
const STARTUP_EXPRESSIONS_STORAGE_KEY = 'live2d.startupExpressions'

// ─── Exported types ────────────────────────────────────────────────────────────

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

// ─── Composable ────────────────────────────────────────────────────────────────

export function useLive2DModel(options: {
  defaultModelPath: string
  modelUrl: Ref<string>
  isModel3: Ref<boolean>
  isCliMode: Ref<boolean>
}) {
  const loadState = ref<'loading' | 'ready' | 'error'>('loading')
  const errorText = ref('')

  // ─── Module-level state ────────────────────────────────────────────────────

  let pixiApp: PIXI.Application | null = null

  let currentModel: any = null
  let currentModelSettingsUrl: string | null = null

  let cachedExpressionTagMap:
    | { sourceUrl: string; map: Record<string, string | string[] | null> }
    | null = null
  let expressionTagMapPromise: Promise<{ sourceUrl: string; map: Record<string, string | string[] | null> } | null> | null = null

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

  // ─── Functions ─────────────────────────────────────────────────────────────

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
    const base = currentModelSettingsUrl ?? options.modelUrl.value
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
      const base = currentModelSettingsUrl ?? options.modelUrl.value
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
    if (!currentModel || options.isCliMode.value) return
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

  async function fetchModel3Meta(settingsUrl: string) {
    const ipcRenderer = getIpcRenderer()
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
    const settingsUrl = currentModelSettingsUrl ?? options.modelUrl.value
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
      modelUrl: currentModelSettingsUrl ?? options.modelUrl.value,
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
    if (options.isModel3.value) {
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

  // ─── State setters (needed by App.vue after model loading / cleanup) ──────

  function setCurrentModel(m: any) {
    currentModel = m
  }

  function setCurrentModelSettingsUrl(url: string | null) {
    currentModelSettingsUrl = url
  }

  function resetCachedMeta() {
    cachedMeta = null
  }

  function setPixiApp(app: PIXI.Application | null) {
    pixiApp = app
  }

  // ─── Return ────────────────────────────────────────────────────────────────

  return {
    // Reactive state
    loadState,
    errorText,

    // Direct access (needed by template and IPC handlers)
    currentModel: () => currentModel,
    currentModelSettingsUrl: () => currentModelSettingsUrl,
    pixiApp: () => pixiApp,
    activeExpressionHandles,
    pinnedExpressionHandleKeys,
    getLastMetaError: () => lastMetaError,

    // State setters
    setCurrentModel,
    setCurrentModelSettingsUrl,
    resetCachedMeta,
    setPixiApp,

    // Model lifecycle
    ensureRuntimeLoaded,
    ensureMetaLoaded,
    applyStartupExpressions,

    // Expression/motion playback
    playLive2DAction,
    stopAllLive2D,
    buildLive2DActionCatalog,

    // Expression management (needed by commands)
    resolveExpressionTagToActionId,
    exprAdd,
    exprClear,
    exprRemove,
    getActiveExpressionsText,
    exprClearNonPinned,
    playExpressionFromFile,
    removeExpressionFile,
    playMotionFromFile,
    getStartupExpressionsFromConfig,
    resolveStartupExpressionTokenToConcreteActionId,
    expressionActionIdToHandleKey,
    fadeOutAndRemoveExpressionHandle,
    getPinnedExpressionHandleKeys: () => pinnedExpressionHandleKeys,

    // Metadata & utilities
    cachedMeta: () => cachedMeta,
    fetchModel3Meta,
    fetchJsonObject,
    fetchJsoncObject,
    resolveModelRelativeUrl,
    isExpressionActionId,
    isMotionActionId,
    makeExpressionNameActionId,
    actionIdLabel,
    looksLikeExpressionFile,
    looksLikeMotionFile,
    resolveExpressionCliArgToActionId,
    resolveMotionCliArgToActionId,

    // Cubism module access
    getCubism4Module,
  }
}
