<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { getIpcRenderer } from '../platform/electronIpc'
import { useMarkdownRenderer } from '../composables/useMarkdownRenderer'
import { useAgentMessages, type ChatLine } from '../composables/useAgentMessages'
import { useChatOperations } from '../composables/useChatOperations'
import BackendIndicator from './BackendIndicator.vue'
import PixelPet from './PixelPet.vue'
import StatusTicker from './StatusTicker.vue'
import PixelLoading from './PixelLoading.vue'
import ChatHistoryPanel from './ChatHistoryPanel.vue'
import WorkspaceSelector from './WorkspaceSelector.vue'
import ChatMessageList from './ChatMessageList.vue'
import ChatInputArea from './ChatInputArea.vue'

const ipcRenderer = getIpcRenderer()

// ---- Theme ----
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

// Init theme from localStorage
const savedTheme = localStorage.getItem('cyber-waifu-theme')
if (savedTheme === 'dark' || savedTheme === 'light') {
  theme.value = savedTheme
}
document.documentElement.setAttribute('data-theme', theme.value)

// ---- Shared state ----
const lines = ref<ChatLine[]>([])
const outputRef = ref<HTMLDivElement | null>(null)
const inputAreaRef = ref<InstanceType<typeof ChatInputArea> | null>(null)
const statusTickerRef = ref<InstanceType<typeof StatusTicker> | null>(null)
const canInvoke = computed(() => Boolean(ipcRenderer?.invoke))

// ---- Core functions ----
function push(role: ChatLine['role'], text: string, extra: Omit<ChatLine, 'role' | 'text'> = {}) {
  if (role === 'assistant' && text) {
    const mode = (extra.renderMode || 'rich_text') as 'rich_text' | 'plain_text'
    chat.startTypewriter(text, mode)
    return
  }
  if (role !== 'assistant') {
    chat.flushTypewriter(true)
  }
  lines.value.push({ role, text, ...extra })
  if (lines.value.length > 500) lines.value.splice(0, lines.value.length - 500)
  void nextTick(() => {
    const el = outputRef.value
    if (!el) return
    el.scrollTop = el.scrollHeight
  })
}

function clearScreen() {
  chat.flushTypewriter(true)
  lines.value = []
  push('system', '屏幕已清空（Ctrl+L）。')
  focusInputSoon()
}

function focusInputSoon() {
  void nextTick(() => {
    window.setTimeout(() => {
      ipcRenderer?.send?.('chat:focus-window')
      inputAreaRef.value?.textarea?.focus()
    }, 0)
  })
}

function buildContext(maxChars = 4000): string {
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

// ---- Composables ----
const { renderAssistantText, normalizeAssistantContent, shouldRenderRichMessage } = useMarkdownRenderer()

const chat = useChatOperations({
  ipcRenderer,
  lines,
  push,
  clearScreen,
  focusInputSoon,
  buildContext,
  normalizeAssistantContent,
  statusTickerRef,
})

const messages = useAgentMessages({
  push,
  startTypewriter: (text, mode) => chat.startTypewriter(text, mode),
  lines,
  statusTickerRef,
  isSending: chat.isSending,
  normalizeAssistantContent,
  onBackendActivity: () => chat.onBackendActivity(),
})

// Override autoResizeInput to use ChatInputArea's exposed textarea
chat.autoResizeInput = () => {
  const el = inputAreaRef.value?.textarea ?? null
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

// ---- Lifecycle ----
onMounted(() => {
  statusTickerRef.value?.push('AI Chat 已启动')
  if (!canInvoke.value) push('err', '（仅 Electron 可用：请通过 pnpm dev 启动桌面端）')
  focusInputSoon()
  messages.registerIpcListeners(ipcRenderer)
  if (!ipcRenderer?.on) {
    push('err', 'IPC 不可用，无法接收 AI Agent 消息')
  }
})

onUnmounted(() => {
  messages.unregisterIpcListeners(ipcRenderer)
})
</script>

<template>
  <div class="chat-root">
    <!-- Header -->
    <header class="chat-header">
      <div class="header-left">
        <ChatHistoryPanel
          :currentSessionId="chat.currentSessionId.value"
          @selectSession="chat.switchSession"
          @newSession="chat.createNewSession"
        />
        <span class="header-title">AI Chat</span>
        <PixelPet />
        <StatusTicker ref="statusTickerRef" />
      </div>
      <div class="header-center">
        <WorkspaceSelector @updateWorkspace="chat.updateWorkspace" />
      </div>
      <div class="header-right">
        <BackendIndicator />
        <div class="status-info" v-if="messages.currentStatus.value !== 'idle'">
          <span class="status-dot" :class="messages.currentStatus.value" />
          <span class="status-label">{{ messages.currentNodeLabel.value || messages.currentNode.value || messages.currentStatus.value }}</span>
          <span v-if="messages.currentProgress.value > 0" class="progress-text">{{ messages.currentProgress.value }}%</span>
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
      <ChatMessageList
        :lines="lines"
        :shouldRenderRichMessage="shouldRenderRichMessage"
        :renderAssistantText="renderAssistantText"
        :hasCodeBlocks="chat.hasCodeBlocks"
        :copyLastCodeBlock="chat.copyLastCodeBlock"
        :copyMessage="copyMessage"
      >
        <template #after-messages>
          <div v-if="chat.isSending.value" class="msg-row assistant">
            <PixelLoading />
          </div>
        </template>
      </ChatMessageList>
    </div>

    <!-- Input -->
    <ChatInputArea
      ref="inputAreaRef"
      :modelValue="chat.input.value"
      :isSending="chat.isSending.value"
      :onKeydown="chat.onKeydown"
      :onSubmit="chat.submit"
      :autoResizeInput="chat.autoResizeInput"
      @update:modelValue="chat.input.value = $event"
    />

    <!-- Desktop export confirm dialog -->
    <div v-if="chat.desktopConfirmVisible.value" class="confirm-backdrop" role="dialog" aria-modal="true" tabindex="-1" @keydown.esc="chat.resolveDesktopExportConfirmation(false)">
      <div class="confirm-panel">
        <div class="confirm-title">确认桌面文本导出</div>
        <div class="confirm-copy">这个请求可能会触发桌面文本导出。后端仍会限制只能写入配置好的 DESKTOP_EXPORT_DIR，但为了避免误操作，请确认是否继续发送这个请求。</div>
        <div class="confirm-actions">
          <button class="btn" type="button" @click="chat.resolveDesktopExportConfirmation(false)">取消</button>
          <button class="btn primary" type="button" @click="chat.resolveDesktopExportConfirmation(true)">继续发送</button>
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

/* ---- Workspace / History integration ---- */
:deep(.workspace-bar) {
  font-size: 11px;
}
</style>
