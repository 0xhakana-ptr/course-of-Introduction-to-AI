<script setup lang="ts">
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

const outputRef = ref<HTMLDivElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const canInvoke = computed(() => Boolean(ipcRenderer?.invoke))
const desktopConfirmVisible = ref(false)
let desktopConfirmResolver: ((confirmed: boolean) => void) | null = null

function push(role: ChatLine['role'], text: string, extra: Omit<ChatLine, 'role' | 'text'> = {}) {
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

// 处理 Chat 消息
function handleChat(_event: any, data: ChatMessage) {
  const { content, metadata } = data
  
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
      push('assistant', fullContent, {
        contentType: data.content_type || metadata.content_type || 'markdown',
        renderMode: data.render_mode || metadata.render_mode || 'rich_text',
      })
      partialMessages.clear()
    }
  } else {
    // 完整消息，直接显示
    push('assistant', content, {
      contentType: data.content_type || metadata?.content_type || 'markdown',
      renderMode: data.render_mode || metadata?.render_mode || 'rich_text',
    })
  }
}

// 处理错误消息
function handleError(_event: any, data: ErrorMessage) {
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
    const res = (await ipcRenderer.invoke('agent:chat', { prompt: trimmed, context })) as AgentChatResponse
    if (res?.ok) {
      push('assistant', res.output || '(ok)', {
        contentType: res.content_type || 'markdown',
        renderMode: res.render_mode || 'rich_text',
      })
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
</script>

<template>
  <div class="chat-root">
    <div class="header">
      <div class="title">AI Chat</div>
      <div class="right">
        <!-- 显示当前状态 -->
        <div class="status-info" v-if="currentStatus !== 'idle'">
          <span class="status-badge" :class="currentStatus">{{ currentStatus }}</span>
          <span v-if="currentProgress > 0" class="progress">{{ currentProgress }}%</span>
          <span v-if="currentNodeLabel || currentNode" class="node">{{ currentNodeLabel || currentNode }}</span>
        </div>
        <div class="status" :class="{ busy: isSending }">{{ isSending ? 'thinking…' : 'ready' }}</div>
        <button class="btn" type="button" @click="clearScreen">清屏</button>
      </div>
    </div>

    <div ref="outputRef" class="output" role="log" aria-live="polite">
      <div v-for="(l, i) in lines" :key="i" class="line" :class="l.role">
        <div
          v-if="shouldRenderRichMessage(l)"
          class="rich-message"
          v-html="renderAssistantText(l.text)"
        />
        <div
          v-else-if="l.fileAction"
          class="file-action-card"
          :class="l.fileAction.status"
        >
          <div class="file-action-head">
            <span class="file-action-title">{{ l.fileAction.title }}</span>
            <span class="file-action-badge">{{ l.fileAction.status }}</span>
          </div>
          <div class="file-action-grid">
            <div v-if="l.fileAction.actionName">
              <span>动作</span>
              <code>{{ l.fileAction.actionName }}</code>
            </div>
            <div v-if="l.fileAction.source">
              <span>来源</span>
              <code>{{ l.fileAction.source }}</code>
            </div>
            <div v-if="l.fileAction.target">
              <span>目标</span>
              <code>{{ l.fileAction.target }}</code>
            </div>
            <div v-if="l.fileAction.query">
              <span>查询</span>
              <code>{{ l.fileAction.query }}</code>
            </div>
            <div v-if="typeof l.fileAction.matchCount === 'number'">
              <span>命中</span>
              <code>{{ l.fileAction.matchCount }}</code>
            </div>
            <div v-if="l.fileAction.tool">
              <span>工具</span>
              <code>{{ l.fileAction.tool }}</code>
            </div>
            <div v-if="l.fileAction.error" class="file-action-error">
              <span>错误</span>
              <code>{{ l.fileAction.error }}</code>
            </div>
          </div>
        </div>
        <template v-else>{{ l.text }}</template>
      </div>
    </div>

    <div class="input-wrap">
      <textarea
        ref="inputRef"
        v-model="input"
        class="cmd"
        placeholder="像命令行一样输入你的要求…（Enter 发送，Shift+Enter 换行）"
        spellcheck="false"
        @keydown="onKeydown"
      />
      <div class="actions">
        <button class="btn primary" type="button" :disabled="isSending" @click="submit">发送</button>
      </div>
    </div>

    <div
      v-if="desktopConfirmVisible"
      class="confirm-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="desktop-export-confirm-title"
      tabindex="-1"
      @keydown.esc="resolveDesktopExportConfirmation(false)"
    >
      <div class="confirm-panel">
        <div id="desktop-export-confirm-title" class="confirm-title">确认桌面文本导出</div>
        <div class="confirm-copy">
          这个请求可能会触发桌面文本导出。后端仍会限制只能写入配置好的 DESKTOP_EXPORT_DIR，
          但为了避免误操作，请确认是否继续发送这个请求。
        </div>
        <div class="confirm-actions">
          <button class="btn" type="button" @click="resolveDesktopExportConfirmation(false)">取消</button>
          <button class="btn primary" type="button" @click="resolveDesktopExportConfirmation(true)">继续发送</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-root {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  padding: 12px;
  gap: 10px;
  background: #0f1115;
  color: #eaeaea;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.title {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0.2px;
}

.right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status {
  font-size: 12px;
  opacity: 0.85;
}

.status.busy {
  opacity: 1;
}

.output {
  flex: 1;
  overflow: auto;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.04);
  white-space: pre-wrap;
}

.line {
  line-height: 1.55;
  font-size: 12.5px;
}

.rich-message {
  white-space: normal;
}

.rich-message :deep(p) {
  margin: 0 0 0.72em;
}

.rich-message :deep(p:last-child) {
  margin-bottom: 0;
}

.rich-message :deep(ul),
.rich-message :deep(ol) {
  margin: 0.4em 0 0.72em;
  padding-left: 1.5em;
}

.rich-message :deep(li + li) {
  margin-top: 0.22em;
}

.rich-message :deep(code) {
  padding: 0.12em 0.34em;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.1);
  color: #f3f6ff;
}

.rich-message :deep(pre) {
  overflow: auto;
  margin: 0.55em 0 0.75em;
  padding: 10px 12px;
  border-radius: 9px;
  background: rgba(0, 0, 0, 0.34);
  white-space: pre;
}

.rich-message :deep(pre code) {
  padding: 0;
  background: transparent;
}

.rich-message :deep(blockquote) {
  margin: 0.55em 0;
  padding-left: 0.9em;
  border-left: 3px solid rgba(183, 215, 255, 0.38);
  color: rgba(234, 234, 234, 0.82);
}

.rich-message :deep(a) {
  color: #b7d7ff;
}

.rich-message :deep(.katex-display) {
  overflow-x: auto;
  overflow-y: hidden;
  margin: 0.65em 0;
  padding: 0.2em 0;
}

.line.user {
  color: #b7d7ff;
}

.line.assistant {
  color: #eaeaea;
}

.line.system {
  color: rgba(234, 234, 234, 0.72);
}

.line.err {
  color: #ffb4b4;
}

.file-action-card {
  margin: 6px 0;
  padding: 10px 12px;
  border: 1px solid rgba(183, 215, 255, 0.16);
  border-radius: 10px;
  background: rgba(183, 215, 255, 0.06);
  color: rgba(234, 234, 234, 0.88);
  white-space: normal;
}

.file-action-card.failed {
  border-color: rgba(255, 180, 180, 0.28);
  background: rgba(255, 180, 180, 0.07);
}

.file-action-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.file-action-title {
  font-weight: 800;
}

.file-action-badge {
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.file-action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 6px 12px;
}

.file-action-grid > div {
  min-width: 0;
}

.file-action-grid span {
  display: block;
  margin-bottom: 2px;
  color: rgba(234, 234, 234, 0.52);
  font-size: 10.5px;
}

.file-action-grid code {
  display: block;
  overflow: hidden;
  padding: 3px 6px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.26);
  color: #f3f6ff;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-action-error code {
  color: #ffb4b4;
}

.input-wrap {
  display: flex;
  gap: 10px;
  align-items: stretch;
}

.cmd {
  flex: 1;
  min-height: 92px;
  max-height: 220px;
  resize: vertical;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.35);
  color: inherit;
  padding: 10px 12px;
  outline: none;
  line-height: 1.5;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.btn {
  height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  cursor: pointer;
}

.status-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: 12px;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.status-badge.running {
  background: rgba(183, 215, 255, 0.2);
  color: #b7d7ff;
}

.status-badge.done {
  background: rgba(180, 255, 180, 0.2);
  color: #b4ffb4;
}

.status-badge.error {
  background: rgba(255, 180, 180, 0.2);
  color: #ffb4b4;
}

.status-badge.cancelled {
  background: rgba(255, 220, 160, 0.2);
  color: #ffdca0;
}

.status-badge.paused {
  background: rgba(220, 220, 220, 0.16);
  color: #dddddd;
}

.progress {
  font-size: 11px;
  color: rgba(234, 234, 234, 0.8);
}

.node {
  font-size: 11px;
  color: rgba(234, 234, 234, 0.6);
}


.btn.primary {
  background: rgba(183, 215, 255, 0.14);
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.confirm-backdrop {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  padding: 18px;
  background: rgba(0, 0, 0, 0.56);
}

.confirm-panel {
  width: min(460px, 100%);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 14px;
  padding: 18px;
  background: #161a22;
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.42);
}

.confirm-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 800;
}

.confirm-copy {
  color: rgba(234, 234, 234, 0.78);
  font-size: 12.5px;
  line-height: 1.7;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}
</style>
