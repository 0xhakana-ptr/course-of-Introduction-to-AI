<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getIpcRenderer } from '../platform/electronIpc'

const ipcRenderer = getIpcRenderer()

type SessionItem = {
  session_id: string
  summary_preview?: string
  message_count?: number
  last_message_at?: string
}

defineProps<{
  currentSessionId?: string
}>()

const emit = defineEmits<{
  selectSession: [sessionId: string]
  newSession: []
}>()

const sessions = ref<SessionItem[]>([])
const isOpen = ref(false)

async function loadSessions() {
  if (!ipcRenderer?.invoke) return
  try {
    const result = await ipcRenderer.invoke('chat:listSessions', { limit: 20 })
    if (result?.ok && Array.isArray(result.sessions)) {
      sessions.value = result.sessions
    }
  } catch {
    // IPC not available
  }
}

function formatPreview(preview: string | undefined): string {
  if (!preview) return '(空对话)'
  return preview.length > 40 ? preview.slice(0, 40) + '...' : preview
}

function formatTime(ts: string | undefined): string {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

function toggle() {
  isOpen.value = !isOpen.value
  if (isOpen.value) loadSessions()
}

async function exportSession(sessionId: string) {
  if (!ipcRenderer?.invoke) return
  try {
    const result = await ipcRenderer.invoke('chat:exportSession', { sessionId }) as any
    if (result?.ok && result.text) {
      // Save to file using download
      const blob = new Blob([result.text], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `chat-${sessionId.slice(0, 8)}.txt`
      a.click()
      URL.revokeObjectURL(url)
    }
  } catch {
    // Silently fail
  }
}

onMounted(() => loadSessions())
</script>

<template>
  <div class="history-wrap">
    <button class="history-toggle" type="button" @click="toggle" title="聊天记录">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
      </svg>
    </button>

    <div v-if="isOpen" class="history-panel">
      <div class="history-header">
        <span>聊天记录</span>
        <button class="new-chat-btn" @click="emit('newSession')">+ 新对话</button>
      </div>
      <div class="history-list">
        <div
          v-for="s in sessions"
          :key="s.session_id"
          class="history-item"
        >
          <div class="history-item-main" @click="emit('selectSession', s.session_id); isOpen = false">
            <div class="history-preview">{{ formatPreview(s.summary_preview) }}</div>
            <div class="history-meta">
              <span>{{ s.message_count || 0 }} 条消息</span>
              <span v-if="s.last_message_at">{{ formatTime(s.last_message_at) }}</span>
            </div>
          </div>
          <button class="export-btn" @click.stop="exportSession(s.session_id)" title="导出聊天记录">
            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
          </button>
        </div>
        <div v-if="sessions.length === 0" class="history-empty">
          暂无聊天记录
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-wrap {
  position: relative;
}

.history-toggle {
  background: none;
  border: none;
  color: rgba(255,255,255,0.7);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
}
.history-toggle:hover {
  background: rgba(255,255,255,0.08);
  color: #fff;
}

.history-panel {
  position: absolute;
  top: 36px;
  left: 0;
  width: 280px;
  max-height: 400px;
  background: #1a1d2a;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 10px;
  z-index: 200;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  font-weight: 700;
  font-size: 13px;
}

.new-chat-btn {
  background: rgba(100,180,255,0.15);
  border: 1px solid rgba(100,180,255,0.2);
  color: #a0c8ff;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
}
.new-chat-btn:hover {
  background: rgba(100,180,255,0.25);
}

.history-list {
  overflow-y: auto;
  max-height: 340px;
}

.history-item {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  cursor: pointer;
}
.history-item:hover {
  background: rgba(255,255,255,0.04);
}

.history-preview {
  font-size: 12.5px;
  color: rgba(255,255,255,0.85);
  margin-bottom: 4px;
  line-height: 1.4;
}

.history-meta {
  display: flex;
  gap: 12px;
  font-size: 10.5px;
  color: rgba(255,255,255,0.4);
}

.history-empty {
  padding: 20px;
  text-align: center;
  color: rgba(255,255,255,0.35);
  font-size: 12px;
}

.history-item {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
}

.history-item-main {
  flex: 1;
  cursor: pointer;
  min-width: 0;
}

.export-btn {
  background: none;
  border: none;
  color: rgba(255,255,255,0.2);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  flex-shrink: 0;
  margin-left: 8px;
}
.export-btn:hover {
  color: rgba(255,255,255,0.7);
  background: rgba(255,255,255,0.06);
}
</style>
