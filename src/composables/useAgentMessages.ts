import { ref, type Ref } from 'vue'
import type { IpcRendererLike } from '../platform/electronIpc'

// ---- Type definitions ----

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

export type MessageContentType = 'plain_text' | 'markdown'
export type MessageRenderMode = 'plain_text' | 'rich_text'

export type ChatLine = {
  role: 'user' | 'assistant' | 'system' | 'err'
  text: string
  contentType?: MessageContentType
  renderMode?: MessageRenderMode
  fileAction?: FileActionCard
}

export type AgentChatResponse = {
  ok: boolean
  output: string
  content_type?: MessageContentType
  render_mode?: MessageRenderMode
}

// AI Agent message type definitions
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
    content_type?: MessageContentType
    render_mode?: MessageRenderMode
  }
  content_type?: MessageContentType
  render_mode?: MessageRenderMode
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

export type QuipMessage = {
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

// ---- Internal throttle state ----
const STATUS_LOG_THROTTLE_MS = 850
const QUIP_LOG_THROTTLE_MS = 850
let lastStatusLogAt = 0
let lastStatusLogKey = ''
let lastQuipLogAt = 0
let lastQuipLogKey = ''

// ---- Partial messages ----
const partialMessages = new Map<number, string>()

// ---- Helper functions ----

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

// ---- Options interface ----

type StatusTickerLike = {
  push: (msg: string) => void
}

interface UseAgentMessagesOptions {
  push: (role: ChatLine['role'], text: string, extra?: Omit<ChatLine, 'role' | 'text'>) => void
  startTypewriter: (text: string, renderMode?: 'rich_text' | 'plain_text') => void
  lines: Ref<ChatLine[]>
  statusTickerRef: Ref<StatusTickerLike | null>
  isSending: Ref<boolean>
  normalizeAssistantContent: (text: string) => string
  onBackendActivity: () => void
}

export function useAgentMessages(options: UseAgentMessagesOptions) {
  const { push, lines, statusTickerRef, isSending, normalizeAssistantContent, onBackendActivity } = options

  // ---- State refs ----
  const currentStatus = ref('idle')
  const currentProgress = ref(0)
  const currentNode = ref('')
  const currentNodeLabel = ref('')

  // Track last assistant message content for dedup (prevents double-reply from IPC + invoke)
  let _lastAssistantContent = ''

  // ---- Handler functions ----

  function handleChat(_event: any, data: ChatMessage) {
    onBackendActivity()
    const { content, metadata } = data

    const normalizedIncoming = normalizeAssistantContent(content)

    // Dedup: skip if identical to what we already pushed from HTTP response
    if (normalizedIncoming && normalizedIncoming === _lastAssistantContent) return

    if (metadata?.is_partial && typeof metadata.sequence_id === 'number' && typeof metadata.total_parts === 'number') {
      // Handle streaming output
      const { sequence_id, total_parts } = metadata
      partialMessages.set(sequence_id, content)

      // Check if all parts have been received
      if (partialMessages.size === total_parts) {
        // Combine all parts in order
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
      // Complete message, display directly
      _lastAssistantContent = normalizedIncoming
      push('assistant', content, {
        contentType: data.content_type || metadata?.content_type || 'markdown',
        renderMode: data.render_mode || metadata?.render_mode || 'rich_text',
      })
    }
  }

  function handleError(_event: any, data: ErrorMessage) {
    onBackendActivity()
    push('err', `[${data.code}] ${data.message}`)
    if (data.details) {
      push('err', JSON.stringify(data.details, null, 2))
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
      statusTickerRef.value?.push(`[过程] ${content}（${node}）`)
      return
    }
    statusTickerRef.value?.push(`[提示] ${content}`)
  }

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
      statusTickerRef.value?.push(actionStatusText)
    } else if (data.status === 'running') {
      statusTickerRef.value?.push(`[状态] 正在运行... 节点: ${node} 进度: ${data.progress || 0}%`)
    } else if (data.status === 'done') {
      statusTickerRef.value?.push('[状态] 任务完成')
    } else if (data.status === 'error') {
      statusTickerRef.value?.push('[状态] 工作流失败')
    } else if (data.status === 'cancelled') {
      statusTickerRef.value?.push('[状态] 任务已取消')
    }
  }

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

  // ---- IPC listener management ----

  function registerIpcListeners(ipcRenderer: IpcRendererLike | null) {
    if (ipcRenderer?.on) {
      ipcRenderer.on('agent:quip', handleQuip)
      ipcRenderer.on('agent:chat', handleChat)
      ipcRenderer.on('agent:error', handleError)
      ipcRenderer.on('agent:status', handleStatus)
      ipcRenderer.on('agent:expression', handleExpression)
    }
  }

  function unregisterIpcListeners(ipcRenderer: IpcRendererLike | null) {
    if (ipcRenderer?.removeListener) {
      ipcRenderer.removeListener('agent:quip', handleQuip)
      ipcRenderer.removeListener('agent:chat', handleChat)
      ipcRenderer.removeListener('agent:error', handleError)
      ipcRenderer.removeListener('agent:status', handleStatus)
      ipcRenderer.removeListener('agent:expression', handleExpression)
    }
  }

  return {
    currentStatus,
    currentProgress,
    currentNode,
    currentNodeLabel,
    buildContext,
    registerIpcListeners,
    unregisterIpcListeners,
  }
}
