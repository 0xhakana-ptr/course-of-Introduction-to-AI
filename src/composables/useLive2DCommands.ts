// This composable wraps executeLive2DCommand from App.vue.
// It depends on model management functions that will be provided by useLive2DModel.

export function useLive2DCommands(modelFns: {
  /** Returns the current Live2D model instance (or null). */
  getCurrentModel: () => any
  /** Returns the current model settings URL (or null). */
  getCurrentModelSettingsUrl: () => string | null
  /** Returns whether the model is a Cubism4/model3 model. */
  getIsModel3: () => boolean
  /** Returns the cached model metadata (or null). */
  getCachedMeta: () => any
  /** Returns the last metadata loading error (or null). */
  getLastMetaError: () => string | null
  /** Load (or reload) model metadata. */
  ensureMetaLoaded: (force?: boolean) => Promise<any>
  /** Build the catalog of available Live2D actions (expressions + motions). */
  buildLive2DActionCatalog: () => any
  /** Play a Live2D action (expression or motion). */
  playLive2DAction: (payload: {
    type: 'expression' | 'motion'
    id: string
    mode?: 'set' | 'add'
  }) => Promise<{ ok: boolean; output: string }>
  /** Stop all Live2D motions and expressions. */
  stopAllLive2D: () => { ok: boolean; output: string }
  /** Resolve a motion CLI argument to a concrete action ID. */
  resolveMotionCliArgToActionId: (groupOrFile: unknown, indexArg?: unknown) => string | null
  /** Resolve an expression CLI argument to a concrete action ID. */
  resolveExpressionCliArgToActionId: (idOrIndex: unknown) => Promise<string | null>
  /** Load an expression file and add it to the active set. */
  playExpressionFromFile: (file: string, mode?: 'set' | 'add') => Promise<{ ok: boolean; output: string }>
  /** Remove an expression file from the active set. */
  removeExpressionFile: (file: string) => { ok: boolean; output: string }
  /** Add an expression by name/index to the active set. */
  exprAdd: (idOrIndex: unknown) => Promise<{ ok: boolean; output: string }>
  /** Clear all active expressions. */
  exprClear: () => { ok: boolean; output: string }
  /** Clear non-pinned expressions only. */
  exprClearNonPinned: () => { ok: boolean; output: string }
  /** Remove an expression by name/index from the active set. */
  exprRemove: (idOrIndex: unknown) => { ok: boolean; output: string }
  /** Get a human-readable list of currently active expressions. */
  getActiveExpressionsText: () => string
  /** Resolve a tag string to a concrete expression action ID. */
  resolveExpressionTagToActionId: (tag: string) => Promise<{ ok: boolean; id?: string; reason?: string }>
  /** Resolve a startup expression token to a concrete action ID. */
  resolveStartupExpressionTokenToConcreteActionId: (token: string) => Promise<string | null>
  /** Convert an expression action ID to a handle key (for pinning). */
  expressionActionIdToHandleKey: (id: string) => string | null
  /** Check whether a string looks like an expression action ID. */
  isExpressionActionId: (s: string) => boolean
  /** Check whether a string looks like an expression file path. */
  looksLikeExpressionFile: (s: string) => boolean
  /** Create an expression-by-name action ID. */
  makeExpressionNameActionId: (name: string) => string
  /** Fade out and remove a pinned expression handle by key. */
  fadeOutAndRemoveExpressionHandle: (key: string) => void
  /** Get the set of currently pinned expression handle keys (mutable reference). */
  getPinnedExpressionHandleKeys: () => Set<string>
}) {
  // Copy of STARTUP_EXPRESSIONS_STORAGE_KEY from App.vue
  const STARTUP_EXPRESSIONS_STORAGE_KEY = 'live2d.startupExpressions'

  // Copy tokenizeCommand from App.vue line 819
  function tokenizeCommand(input: string): string[] {
    const tokens: string[] = []
    const re = /"([^"]*)"|'([^']*)'|(\S+)/g
    let match: RegExpExecArray | null
    while ((match = re.exec(input))) {
      tokens.push(match[1] ?? match[2] ?? match[3])
    }
    return tokens
  }

  // Copy executeLive2DCommand from App.vue line 1039 (verbatim, with modelFns indirection)
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
          `- stop                   （停止所有动作）\n` +
          `- focus <x> <y> [instant]（x/y: -1..1）\n` +
          `- tap <x> <y>            （x/y: 屏幕坐标，像素）\n`,
      }
    }

    if (head === 'status') {
      const loaded = Boolean(modelFns.getCurrentModel())
      return {
        ok: true,
        output:
          `loaded=${loaded}\n` +
          `modelUrl=${modelFns.getCurrentModelSettingsUrl() ?? '(none)'}\n` +
          `type=${modelFns.getIsModel3() ? 'model3' : 'model'}\n`,
      }
    }

    if (head === 'meta') {
      const force = (args[1] ?? '').toLowerCase() === 'reload'
      const meta = await modelFns.ensureMetaLoaded(force)
      if (!meta) {
        return {
          ok: false,
          output:
            '未加载模型元数据。' +
            (modelFns.getLastMetaError() ? `\n原因：${modelFns.getLastMetaError()}` : '') +
            `\nmodelUrl=${modelFns.getCurrentModelSettingsUrl() ?? '(none)'}`,
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
      void modelFns.ensureMetaLoaded(false)

      if (target === 'motions') {
        const cat = modelFns.buildLive2DActionCatalog()
        if (!cat.ok) return { ok: false, output: cat.error ?? 'list failed' }
        if (!cat.motions.length) return { ok: true, output: '(none)' }
        return {
          ok: true,
          output: cat.motions.map((a) => `${a.id}  # ${a.label}`).join('\n'),
        }
      }
      if (target === 'expressions') {
        const cat = modelFns.buildLive2DActionCatalog()
        if (!cat.ok) return { ok: false, output: cat.error ?? 'list failed' }
        if (!cat.expressions.length) return { ok: true, output: '(none)' }
        return {
          ok: true,
          output: cat.expressions.map((a) => `${a.id}  # ${a.label}`).join('\n'),
        }
      }

      return { ok: false, output: '用法：list motions | list expressions' }
    }


    if (!modelFns.getCurrentModel()) return { ok: false, output: '模型尚未加载完成（currentModel is null）' }

    if (head === 'motion') {
      const id = modelFns.resolveMotionCliArgToActionId(args[1], args[2])
      if (!id) return { ok: false, output: '用法：motion <group> [index] | motion <file.motion3.json>' }
      const res = await modelFns.playLive2DAction({ type: 'motion', id })
      return { ok: res.ok, output: res.output }
    }

    if (head === 'expr' || head === 'expression') {
      const sub = (args[1] ?? '').toLowerCase()
      const rest = args.slice(2)

      // Cubism4 stacking commands
      if (sub === 'active') return { ok: true, output: `active: ${modelFns.getActiveExpressionsText()}` }
      if (sub === 'clear' || sub === 'reset') return modelFns.exprClear()

      if (sub === 'add') {
        const id = rest[0]
        if (!id) return { ok: false, output: '用法：expr add <name|index> | expr add <file.exp3.json>' }
        const actionId = await modelFns.resolveExpressionCliArgToActionId(id)
        if (!actionId) return { ok: false, output: '无效表情参数' }
        const res = await modelFns.playLive2DAction({ type: 'expression', id: actionId, mode: 'add' })
        return { ok: res.ok, output: res.output }
      }

      if (sub === 'remove' || sub === 'rm' || sub === 'del') {
        const id = rest[0]
        if (!id) return { ok: false, output: '用法：expr remove <name|index> | expr remove <file.exp3.json>' }
        const actionId = await modelFns.resolveExpressionCliArgToActionId(id)
        if (!actionId) return { ok: false, output: '无效表情参数' }

        if (actionId.toLowerCase().startsWith('tag:')) {
          const tag = actionId.slice('tag:'.length)
          const resolved = await modelFns.resolveExpressionTagToActionId(tag)
          if (!resolved.ok || !resolved.id) return { ok: false, output: `tag 映射失败：${tag}` }
          // Remove the resolved concrete action
          if (resolved.id.startsWith('expr/') && resolved.id.toLowerCase().includes('.exp3.json')) {
            const file = resolved.id.slice('expr/'.length)
            return modelFns.removeExpressionFile(file)
          }
          if (resolved.id.startsWith('expr/@name/')) {
            const name = decodeURIComponent(resolved.id.slice('expr/@name/'.length))
            return modelFns.exprRemove(name)
          }
          return { ok: false, output: '不支持的 tag 映射结果' }
        }

        if (actionId.startsWith('expr/') && actionId.toLowerCase().includes('.exp3.json')) {
          const file = actionId.slice('expr/'.length)
          return modelFns.removeExpressionFile(file)
        }
        if (actionId.startsWith('expr/@name/')) {
          const name = decodeURIComponent(actionId.slice('expr/@name/'.length))
          return modelFns.exprRemove(name)
        }
        return { ok: false, output: '不支持的 expr remove 参数' }
      }

      if (sub === 'set' || sub === 'only') {
        const id = rest[0]
        if (!id) return { ok: false, output: '用法：expr set <name|index> | expr set <file.exp3.json>' }
        const actionId = await modelFns.resolveExpressionCliArgToActionId(id)
        if (!actionId) return { ok: false, output: '无效表情参数' }
        const res = await modelFns.playLive2DAction({ type: 'expression', id: actionId, mode: 'set' })
        return { ok: res.ok, output: res.output }
      }

      // Backward compatible: `expr <id>` means set-only.
      const id = args[1]
      if (id == null || String(id).trim() === '') {
        return { ok: false, output: '用法：expr <name|index> | expr add/remove/clear/active' }
      }

      // Allow `expr tag:开心`
      if (typeof id === 'string' && id.trim().toLowerCase().startsWith('tag:')) {
        const res = await modelFns.playLive2DAction({ type: 'expression', id: id.trim(), mode: 'set' })
        return { ok: res.ok, output: res.output }
      }

      const actionId = await modelFns.resolveExpressionCliArgToActionId(id)
      if (!actionId) return { ok: false, output: '无效表情参数' }
      const res = await modelFns.playLive2DAction({ type: 'expression', id: actionId, mode: 'set' })
      // Keep Cubism2 fallback behavior when model.expression exists and action isn't a file.
      if (!res.ok && typeof modelFns.getCurrentModel()?.expression === 'function' && !actionId.toLowerCase().includes('.exp3.json')) {
        const raw = typeof id === 'string' ? id.trim() : ''
        const idNum = raw && /^\d+$/.test(raw) ? Number.parseInt(raw, 10) : undefined
        const ok = await modelFns.getCurrentModel().expression(idNum ?? raw)
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
        for (const key of [...modelFns.getPinnedExpressionHandleKeys()]) {
          modelFns.fadeOutAndRemoveExpressionHandle(key)
        }
        modelFns.getPinnedExpressionHandleKeys().clear()

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
          } else if (modelFns.isExpressionActionId(t)) {
            ids.push(t)
          } else if (modelFns.looksLikeExpressionFile(t)) {
            ids.push(`expr/${t}`)
          } else {
            ids.push(modelFns.makeExpressionNameActionId(t))
          }
        }

        const saved = ids.join(',')
        localStorage.setItem(STARTUP_EXPRESSIONS_STORAGE_KEY, saved)

        // Apply immediately in current session (so the pinned base takes effect right away).
        // Do NOT clear existing non-pinned expressions; just reconcile pinned set.
        const newPinned = new Set<string>()
        for (const t of ids) {
          const concreteId = await modelFns.resolveStartupExpressionTokenToConcreteActionId(t)
          if (!concreteId) continue
          const key = modelFns.expressionActionIdToHandleKey(concreteId)
          if (!key) continue
          newPinned.add(key)
          // Ensure it's active (add mode to avoid wiping user's current overlays).
          await modelFns.playLive2DAction({ type: 'expression', id: concreteId, mode: 'add' })
        }

        // Remove expressions that were pinned but no longer pinned.
        for (const oldKey of [...modelFns.getPinnedExpressionHandleKeys()]) {
          if (!newPinned.has(oldKey)) {
            modelFns.fadeOutAndRemoveExpressionHandle(oldKey)
          }
        }

        modelFns.getPinnedExpressionHandleKeys().clear()
        for (const k of newPinned) modelFns.getPinnedExpressionHandleKeys().add(k)

        return { ok: true, output: `startupExpr saved (pinned): ${saved}` }
      }
      return { ok: false, output: '用法：startup expr <a,b,c> | startup clear | startup show' }
    }

    if (head === 'stop') {
      const r = modelFns.stopAllLive2D()
      return { ok: r.ok, output: r.output }
    }

    if (head === 'focus') {
      const x = Number.parseFloat(args[1] ?? '')
      const y = Number.parseFloat(args[2] ?? '')
      const instant = (args[3] ?? '').toLowerCase() === 'instant'
      if (!Number.isFinite(x) || !Number.isFinite(y)) return { ok: false, output: '用法：focus <x> <y> [instant]' }
      modelFns.getCurrentModel().focus(x, y, instant)
      return { ok: true, output: 'ok' }
    }

    if (head === 'tap') {
      const x = Number.parseFloat(args[1] ?? '')
      const y = Number.parseFloat(args[2] ?? '')
      if (!Number.isFinite(x) || !Number.isFinite(y)) return { ok: false, output: '用法：tap <x> <y>' }
      modelFns.getCurrentModel().tap(x, y)
      return { ok: true, output: 'ok' }
    }

    return { ok: false, output: `未知命令：${head}（输入 help 查看）` }
  }

  return { executeLive2DCommand }
}
