<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { getIpcRenderer } from '../platform/electronIpc'

type ChatLine = { role: 'user' | 'assistant' | 'system' | 'err'; text: string }
type AgentChatResponse = { ok: boolean; output: string }

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
  }
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
  status: 'idle' | 'running' | 'paused' | 'done' | 'error'
  progress?: number
  node_name?: string
  timestamp: string
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

// 存储部分消息
const partialMessages = new Map<number, string>()

const outputRef = ref<HTMLDivElement | null>(null)
const canInvoke = computed(() => Boolean(ipcRenderer?.invoke))

function push(role: ChatLine['role'], text: string) {
  lines.value.push({ role, text })
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
}

// 处理 Chat 消息
function handleChat(event: any, data: ChatMessage) {
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
      push('assistant', fullContent)
      partialMessages.clear()
    }
  } else {
    // 完整消息，直接显示
    push('assistant', content)
  }
}

// 处理错误消息
function handleError(event: any, data: ErrorMessage) {
  push('err', `[${data.code}] ${data.message}`)
  if (data.details) {
    push('err', JSON.stringify(data.details, null, 2))
  }
}

// 处理状态更新
function handleStatus(event: any, data: StatusUpdate) {
  currentStatus.value = data.status
  currentProgress.value = data.progress || 0
  currentNode.value = data.node_name || ''
  
  if (data.status === 'running') {
    push('system', `[状态] 正在运行... 节点: ${data.node_name || '未知'} 进度: ${data.progress || 0}%`)
  } else if (data.status === 'done') {
    push('system', '[状态] 任务完成')
  } else if (data.status === 'error') {
    push('system', '[状态] 发生错误')
  }
}

// 处理表情消息
function handleExpression(event: any, data: ExpressionMessage) {
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

async function sendPrompt(prompt: string) {
  const trimmed = prompt.trim()
  if (!trimmed) return

  if (!ipcRenderer?.invoke) {
    push('err', '当前窗口没有可用的 ipcRenderer.invoke（请确认在 Electron 中运行）')
    return
  }

  isSending.value = true
  push('user', `> ${trimmed}`)

  try {
    const context = buildContext()
    const res = (await ipcRenderer.invoke('agent:chat', { prompt: trimmed, context })) as AgentChatResponse
    if (res?.ok) push('assistant', res.output || '(ok)')
    else push('err', res?.output || '(error)')
  } catch (e) {
    push('err', String(e))
  } finally {
    isSending.value = false
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
  
  // 监听消息
  if (ipcRenderer) {
    ipcRenderer.on('agent:chat', handleChat)
    ipcRenderer.on('agent:error', handleError)
    ipcRenderer.on('agent:status', handleStatus)
    ipcRenderer.on('agent:expression', handleExpression)
  } else {
    push('err', 'IPC 不可用，无法接收 AI Agent 消息')
  }
})

onUnmounted(() => {
  if (ipcRenderer) {
    ipcRenderer.removeListener('agent:chat', handleChat)
    ipcRenderer.removeListener('agent:error', handleError)
    ipcRenderer.removeListener('agent:status', handleStatus)
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
          <span v-if="currentNode" class="node">{{ currentNode }}</span>
        </div>
        <div class="status" :class="{ busy: isSending }">{{ isSending ? 'thinking…' : 'ready' }}</div>
        <button class="btn" type="button" @click="clearScreen">清屏</button>
      </div>
    </div>

    <div ref="outputRef" class="output" role="log" aria-live="polite">
      <div v-for="(l, i) in lines" :key="i" class="line" :class="l.role">
        {{ l.text }}
      </div>
    </div>

    <div class="input-wrap">
      <textarea
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
</style>