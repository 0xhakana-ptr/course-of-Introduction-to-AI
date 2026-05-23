<script setup lang="ts">
const theme = ref<'light' | 'dark'>('light')

function toggleTheme() {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
  document.documentElement.setAttribute('data-theme', theme.value)
  localStorage.setItem('cyber-waifu-theme', theme.value)
}

function copyMessage(text: string) {
  const raw = String(text || '')
  if (!raw) return
  navigator.clipboard.writeText(raw).catch(() => {
    const ta = document.createElement('textarea')
    ta.value = raw
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  })
}


// Init theme
const savedTheme = localStorage.getItem('cyber-waifu-theme')
if (savedTheme === 'dark' || savedTheme === 'light') {
  theme.value = savedTheme
}
document.documentElement.setAttribute('data-theme', theme.value)

import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import c from 'highlight.js/lib/languages/c'
import cpp from 'highlight.js/lib/languages/cpp'
import css from 'highlight.js/lib/languages/css'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import python from 'highlight.js/lib/languages/python'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import 'highlight.js/styles/github-dark.css'
import MarkdownIt from 'markdown-it'
import markdownItKatex from 'markdown-it-katex'
import 'katex/dist/katex.min.css'
import { getIpcRenderer } from '../platform/electronIpc'
import BackendIndicator from './BackendIndicator.vue'
import PixelPet from './PixelPet.vue'
import ChatHistoryPanel from './ChatHistoryPanel.vue'
import WorkspaceSelector from './WorkspaceSelector.vue'

type FileActionCard = {
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
type MessageContentType = 'plain_text' | 'markdown'
type MessageRenderMode = 'plain_text' | 'rich_text'
type ChatLine = {
  role: 'user' | 'assistant' | 'system' | 'err'
  text: string
  contentType?: MessageContentType
  renderMode?: MessageRenderMode
  fileAction?: FileActionCard
}
type AgentChatResponse = {
  ok: boolean
  output: string
  content_type?: MessageContentType
  render_mode?: MessageRenderMode
}

// AI Agent 消息类型定义
type ChatMessage = {
  type: 'chat'
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  metadata?: {
    is_partial: boolean
    sequence_id?: number
    total_parts?: number
    node_name?: string
    content_type?: MessageContentType
    render_mode?: MessageRenderMode
  }
  content_type?: MessageContentType
  render_mode?: MessageRenderMode
}

type ExpressionMessage = {
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

type ErrorMessage = {
  type: 'error'
  code: string
  message: string
  details?: any
  timestamp: string
  node_name?: string
}

type StatusUpdate = {
  type: 'status'
  status: 'idle' | 'running' | 'paused' | 'done' | 'error' | 'cancelled'
  progress?: number
  message?: string
  node_name?: string
  timestamp: string
  event_type?: string
  event_source?: string
  event_stage?: string
  bridge_payload?: {
    message?: string
    action_target?: string
    action_name?: string
    action_label?: string
    action_status?: 'started' | 'completed' | 'failed'
    metadata?: Record<string, unknown>
  }
  metadata?: {
    node_label?: string
    phase?: string
    runtime_event?: string
    quip?: string
    action_target?: string
    action_name?: string
    action_label?: string
    action_status?: 'started' | 'completed' | 'failed'
    action_rel_path?: string
    action_source_path?: string
    action_target_path?: string
    action_query?: string
    result_path?: string
    result_source_path?: string
    result_target_path?: string
    result_match_count?: number
    tool_name?: string
    tool_output_kind?: string
    tool_error_code?: string
    error?: string
    ok?: boolean
    action_category?: string
    safety_level?: string
    requires_confirmation?: boolean
  }
}

type QuipMessage = {
  type: 'quip'
  content: string
  node_name?: string
  timestamp: string
  event_type?: string
  event_source?: string
  event_stage?: string
  metadata?: {
    priority?: 'low' | 'medium' | 'high'
    duration?: number
    node_label?: string
    phase?: string
    runtime_event?: string
  }
}

const ipcRenderer = getIpcRenderer()

const lines = ref<ChatLine[]>([])
const input = ref('')
const inputHistory = ref<string[]>([])
const historyIndex = ref(-1)
const isSending = ref(false)
const currentStatus = ref('idle')
const currentProgress = ref(0)
const currentNode = ref('')
const currentNodeLabel = ref('')
const STATUS_LOG_THROTTLE_MS = 850
const QUIP_LOG_THROTTLE_MS = 850
let lastStatusLogAt = 0
let lastStatusLogKey = ''
let lastQuipLogAt = 0
let lastQuipLogKey = ''

hljs.registerLanguage('bash', bash)
hljs.registerLanguage('c', c)
hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('css', css)
hljs.registerLanguage('java', java)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('python', python)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('xml', xml)

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function highlightCodeBlock(code: string, language: string): string {
  const normalizedLanguage = String(language || '').trim().toLowerCase()
  const languageAliases: Record<string, string> = {
    cplusplus: 'cpp',
    js: 'javascript',
    py: 'python',
    shell: 'bash',
    sh: 'bash',
    ts: 'typescript',
  }
  const resolvedLanguage = languageAliases[normalizedLanguage] || normalizedLanguage
  if (resolvedLanguage && hljs.getLanguage(resolvedLanguage)) {
    const highlighted = hljs.highlight(code, {
      language: resolvedLanguage,
      ignoreIllegals: true,
    }).value
    return `<pre class="hljs code-block"><code>${highlighted}</code></pre>`
  }
  return `<pre class="hljs code-block"><code>${escapeHtml(code)}</code></pre>`
}

const markdownRenderer = new MarkdownIt({
  breaks: true,
  highlight: highlightCodeBlock,
  html: false,
  linkify: true,
  typographer: true,
}).use(markdownItKatex)

const FENCE_LINE_PATTERN = /^\s*(```|~~~)/
const LATEX_WORD_COMMANDS = [
  'frac',
  'dfrac',
  'tfrac',
  'sqrt',
  'int',
  'sum',
  'prod',
  'lim',
  'ln',
  'log',
  'sin',
  'cos',
  'tan',
  'cot',
  'sec',
  'csc',
  'neq',
  'leq',
  'geq',
  'approx',
  'cdot',
  'times',
  'pm',
  'mp',
  'infty',
  'alpha',
  'beta',
  'gamma',
  'delta',
  'theta',
  'lambda',
  'mu',
  'pi',
  'sigma',
  'omega',
  'partial',
  'nabla',
  'left',
  'right',
  'text',
  'mathrm',
  'mathbf',
  'mathbb',
].join('|')
const LATEX_COMMAND_PATTERN = new RegExp(String.raw`\\{1,2}(?:${LATEX_WORD_COMMANDS}\b|[,;!])`)
const LATEX_DOUBLE_BACKSLASH_PATTERN = new RegExp(
  String.raw`\\\\(?=(?:${LATEX_WORD_COMMANDS})\b|[,;!])`,
  'g',
)
const INLINE_LATEX_PATTERN = new RegExp(
  String.raw`(^|[\s([{，。；：、])((?:[A-Za-z0-9{}|+\-*/=^_.,:;!]*\s*)*\\{1,2}(?:${LATEX_WORD_COMMANDS}\b|[,;!])(?:\s*[A-Za-z0-9{}|+\-*/=^_.,:;!\\]*)*)`,
  'g',
)

function normalizeLatexBackslashes(text: string): string {
  return text.replace(LATEX_DOUBLE_BACKSLASH_PATTERN, '\\')
}

function looksLikeStandaloneLatex(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed || trimmed.startsWith('$') || trimmed.endsWith('$')) return false
  if (/[\u4e00-\u9fff]/.test(trimmed)) return false
  if (!LATEX_COMMAND_PATTERN.test(trimmed)) return false
  if (!trimmed.startsWith('\\') && !trimmed.includes('=')) return false
  return /(?:=|[+\-*/^]|\\{1,2}(?:int|sum|prod|frac|dfrac|tfrac|sqrt|lim|ln|log|sin|cos|tan|neq|leq|geq|approx|cdot|times))/.test(trimmed)
}

function wrapInlineLatex(text: string): string {
  const normalized = normalizeLatexBackslashes(text)
  const mathSegments = normalized.split(/(\$\$[\s\S]*?\$\$|\$[^$\n]+\$)/g)
  return mathSegments
    .map((segment) => {
      if (segment.startsWith('$')) return segment
      return segment.replace(INLINE_LATEX_PATTERN, (_match, prefix: string, expression: string) => {
        const formula = normalizeLatexBackslashes(expression).trim()
        if (!formula || formula.includes('$')) return `${prefix}${expression}`
        return `${prefix}$${formula}$`
      })
    })
    .join('')
}

function normalizeMathMarkdownLine(line: string): string {
  const delimiterNormalized = line
    .replace(/\\\[(.+?)\\\]/g, (_match, expression: string) => `$$\n${normalizeLatexBackslashes(expression).trim()}\n$$`)
    .replace(/\\\((.+?)\\\)/g, (_match, expression: string) => `$${normalizeLatexBackslashes(expression).trim()}$`)

  const indent = delimiterNormalized.match(/^\s*/)?.[0] || ''
  const trimmed = delimiterNormalized.trim()
  if (looksLikeStandaloneLatex(trimmed)) {
    return `${indent}$$\n${normalizeLatexBackslashes(trimmed)}\n${indent}$$`
  }
  return wrapInlineLatex(delimiterNormalized)
}

function normalizeRichTextMarkdown(text: string): string {
  const lines = String(text || '').replace(/\r\n/g, '\n').split('\n')
  let inFence = false
  return lines
    .map((line) => {
      if (FENCE_LINE_PATTERN.test(line)) {
        inFence = !inFence
        return line
      }
      if (inFence) return line
      return normalizeMathMarkdownLine(line)
    })
    .join('\n')
}

// 存储部分消息
const partialMessages = new Map<number, string>()
const DESKTOP_EXPORT_TARGET_PATTERN = /(桌面|desktop)/i
const TEXT_WRITE_ACTION_PATTERN = /(创建|新建|写入|保存|导出|create|new|write|save|export)/i
const TEXT_FILE_PATTERN = /(\.txt|txt|文本文件|text file)/i

// 新功能：工作区、聊天历史、后端状态
const currentSessionId = ref<string>('')
const isBackendRunning = ref(false)
const heartbeatDot = ref(false)

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

// Backend heartbeat: listen for any backend event
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

const outputRef = ref<HTMLDivElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const canInvoke = computed(() => Boolean(ipcRenderer?.invoke))
const desktopConfirmVisible = ref(false)
let desktopConfirmResolver: ((confirmed: boolean) => void) | null = null

function push(role: ChatLine['role'], text: string, extra: Omit<ChatLine, 'role' | 'text'> = {}) {
  // Assistant messages: typewriter animation
  if (role === 'assistant' && text) {
    const mode = (extra.renderMode || 'rich_text') as 'rich_text' | 'plain_text'
    startTypewriter(text, mode)
    return
  }
  // Non-assistant (user/system/err): flush any running typewriter first
  if (role !== 'assistant') {
    flushTypewriter(true)
  }
  lines.value.push({ role, text, ...extra })
  // Keep last ~500 lines
  if (lines.value.length > 500) lines.value.splice(0, lines.value.length - 500)
  void nextTick(() => {
    const el = outputRef.value
    if (!el) return
    el.scrollTop = el.scrollHeight
  })
}

function clearScreen() {
  flushTypewriter(true)
  lines.value = []
  push('system', '屏幕已清空（Ctrl+L）。')
  focusInputSoon()
}

function renderAssistantText(text: string): string {
  return markdownRenderer.render(normalizeRichTextMarkdown(text))
}

function shouldRenderRichMessage(line: ChatLine): boolean {
  return line.role === 'assistant' && (line.renderMode || 'rich_text') === 'rich_text'
}

function focusInputSoon() {
  void nextTick(() => {
    window.setTimeout(() => {
      ipcRenderer?.send?.('chat:focus-window')
      inputRef.value?.focus()
    }, 0)
  })
}

function normalizeAssistantContent(text: string): string {
  return String(text ?? '').replace(/\r\n/g, '\n')
}

// Track last assistant message content for dedup (prevents double-reply from IPC + invoke)
let _lastAssistantContent = ''

// ---- Typewriter animation state ----
const TYPEWRITER_SPEED_MS = 20   // ms per character batch
const TYPEWRITER_CHARS_PER_TICK = 3  // characters per animation frame
const typewriterTimer = ref<ReturnType<typeof setInterval> | null>(null)
const typewriterFullText = ref('')
const typewriterLineIndex = ref(-1)
const typewriterLineRenderMode = ref<'rich_text' | 'plain_text'>('rich_text')

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


// 处理 Chat 消息
function handleChat(_event: any, data: ChatMessage) {
  onBackendActivity()
  const { content, metadata } = data

  const normalizedIncoming = normalizeAssistantContent(content)

  // Dedup: skip if identical to what we already pushed from HTTP response
  if (normalizedIncoming && normalizedIncoming === _lastAssistantContent) return
  
  if (metadata?.is_partial && typeof metadata.sequence_id === 'number' && typeof metadata.total_parts === 'number') {
    // 处理流式输出
    const { sequence_id, total_parts } = metadata
    partialMessages.set(sequence_id, content)
    
    // 检查是否所有部分都已接收
    if (partialMessages.size === total_parts) {
      // 按顺序组合所有部分
      let fullContent = ''
      for (let i = 0; i < total_parts; i++) {
        fullContent += partialMessages.get(i) || ''
      }
      _lastAssistantContent = normalizeAssistantContent(fullContent)
      push('assistant', fullContent, {
        contentType: data.content_type || metadata.content_type || 'markdown',
        renderMode: data.render_mode || metadata.render_mode || 'rich_text',
      })
      partialMessages.clear()
    }
  } else {
    // 完整消息，直接显示
    _lastAssistantContent = normalizedIncoming
    push('assistant', content, {
      contentType: data.content_type || metadata?.content_type || 'markdown',
      renderMode: data.render_mode || metadata?.render_mode || 'rich_text',
    })
  }
}

// 处理错误消息
function handleError(_event: any, data: ErrorMessage) {
  onBackendActivity()
  push('err', `[${data.code}] ${data.message}`)
  if (data.details) {
    push('err', JSON.stringify(data.details, null, 2))
  }
}

function shouldLogTransientEvent(
  key: string,
  options: {
    throttleMs: number
    lastKey: string
    lastAt: number
    force?: boolean
  },
): { shouldLog: boolean; nextAt: number; nextKey: string } {
  const { throttleMs, lastKey, lastAt, force = false } = options
  if (force) {
    return { shouldLog: true, nextAt: Date.now(), nextKey: key }
  }

  const now = Date.now()
  if (key === lastKey && now - lastAt < throttleMs * 2) {
    return { shouldLog: false, nextAt: lastAt, nextKey: lastKey }
  }
  if (now - lastAt < throttleMs) {
    return { shouldLog: false, nextAt: lastAt, nextKey: lastKey }
  }
  return { shouldLog: true, nextAt: now, nextKey: key }
}

function getDisplayNodeName(data: Pick<StatusUpdate | QuipMessage, 'node_name' | 'metadata'>): string {
  return data.metadata?.node_label || data.node_name || '未知'
}

function getActionStatusText(data: StatusUpdate): string | null {
  if (!data.event_type?.startsWith('workflow.action_')) return null
  const quip = data.message || data.metadata?.quip || data.bridge_payload?.message
  if (quip) return `[动作] ${quip}`
  const label = data.metadata?.action_label || data.metadata?.action_name || getDisplayNodeName(data)
  const actionStatus = data.metadata?.action_status
  if (actionStatus === 'started' || data.event_type === 'workflow.action_started') {
    return `[动作] 开始执行：${label}`
  }
  if (actionStatus === 'completed' || data.event_type === 'workflow.action_completed') {
    return `[动作] 执行完成：${label}`
  }
  if (actionStatus === 'failed' || data.event_type === 'workflow.action_failed') {
    return `[动作] 执行失败：${label}`
  }
  return `[动作] ${label}`
}

function stringField(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function numberField(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function getStatusMetadata(data: StatusUpdate): Record<string, unknown> {
  const bridgeMetadata = data.bridge_payload?.metadata
  return {
    ...(bridgeMetadata && typeof bridgeMetadata === 'object' ? bridgeMetadata : {}),
    ...(data.metadata || {}),
  }
}

function buildFileActionCard(data: StatusUpdate): FileActionCard | null {
  const metadata = getStatusMetadata(data)
  const actionName = stringField(metadata.action_name || data.bridge_payload?.action_name)
  if (!actionName.startsWith('workspace.')) return null

  const status = stringField(metadata.action_status || data.bridge_payload?.action_status)
  if (status !== 'completed' && status !== 'failed') return null

  const target = (
    stringField(metadata.result_target_path)
    || stringField(metadata.result_path)
    || stringField(metadata.action_target_path)
    || stringField(metadata.action_rel_path)
    || stringField(metadata.action_target || data.bridge_payload?.action_target)
  )
  const source = stringField(metadata.result_source_path) || stringField(metadata.action_source_path)
  const query = stringField(metadata.action_query)
  const matchCount = numberField(metadata.result_match_count)
  const error = stringField(metadata.error || metadata.tool_error_code)
  const title = data.message || stringField(metadata.quip) || (status === 'completed' ? '文件动作完成。' : '文件动作失败。')

  return {
    title,
    status,
    actionName,
    target,
    source,
    result: stringField(metadata.result_path),
    query,
    matchCount,
    tool: stringField(metadata.tool_name || metadata.tool_output_kind),
    error,
  }
}

function handleQuip(_event: any, data: QuipMessage) {
  const content = String(data.content || '').trim()
  if (!content) return

  const node = getDisplayNodeName(data)
  const forceLog = data.metadata?.priority === 'high' || data.event_source !== 'workflow'
  const logDecision = shouldLogTransientEvent(
    `${data.event_type || 'quip'}:${data.node_name || ''}:${content}`,
    {
      throttleMs: QUIP_LOG_THROTTLE_MS,
      lastKey: lastQuipLogKey,
      lastAt: lastQuipLogAt,
      force: forceLog,
    },
  )
  if (!logDecision.shouldLog) return
  lastQuipLogAt = logDecision.nextAt
  lastQuipLogKey = logDecision.nextKey

  if (data.event_type === 'workflow.node_entered') {
    push('system', `[过程] ${content}（${node}）`)
    return
  }
  push('system', `[提示] ${content}`)
}

// 处理状态更新
function handleStatus(_event: any, data: StatusUpdate) {
  onBackendActivity()
  currentStatus.value = data.status
  currentProgress.value = data.progress ?? (data.status === 'done' ? 100 : 0)
  currentNode.value = data.node_name || ''
  currentNodeLabel.value = data.metadata?.node_label || ''
  const node = getDisplayNodeName(data)
  const isTerminalStatus = data.status === 'done' || data.status === 'error' || data.status === 'cancelled'
  const actionStatusText = getActionStatusText(data)
  const fileActionCard = buildFileActionCard(data)
  if (isTerminalStatus) {
    isSending.value = false
  }

  const logDecision = shouldLogTransientEvent(
    `${data.status}:${data.event_type || ''}:${data.node_name || ''}:${data.progress ?? ''}`,
    {
      throttleMs: STATUS_LOG_THROTTLE_MS,
      lastKey: lastStatusLogKey,
      lastAt: lastStatusLogAt,
      force: Boolean(fileActionCard) || isTerminalStatus || data.event_type === 'workflow.action_failed',
    },
  )
  if (!logDecision.shouldLog) return
  lastStatusLogAt = logDecision.nextAt
  lastStatusLogKey = logDecision.nextKey
  
  if (fileActionCard) {
    push('system', actionStatusText || fileActionCard.title, { fileAction: fileActionCard })
  } else if (actionStatusText) {
    push('system', actionStatusText)
  } else if (data.status === 'running') {
    push('system', `[状态] 正在运行... 节点: ${node} 进度: ${data.progress || 0}%`)
  } else if (data.status === 'done') {
    push('system', data.event_type === 'workflow.completed' ? '[状态] 工作流完成' : '[状态] 任务完成')
  } else if (data.status === 'error') {
    push('system', data.event_type === 'workflow.failed' ? '[状态] 工作流失败' : '[状态] 发生错误')
  } else if (data.status === 'cancelled') {
    push('system', '[状态] 任务已取消')
  }
}

// 处理表情消息
function handleExpression(_event: any, data: ExpressionMessage) {
  push('system', `[表情] 切换到: ${data.expression} (强度: ${data.intensity})`)
}

function buildContext(maxChars = 4000): string {
  // Provide recent transcript as lightweight context.
  const chunks: string[] = []
  for (let i = lines.value.length - 1; i >= 0; i--) {
    const l = lines.value[i]
    if (l.role === 'system') continue
    const prefix = l.role === 'user' ? 'User' : l.role === 'assistant' ? 'Assistant' : 'Other'
    const seg = `${prefix}: ${l.text}`
    chunks.unshift(seg)
    const joined = chunks.join('\n')
    if (joined.length > maxChars) break
  }
  const joined = chunks.join('\n')
  return joined.length > maxChars ? joined.slice(joined.length - maxChars) : joined
}

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

onMounted(() => {
  push('system', 'AI Chat 已启动。Enter 发送，Shift+Enter 换行，↑/↓ 历史，Ctrl+L 清屏。')
  if (!canInvoke.value) push('err', '（仅 Electron 可用：请通过 pnpm dev 启动桌面端）')
  focusInputSoon()
  
  // 监听消息
  if (ipcRenderer?.on) {
    ipcRenderer.on('agent:quip', handleQuip)
    ipcRenderer.on('agent:chat', handleChat)
    ipcRenderer.on('agent:error', handleError)
    ipcRenderer.on('agent:status', handleStatus)
    ipcRenderer.on('agent:expression', handleExpression)
  } else {
    push('err', 'IPC 不可用，无法接收 AI Agent 消息')
  }
})

onUnmounted(() => {
  if (ipcRenderer?.removeListener) {
    ipcRenderer.removeListener('agent:quip', handleQuip)
    ipcRenderer.removeListener('agent:chat', handleChat)
    ipcRenderer.removeListener('agent:error', handleError)
    ipcRenderer.removeListener('agent:status', handleStatus)
    ipcRenderer.removeListener('agent:expression', handleExpression)
  }
})


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

</script>

<template>
  <div class="chat-root">
    <!-- Header -->
    <header class="chat-header">
      <div class="header-left">
        <ChatHistoryPanel
          :currentSessionId="currentSessionId"
          @selectSession="switchSession"
          @newSession="createNewSession"
        />
        <span class="header-title">AI Chat</span>
        <PixelPet />
      </div>
      <div class="header-center">
        <WorkspaceSelector @updateWorkspace="updateWorkspace" />
      </div>
      <div class="header-right">
        <BackendIndicator />
        <div class="status-info" v-if="currentStatus !== 'idle'">
          <span class="status-dot" :class="currentStatus" />
          <span class="status-label">{{ currentNodeLabel || currentNode || currentStatus }}</span>
          <span v-if="currentProgress > 0" class="progress-text">{{ currentProgress }}%</span>
        </div>
        <button class="header-btn" type="button" @click="clearScreen" title="清屏">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
        </button>

        <button class="theme-toggle header-btn" type="button" @click="toggleTheme" :title="theme === 'dark' ? 'Switch Light' : 'Switch Dark'">
          <svg v-if="theme === 'dark'" class="theme-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
          <svg v-else class="theme-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        </button>
      </div>
    </header>

    <!-- Messages -->
    <div ref="outputRef" class="msg-list" role="log" aria-live="polite">
      <div v-for="(l, i) in lines" :key="i" class="msg-row" :class="l.role">
        <!-- Assistant with rich text -->
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
          <div class="file-action-card" :class="l.fileAction.status">
            <div class="file-action-head">
              <span class="file-action-title">{{ l.fileAction.title }}</span>
              <span class="file-action-badge">{{ l.fileAction.status }}</span>
            </div>
            <button class="msg-copy-btn" @click="copyMessage(l.fileAction.title + ' - ' + l.fileAction.status)" title="复制">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          </button>
          <div class="file-action-boxes">
              <div class="fa-box" v-if="l.fileAction.actionName">
                <span class="fa-box-label">动作</span>
                <code class="fa-box-value">{{ l.fileAction.actionName }}</code>
              </div>
              <div class="fa-box" v-if="l.fileAction.tool">
                <span class="fa-box-label">工具</span>
                <code class="fa-box-value">{{ l.fileAction.tool }}</code>
              </div>
              <div class="fa-box fa-box-error" v-if="l.fileAction.error">
                <span class="fa-box-label">错误</span>
                <code class="fa-box-value">{{ l.fileAction.error }}</code>
              </div>
            </div>
            <div class="file-action-meta" v-if="l.fileAction.source || l.fileAction.target || l.fileAction.query || typeof l.fileAction.matchCount === 'number'">
              <span v-if="l.fileAction.source">来源: {{ l.fileAction.source }}</span>
              <span v-if="l.fileAction.target">目标: {{ l.fileAction.target }}</span>
              <span v-if="l.fileAction.query">查询: {{ l.fileAction.query }}</span>
              <span v-if="typeof l.fileAction.matchCount === 'number'">命中: {{ l.fileAction.matchCount }}</span>
            </div>
          </div>
        </div>
        <!-- User message -->
        <div v-else-if="l.role === 'user'" class="msg-bubble user">
          <div class="msg-content">{{ l.text }}</div>
          <button class="msg-copy-btn" @click="copyMessage(l.text)" title="复制">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          </button>
        </div>
        <!-- System / error -->
        <div v-else class="msg-bubble system">
          <div class="msg-content">{{ l.text }}</div>
          <button class="msg-copy-btn" @click="copyMessage(l.text)" title="复制">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Input -->
    <footer class="input-area">
      <div class="input-row">
        <textarea
          ref="inputRef"
          v-model="input"
          class="input-box"
          placeholder="输入你的问题…（Enter 发送，Shift+Enter 换行）"
          spellcheck="false"
          rows="1"
          @keydown="onKeydown"
          @input="autoResizeInput"
        />
        <button class="send-btn" type="button" :disabled="isSending || !input.trim()" @click="submit" title="发送">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
      <div class="input-hint">Enter 发送 · Shift+Enter 换行 · Ctrl+L 清屏 · ↑↓ 历史</div>
    </footer>

    <!-- Desktop export confirm dialog -->
    <div v-if="desktopConfirmVisible" class="confirm-backdrop" role="dialog" aria-modal="true" tabindex="-1" @keydown.esc="resolveDesktopExportConfirmation(false)">
      <div class="confirm-panel">
        <div class="confirm-title">确认桌面文本导出</div>
        <div class="confirm-copy">这个请求可能会触发桌面文本导出。后端仍会限制只能写入配置好的 DESKTOP_EXPORT_DIR，但为了避免误操作，请确认是否继续发送这个请求。</div>
        <div class="confirm-actions">
          <button class="btn" type="button" @click="resolveDesktopExportConfirmation(false)">取消</button>
          <button class="btn primary" type="button" @click="resolveDesktopExportConfirmation(true)">继续发送</button>
        </div>
      </div>
    </div>
  </div>
</template>

<!-- Theme CSS Variables -->
<style>
:root {
  --bg-root: #f2ede6;
  --bg-surface: #f5f0ea;
  --bg-code: #f0ebe4;
  --bg-input: rgba(255,248,240,0.6);
  --bg-input-focus: rgba(255,248,240,0.8);
  --text-primary: #4a3f35;
  --text-secondary: #8b7355;
  --text-muted: rgba(74,63,53,0.45);
  --border-rgb: 139,115,85;
  --accent-indigo-rgb: 107,142,158;
  --accent-sakura-rgb: 244,172,183;
  --accent-error-rgb: 220,120,130;
  --text-primary-rgb: 74,63,53;
  --accent-green: #7eb8a0;
  --accent-green-bright: #9ece6a;
  --accent-link: #6b8e7a;
  --accent-sakura-text: #d08090;
  --accent-error-text: #c06070;
  --status-dot-idle: rgba(139,115,85,0.2);
  --scrollbar-thumb: rgba(139,115,85,0.12);
  --shadow-popup: 0 8px 32px rgba(0,0,0,0.12);
  --header-btn-bg: rgba(139,115,85,0.06);
  --header-btn-color: var(--text-muted);
  --header-btn-hover-bg: rgba(139,115,85,0.12);
  --header-btn-hover-color: #4a3f35;
  --input-border: rgba(139,115,85,0.15);
  --input-border-focus: rgba(139,115,85,0.3);
  --input-hint: rgba(139,115,85,0.35);
  --theme-transition: background-color 0.4s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

:root[data-theme=dark] {
  --bg-root: #1a1b26;
  --bg-surface: #1e2030;
  --bg-code: #161822;
  --bg-input: rgba(255,255,255,0.04);
  --bg-input-focus: rgba(255,255,255,0.06);
  --text-primary: #c0caf5;
  --text-secondary: #a9b1d6;
  --text-muted: rgba(169,177,214,0.45);
  --border-rgb: 169,177,214;
  --accent-indigo-rgb: 122,162,247;
  --accent-sakura-rgb: 255,210,218;
  --accent-error-rgb: 255,180,190;
  --text-primary-rgb: 192,202,245;
  --accent-green: #9ece6a;
  --accent-green-bright: #9ece6a;
  --accent-link: #7aa2f7;
  --accent-sakura-text: #e8a0b0;
  --accent-error-text: #e8a0b0;
  --status-dot-idle: rgba(169,177,214,0.2);
  --scrollbar-thumb: rgba(169,177,214,0.1);
  --shadow-popup: 0 8px 32px rgba(0,0,0,0.5);
  --header-btn-bg: rgba(169,177,214,0.06);
  --header-btn-color: rgba(192,202,245,0.45);
  --header-btn-hover-bg: rgba(169,177,214,0.12);
  --header-btn-hover-color: #c0caf5;
  --input-border: rgba(169,177,214,0.12);
  --input-border-focus: rgba(122,162,247,0.3);
  --input-hint: rgba(169,177,214,0.25);
}
</style>

<style scoped>
/* ================================================================
   Modern AI Chat UI — inspired by LobeChat / ChatGPT-Next-Web
   ================================================================ */

.chat-root {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-root);
  color: var(--text-primary);
  transition: var(--theme-transition);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans SC', sans-serif;
  font-size: 14px;
  line-height: 1.7;
  overflow: hidden;
}

/* ---- Header ---- */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid rgba(var(--border-rgb), 0.12);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: 0.02em;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: var(--header-btn-bg);
  color: var(--header-btn-color);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.header-btn:hover {
  background: var(--header-btn-hover-bg);
  color: var(--header-btn-hover-color);
}

/* Theme toggle animation */
.theme-icon {
  transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}
.theme-toggle:active .theme-icon {
  transform: rotate(180deg) scale(0.85);
}

.status-info {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--status-dot-idle);
}
.status-dot.running {
  background: var(--accent-green);
  box-shadow: 0 0 6px var(--accent-green);
  animation: pulse 1.2s ease-in-out infinite;
}
.status-dot.done { background: var(--accent-green-bright); }
.status-dot.error, .status-dot.failed { background: var(--accent-error-text); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.status-label {
  font-size: 11px;
  color: var(--text-muted);
}

.progress-text {
  font-size: 11px;
  color: var(--accent-green);
  font-weight: 600;
}

/* ---- Messages ---- */
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scroll-behavior: smooth;
}
.msg-list::-webkit-scrollbar {
  width: 5px;
}
.msg-list::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 99px;
}

.msg-row {
  display: flex;
  animation: fadeInUp 0.28s ease-out;
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

.msg-row.user {
  justify-content: flex-end;
}
.msg-row.assistant {
  justify-content: flex-start;
}
.msg-row.system, .msg-row.err {
  justify-content: center;
}

/* ---- Message Bubbles ---- */
.msg-bubble {
  max-width: 85%;
  border-radius: 14px;
  padding: 12px 16px;
  padding-right: 36px;
  word-break: break-word;
  overflow-wrap: anywhere;
  position: relative;
}

.msg-bubble.user {
  background: rgba(var(--accent-indigo-rgb), 0.1);
  border: 1px solid rgba(var(--accent-indigo-rgb), 0.16);
  color: var(--text-primary);
  border-bottom-right-radius: 4px;
}

.msg-bubble.assistant {
  background: rgba(var(--accent-sakura-rgb), 0.2);
  border: 1px solid rgba(var(--accent-sakura-rgb), 0.25);
  border-radius: 14px;
  padding: 10px 14px;
  border-bottom-left-radius: 4px;
}

.msg-bubble.system {
  background: rgba(var(--border-rgb), 0.06);
  color: var(--text-muted);
  font-size: 12px;
  padding: 6px 14px;
  border-radius: 8px;
}

.msg-row.err .msg-bubble {
  background: rgba(var(--accent-error-rgb), 0.1);
  border: 1px solid rgba(var(--accent-error-rgb), 0.2);
  color: var(--accent-error-text);
  font-size: 12.5px;
  border-radius: 8px;
}

.msg-content {
  white-space: pre-wrap;
}

.msg-content.rich {
  white-space: normal;
}

/* ---- Rich Markdown ---- */
.msg-content.rich :deep(p) {
  margin: 0 0 0.8em;
}
.msg-content.rich :deep(p:last-child) {
  margin-bottom: 0;
}
.msg-content.rich :deep(ul),
.msg-content.rich :deep(ol) {
  margin: 0.5em 0 0.8em;
  padding-left: 1.6em;
}
.msg-content.rich :deep(li + li) {
  margin-top: 0.3em;
}
.msg-content.rich :deep(code) {
  padding: 0.15em 0.4em;
  border-radius: 5px;
  background: rgba(var(--border-rgb), 0.08);
  color: var(--text-secondary);
  font-size: 0.9em;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
}

/* ---- Code Blocks ---- */
.msg-content.rich :deep(pre) {
  overflow-x: auto;
  margin: 0.65em 0 0.85em;
  padding: 14px 16px;
  border-radius: 10px;
  background: var(--bg-code);
  border: 1px solid rgba(var(--border-rgb), 0.12);
  position: relative;
}
.msg-content.rich :deep(pre code) {
  padding: 0;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.88em;
  line-height: 1.6;
}

/* ---- Blockquote ---- */
.msg-content.rich :deep(blockquote) {
  margin: 0.6em 0;
  padding-left: 1em;
  border-left: 3px solid rgba(var(--border-rgb), 0.3);
  color: var(--text-primary);
}

.msg-content.rich :deep(a) {
  color: var(--accent-link);
}

.msg-content.rich :deep(.katex-display) {
  overflow-x: auto;
  margin: 0.7em 0;
  padding: 0.25em 0;
}

/* ---- Code Copy Button ---- */
.msg-copy-row {
  margin-top: 6px;
  display: flex;
  justify-content: flex-end;
}

.copy-code-btn {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(var(--border-rgb), 0.12);
  background: rgba(var(--border-rgb), 0.06);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
}
.copy-code-btn:hover {
  background: rgba(var(--border-rgb), 0.1);
  color: var(--text-primary);
}

/* ---- File Action Card ---- */
.file-action-card {
  padding: 12px 14px;
  border: 1px solid rgba(var(--border-rgb), 0.15);
  border-radius: 10px;
  background: rgba(var(--border-rgb), 0.05);
  color: var(--text-primary);
}
.file-action-card.failed {
  border-color: rgba(var(--accent-error-rgb), 0.25);
  background: rgba(var(--accent-error-rgb), 0.06);
}
.file-action-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.file-action-title {
  font-weight: 700;
}
.file-action-badge {
  padding: 2px 8px;
  border-radius: 99px;
  background: rgba(var(--border-rgb), 0.12);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.file-action-boxes {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.fa-box {
  flex: 1;
  min-width: 130px;
  max-width: 280px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(var(--border-rgb), 0.06);
  border: 1px solid rgba(var(--border-rgb), 0.1);
  overflow: hidden;
}
.fa-box-error {
  background: rgba(var(--accent-error-rgb), 0.08);
  border-color: rgba(var(--accent-error-rgb), 0.18);
}
.fa-box-label {
  display: block;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}
.fa-box-value {
  display: block;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fa-box-error .fa-box-value {
  color: var(--accent-error-text);
}
.file-action-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 10.5px;
  color: var(--text-muted);
}
.file-action-meta span {
  white-space: nowrap;
}
.file-action-error code { color: var(--accent-sakura-text); }

/* ---- Copy Button ---- */
.msg-copy-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: rgba(var(--border-rgb), 0.06);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s, background 0.15s;
  z-index: 2;
}
.msg-bubble:hover .msg-copy-btn,
.msg-copy-btn:focus-visible {
  opacity: 1;
}
.msg-copy-btn:hover {
  background: rgba(var(--border-rgb), 0.12);
  color: var(--text-primary);
}
.msg-copy-btn:active {
  transform: scale(0.9);
}

/* ---- Input Area ---- */
.input-area {
  flex-shrink: 0;
  padding: 10px 16px 14px;
  border-top: 1px solid rgba(var(--border-rgb), 0.1);
}

.input-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.input-box {
  flex: 1;
  resize: none;
  border-radius: 12px;
  border: 1px solid var(--input-border);
  background: var(--bg-input);
  color: var(--text-primary);
  padding: 10px 14px;
  outline: none;
  font-size: 14px;
  line-height: 1.55;
  font-family: inherit;
  max-height: 200px;
  transition: border-color 0.15s;
}
.input-box:focus {
  border-color: var(--input-border-focus);
  background: var(--bg-input-focus);
}
.input-box::placeholder {
  color: var(--input-hint);
}

.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  border: none;
  background: rgba(var(--accent-sakura-rgb), 0.25);
  color: var(--accent-sakura-text);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
}
.send-btn:hover:not(:disabled) {
  background: rgba(var(--accent-sakura-rgb), 0.4);
  transform: scale(1.04);
}
.send-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.input-hint {
  margin-top: 6px;
  font-size: 10.5px;
  color: var(--input-hint);
  text-align: center;
}

/* ---- Buttons (confirm dialog) ---- */
.btn {
  height: 36px;
  padding: 0 16px;
  border-radius: 9px;
  border: 1px solid rgba(var(--border-rgb), 0.12);
  background: rgba(var(--border-rgb), 0.05);
  color: var(--text-primary);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}
.btn:hover {
  background: rgba(var(--border-rgb), 0.1);
}
.btn.primary {
  background: rgba(107,142,158,0.15);
  border-color: rgba(107,142,158,0.25);
  color: var(--accent-link);
}
.btn.primary:hover {
  background: rgba(107,142,158,0.22);
}

/* ---- Confirm Dialog ---- */
.confirm-backdrop {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  padding: 18px;
  background: rgba(0,0,0,0.6);
}
.confirm-panel {
  width: min(440px, 100%);
  border: 1px solid rgba(var(--border-rgb), 0.15);
  border-radius: 14px;
  padding: 20px;
  background: var(--bg-root);
  box-shadow: 0 18px 48px rgba(0,0,0,0.5);
}
.confirm-title {
  margin-bottom: 10px;
  font-size: 15px;
  font-weight: 700;
}
.confirm-copy {
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.7;
}
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

/* ---- Workspace / History integration ---- */
:deep(.workspace-bar) {
  font-size: 11px;
}
</style>
