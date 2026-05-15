<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { getIpcRenderer } from '../platform/electronIpc'

const ipcRenderer = getIpcRenderer()

const isBackendActive = ref(false)
const isFlashing = ref(false)
let flashTimer: ReturnType<typeof setInterval> | null = null
let lastActivity = 0

function startFlashing() {
  isBackendActive.value = true
  lastActivity = Date.now()
  if (!flashTimer) {
    flashTimer = setInterval(() => {
      isFlashing.value = !isFlashing.value
      // Stop flashing if no activity for 10s
      if (Date.now() - lastActivity > 30000) {
        stopFlashing()
      }
    }, 600)
  }
}

function stopFlashing() {
  isBackendActive.value = false
  isFlashing.value = false
  if (flashTimer) {
    clearInterval(flashTimer)
    flashTimer = null
  }
}

function onActivity() {
  lastActivity = Date.now()
  if (!isBackendActive.value) {
    startFlashing()
  }
}

onMounted(() => {
  if (ipcRenderer?.on) {
    // Listen for status updates from backend
    ipcRenderer.on('agent:status', (_event: any, data: any) => {
      const status = data?.status
      if (status === 'running' || status === 'thinking') {
        onActivity()
      } else if (status === 'done' || status === 'error' || status === 'idle') {
        // Keep showing for a bit after completion
        setTimeout(stopFlashing, 2000)
      }
    })
    // Also listen for quips, chat messages, expressions as activity signals
    ipcRenderer.on('agent:quip', () => onActivity())
    ipcRenderer.on('agent:chat', () => onActivity())
    ipcRenderer.on('agent:expression', () => onActivity())
  }
})

onUnmounted(() => {
  stopFlashing()
  if (ipcRenderer?.removeListener) {
    ipcRenderer.removeListener('agent:status', () => {})
    ipcRenderer.removeListener('agent:quip', () => {})
    ipcRenderer.removeListener('agent:chat', () => {})
    ipcRenderer.removeListener('agent:expression', () => {})
  }
})
</script>

<template>
  <span
    class="backend-indicator"
    :class="{ active: isBackendActive, flash: isFlashing }"
    title="后端运行状态"
  />
</template>

<style scoped>
.backend-indicator {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.18);
  transition: background 0.3s;
  flex-shrink: 0;
}

.backend-indicator.active {
  background: rgba(100, 220, 100, 0.5);
}

.backend-indicator.flash {
  background: rgba(100, 255, 100, 0.9);
  box-shadow: 0 0 6px rgba(100, 255, 100, 0.6);
}
</style>
