import { computed, nextTick, ref, type Ref } from 'vue'
import type { ChatLine, AgentChatResponse, MessageRenderMode } from './useAgentMessages'

// ---- Desktop export patterns ----
const DESKTOP_EXPORT_TARGET_PATTERN = /(桌面|desktop)/i
const TEXT_WRITE_ACTION_PATTERN = /(创建|新建|写入|保存|导出|create|new|write|save|export)/i
const TEXT_FILE_PATTERN = /(\.txt|txt|文本文件|text file)/i

// ---- Typewriter constants ----
const TYPEWRITER_SPEED_MS = 20   // ms per character batch
const TYPEWRITER_CHARS_PER_TICK = 3  // characters per animation frame

// ---- Options interface ----

type StatusTickerLike = {
  push: (msg: string) => void
}

interface UseChatOperationsOptions {
  ipcRenderer: any
  lines: Ref<ChatLine[]>
  push: (role: ChatLine['role'], text: string, extra?: Omit<ChatLine, 'role' | 'text'>) => void
  clearScreen: () => void
  focusInputSoon: () => void
  buildContext: (maxChars?: number) => string
  normalizeAssistantContent: (text: string) => string
  statusTickerRef: Ref<StatusTickerLike | null>
}

export function useChatOperations(options: UseChatOperationsOptions) {
  const { ipcRenderer, lines, push, clearScreen, focusInputSoon, buildContext, normalizeAssistantContent, statusTickerRef } = options

  // ---- Session state ----
  const currentSessionId = ref<string>('')
  const isBackendRunning = ref(false)
  const heartbeatDot = ref(false)
  const isSending = ref(false)
  const input = ref('')
  const inputHistory = ref<string[]>([])
  const historyIndex = ref(-1)

  // ---- Refs for DOM elements ----
  const inputRef = ref<HTMLTextAreaElement | null>(null)
  const outputRef = ref<HTMLDivElement | null>(null)
  const statusTickerRef = options.statusTickerRef

  const canInvoke = computed(() => Boolean(ipcRenderer?.invoke))

  // ---- Desktop export confirmation ----
  const desktopConfirmVisible = ref(false)
  let desktopConfirmResolver: ((confirmed: boolean) => void) | null = null

  // ---- Typewriter state ----
  const typewriterTimer = ref<ReturnType<typeof setInterval> | null>(null)
  const typewriterFullText = ref('')
  const typewriterLineIndex = ref(-1)
  const typewriterLineRenderMode = ref<'rich_text' | 'plain_text'>('rich_text')

  // Track last assistant message content for dedup
  let _lastAssistantContent = ''

  // ---- Backend heartbeat ----
  function onBackendActivity() {
    isBackendRunning.value = true
    heartbeatDot.value = true
    setTimeout(() => { heartbeatDot.value = false }, 300)
    // Auto-reset after 10s of no activity
    clearTimeout((window as any).__backendIdleTimer)
    ;(window as any).__backendIdleTimer = setTimeout(() => {
      isBackendRunning.value = false
    }, 10000)
  }

  // ---- Typewriter functions ----

  function flushTypewriter(finishLine = true) {
    if (typewriterTimer.value !== null) {
      clearInterval(typewriterTimer.value)
      typewriterTimer.value = null
    }
    const idx = typewriterLineIndex.value
    if (finishLine && idx >= 0 && idx < lines.value.length && typewriterFullText.value) {
      lines.value[idx] = {
        ...lines.value[idx],
        text: typewriterFullText.value,
        renderMode: typewriterLineRenderMode.value,
      }
    }
    typewriterFullText.value = ''
    typewriterLineIndex.value = -1
  }

  function startTypewriter(text: string, renderMode: 'rich_text' | 'plain_text' = 'rich_text') {
    if (!text) return
    flushTypewriter(true)
    // Push placeholder line; render as plain_text during animation
    const line: ChatLine = { role: 'assistant', text: '', renderMode: 'plain_text', contentType: 'markdown' }
    lines.value.push(line)
    const lineIndex = lines.value.length - 1
    typewriterFullText.value = text
    typewriterLineIndex.value = lineIndex
    typewriterLineRenderMode.value = renderMode

    let pos = 0
    typewriterTimer.value = setInterval(() => {
      pos += TYPEWRITER_CHARS_PER_TICK
      if (pos >= text.length) {
        // Done: switch to rich_text
        if (lineIndex < lines.value.length) {
          lines.value[lineIndex] = { ...lines.value[lineIndex], text, renderMode }
        }
        flushTypewriter(false)
        void nextTick(() => {
          const el = outputRef.value
          if (el) el.scrollTop = el.scrollHeight
        })
      } else {
        if (lineIndex < lines.value.length) {
          lines.value[lineIndex] = { ...lines.value[lineIndex], text: text.slice(0, pos) }
        }
        void nextTick(() => {
          const el = outputRef.value
          if (el) el.scrollTop = el.scrollHeight
        })
      }
    }, TYPEWRITER_SPEED_MS)
  }

  // ---- Session management ----

  async function switchSession(sessionId: string) {
    currentSessionId.value = sessionId
    lines.value = []
    _lastAssistantContent = ''

    // Load historical messages from backend
    if (ipcRenderer?.invoke) {
      try {
        const res = await ipcRenderer.invoke('chat:loadSession', { sessionId }) as any
        if (res?.ok && Array.isArray(res.messages)) {
          for (const msg of res.messages) {
            if (msg.role === 'user') {
              push('user', `> ${msg.content}`)
            } else if (msg.role === 'assistant') {
              push('assistant', msg.content)
            }
          }
          push('system', `已切换到对话: ${sessionId.slice(0, 8)}... (${res.messages.length} 条消息)`)
          return
        }
      } catch { /* fallback */ }
    }
    push('system', `已切换到对话: ${sessionId.slice(0, 8)}...`)
  }

  function createNewSession() {
    currentSessionId.value = ''
    lines.value = []
    _lastAssistantContent = ''
    push('system', '已创建新对话。')
    if (ipcRenderer?.send) {
      ipcRenderer.send('chat:newSession')
    }
  }

  function updateWorkspace(path: string) {
    if (ipcRenderer?.send) {
      ipcRenderer.send('chat:setWorkspace', { path })
    }
  }

  // ---- Desktop export confirmation ----

  function needsDesktopExportConfirmation(prompt: string): boolean {
    return (
      DESKTOP_EXPORT_TARGET_PATTERN.test(prompt)
      && TEXT_WRITE_ACTION_PATTERN.test(prompt)
      && TEXT_FILE_PATTERN.test(prompt)
    )
  }

  async function confirmDesktopExportRequest(prompt: string): Promise<boolean> {
    if (!needsDesktopExportConfirmation(prompt)) return true
    if (desktopConfirmResolver) return false

    desktopConfirmVisible.value = true
    return await new Promise<boolean>((resolve) => {
      desktopConfirmResolver = (confirmed: boolean) => {
        desktopConfirmVisible.value = false
        desktopConfirmResolver = null
        focusInputSoon()
        resolve(confirmed)
      }
    })
  }

  function resolveDesktopExportConfirmation(confirmed: boolean) {
    desktopConfirmResolver?.(confirmed)
  }

  // ---- Send / Submit ----

  async function sendPrompt(prompt: string) {
    const trimmed = prompt.trim()
    if (!trimmed) return

    if (!ipcRenderer?.invoke) {
      push('err', '当前窗口没有可用的 ipcRenderer.invoke（请确认在 Electron 中运行）')
      return
    }

    if (!(await confirmDesktopExportRequest(trimmed))) {
      push('system', '已取消发送：桌面导出请求没有通过前端确认。')
      focusInputSoon()
      return
    }

    isSending.value = true
    push('user', `> ${trimmed}`)

    try {
      const context = buildContext()
      const res = (await ipcRenderer.invoke('agent:chat', { prompt: trimmed, context, sessionId: currentSessionId.value || undefined })) as AgentChatResponse
      if (res?.ok) {
        const outputText = res.output || '(ok)'
        const normalized = normalizeAssistantContent(outputText)
        // If IPC already delivered the same assistant message, avoid double push.
        if (normalized !== _lastAssistantContent) {
          _lastAssistantContent = normalized
          push('assistant', outputText, {
            contentType: res.content_type || 'markdown',
            renderMode: res.render_mode || 'rich_text',
          })
        }
      }
      else push('err', res?.output || '(error)')
    } catch (e) {
      push('err', String(e))
    } finally {
      isSending.value = false
      focusInputSoon()
    }
  }

  function submit() {
    const trimmed = input.value.trim()
    if (!trimmed) return
    // Immediately finish any in-progress typewriter for responsiveness
    flushTypewriter(true)
    inputHistory.value.push(trimmed)
    historyIndex.value = -1
    void sendPrompt(trimmed)
    input.value = ''
  }

  function applyHistory(delta: number) {
    const h = inputHistory.value
    if (!h.length) return

    if (historyIndex.value === -1) historyIndex.value = h.length
    historyIndex.value = Math.min(Math.max(historyIndex.value + delta, 0), h.length)

    if (historyIndex.value === h.length) {
      input.value = ''
    } else {
      input.value = h[historyIndex.value] ?? ''
    }
  }

  function onKeydown(e: KeyboardEvent) {
    // Ctrl+L: clear
    if (e.ctrlKey && (e.key === 'l' || e.key === 'L')) {
      e.preventDefault()
      clearScreen()
      return
    }

    // Up/Down: history (when cursor at start/end, approximate)
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      applyHistory(-1)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      applyHistory(+1)
      return
    }

    // Enter: send (Shift+Enter newline)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isSending.value) submit()
    }
  }

  // ---- Code copy utilities ----

  function hasCodeBlocks(text: string): boolean {
    return /```[\s\S]*?```/.test(text)
  }

  async function copyLastCodeBlock(text: string) {
    const match = text.match(/```(?:\w+\n)?([\s\S]*?)```/g)
    if (!match) return
    const last = match[match.length - 1]
    const code = last.replace(/```(?:\w+\n)?|```/g, '').trim()
    try {
      await navigator.clipboard.writeText(code)
    } catch {
      // fallback: ignore
    }
  }

  function autoResizeInput() {
    const el = inputRef.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  return {
    // State
    currentSessionId,
    isBackendRunning,
    heartbeatDot,
    isSending,
    input,
    inputHistory,
    historyIndex,
    canInvoke,
    desktopConfirmVisible,

    // Refs
    inputRef,
    outputRef,

    // Session
    switchSession,
    createNewSession,
    updateWorkspace,

    // Typewriter
    flushTypewriter,
    startTypewriter,

    // Backend
    onBackendActivity,

    // Desktop export
    needsDesktopExportConfirmation,
    confirmDesktopExportRequest,
    resolveDesktopExportConfirmation,

    // Send / submit
    sendPrompt,
    submit,
    applyHistory,
    onKeydown,

    // Code utilities
    hasCodeBlocks,
    copyLastCodeBlock,
    autoResizeInput,
  }
}
