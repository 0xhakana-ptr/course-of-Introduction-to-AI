<script setup lang="ts">
import { ref, nextTick } from 'vue'

export interface StatusEntry {
  text: string
  time: string
}

const history = ref<StatusEntry[]>([])
const current = ref<StatusEntry | null>(null)
const animating = ref(false)
const showHistory = ref(false)
const historyPanelRef = ref<HTMLDivElement | null>(null)

function push(text: string) {
  if (!text) return
  const entry: StatusEntry = {
    text,
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
  }
  history.value.push(entry)

  if (animating.value) {
    // Still animating, queue the update
    current.value = entry
    return
  }

  if (current.value) {
    animating.value = true
    // Wait for exit animation, then swap
    setTimeout(() => {
      current.value = entry
      animating.value = false
    }, 200)
  } else {
    current.value = entry
  }
}

function toggleHistory() {
  showHistory.value = !showHistory.value
  if (showHistory.value) {
    nextTick(() => {
      if (historyPanelRef.value) {
        historyPanelRef.value.scrollTop = historyPanelRef.value.scrollHeight
      }
    })
  }
}

function closeHistory(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.classList.contains('status-history-backdrop')) {
    showHistory.value = false
  }
}

defineExpose({ push })
</script>

<template>
  <div class="status-ticker">
    <!-- Latest message box -->
    <div
      class="ticker-box"
      :class="{ 'ticker-exit': animating }"
      @click="toggleHistory"
      title="点击查看历史状态消息"
    >
      <div class="ticker-inner" :key="current?.time || 'empty'">
        <span class="ticker-text">{{ current?.text || '就绪' }}</span>
        <span class="ticker-time">{{ current?.time || '' }}</span>
      </div>
    </div>

    <!-- History popup -->
    <Teleport to="body">
      <div
        v-if="showHistory"
        class="status-history-backdrop"
        @click="closeHistory"
      >
        <div class="status-history-panel" @click.stop>
          <div class="status-history-header">
            <span>状态历史</span>
            <button class="status-history-close" @click="showHistory = false">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div ref="historyPanelRef" class="status-history-list">
            <div v-if="history.length === 0" class="status-history-empty">暂无状态消息</div>
            <div
              v-for="(entry, i) in history"
              :key="i"
              class="status-history-item"
            >
              <span class="status-history-time">{{ entry.time }}</span>
              <span class="status-history-text">{{ entry.text }}</span>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.status-ticker {
  position: relative;
}

/* ---- Latest message box ---- */
.ticker-box {
  border: 1px solid rgba(var(--border-rgb), 0.2);
  border-radius: 8px;
  padding: 4px 12px;
  max-width: 260px;
  min-width: 120px;
  cursor: pointer;
  background: rgba(var(--border-rgb), 0.04);
  transition: background 0.2s, border-color 0.2s;
  overflow: hidden;
  height: 32px;
  display: flex;
  align-items: center;
}
.ticker-box:hover {
  background: rgba(var(--border-rgb), 0.08);
  border-color: rgba(var(--border-rgb), 0.35);
}

.ticker-inner {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  animation: ticker-enter 0.25s ease-out;
}

@keyframes ticker-enter {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.ticker-exit .ticker-inner {
  animation: ticker-exit 0.2s ease-in forwards;
}

@keyframes ticker-exit {
  from {
    opacity: 1;
    transform: translateY(0);
  }
  to {
    opacity: 0;
    transform: translateY(-12px);
  }
}

.ticker-text {
  font-size: 12px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.ticker-time {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

/* ---- History popup ---- */
.status-history-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.3);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-history-panel {
  background: var(--bg-surface);
  border: 1px solid rgba(var(--border-rgb), 0.25);
  border-radius: 14px;
  width: 420px;
  max-width: 90vw;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-popup);
  animation: panel-in 0.2s ease-out;
}

@keyframes panel-in {
  from { opacity: 0; transform: scale(0.95) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.status-history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(var(--border-rgb), 0.1);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.status-history-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: rgba(var(--border-rgb), 0.06);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.status-history-close:hover {
  background: rgba(var(--border-rgb), 0.12);
  color: var(--text-primary);
}

.status-history-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 18px;
}

.status-history-empty {
  text-align: center;
  color: var(--text-muted);
  padding: 40px 0;
  font-size: 13px;
}

.status-history-item {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(var(--border-rgb), 0.06);
  font-size: 12px;
  line-height: 1.5;
}

.status-history-time {
  color: var(--text-muted);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.status-history-text {
  color: var(--text-primary);
  word-break: break-all;
}
</style>
