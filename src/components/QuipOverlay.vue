<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue"
import { getIpcRenderer } from "../platform/electronIpc"

type AgentQuipMessage = {
  type: "quip"
  content?: string
  node_name?: string
  event_type?: string
  event_source?: string
  event_stage?: string
  metadata?: {
    priority?: "low" | "medium" | "high"
    duration?: number
    node_label?: string
    phase?: string
  }
}

const ipcRenderer = getIpcRenderer()

const quipContent = ref("")
const isVisible = ref(false)
const quipSource = ref<"workflow" | "character">("character")
const quipKey = ref(0)
let dismissTimer: ReturnType<typeof setTimeout> | null = null

// Workflow quip throttle
const WORKFLOW_THROTTLE_MS = 900
let lastWorkflowQuipAt = 0
let pendingWorkflowQuip = ""
let pendingTimer: ReturnType<typeof setTimeout> | null = null

function showQuip(content: string, source: "workflow" | "character", duration: number) {
  // dismiss previous
  if (dismissTimer) {
    clearTimeout(dismissTimer)
    dismissTimer = null
  }

  quipContent.value = content
  quipSource.value = source
  quipKey.value++
  isVisible.value = true

  dismissTimer = setTimeout(() => {
    isVisible.value = false
  }, duration)
}

function handleQuip(_event: any, message: AgentQuipMessage) {
  const content = typeof message?.content === "string" ? message.content.trim() : ""
  if (!content) return

  const isWorkflow =
    message.event_type === "workflow.node_entered" || message.event_source === "workflow"
  const isHighPriority = message.metadata?.priority === "high"
  const duration = message.metadata?.duration || (isHighPriority ? 8000 : 5000)

  if (isWorkflow && !isHighPriority) {
    const now = Date.now()
    const elapsed = now - lastWorkflowQuipAt

    if (elapsed < WORKFLOW_THROTTLE_MS) {
      // buffer last quip; show after throttle window
      pendingWorkflowQuip = content
      if (!pendingTimer) {
        pendingTimer = setTimeout(() => {
          pendingTimer = null
          const q = pendingWorkflowQuip
          pendingWorkflowQuip = ""
          if (q) {
            showQuip(q, "workflow", duration)
            lastWorkflowQuipAt = Date.now()
          }
        }, WORKFLOW_THROTTLE_MS - elapsed)
      }
      return
    }

    lastWorkflowQuipAt = now
    showQuip(content, "workflow", duration)
  } else {
    if (pendingTimer) {
      clearTimeout(pendingTimer)
      pendingTimer = null
      pendingWorkflowQuip = ""
    }
    lastWorkflowQuipAt = Date.now()
    showQuip(content, isWorkflow ? "workflow" : "character", duration)
  }
}

onMounted(() => {
  if (ipcRenderer?.on) {
    ipcRenderer.on("agent:quip", handleQuip)
  }
})

onUnmounted(() => {
  if (ipcRenderer?.removeListener) {
    ipcRenderer.removeListener("agent:quip", handleQuip)
  }
  if (dismissTimer) clearTimeout(dismissTimer)
  if (pendingTimer) clearTimeout(pendingTimer)
})
</script>

<template>
  <Transition name="quip" mode="out-in">
    <div
      v-if="isVisible"
      :key="quipKey"
      class="quip-overlay"
      :class="quipSource"
    >
      <div class="quip-bubble">{{ quipContent }}</div>
    </div>
  </Transition>
</template>

<style scoped>
.quip-overlay {
  position: absolute;
  top: 18%;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1001;
  pointer-events: none;
  max-width: 82%;
}

.quip-bubble {
  padding: 10px 20px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.45;
  text-align: center;
  color: rgba(255, 255, 255, 0.96);
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.55);
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

/* workflow quips: smaller, muted, almost ghost-like */
.quip-overlay.workflow .quip-bubble {
  background: rgba(0, 0, 0, 0.42);
  border: 1px solid rgba(255, 255, 255, 0.07);
  font-size: 12px;
  padding: 6px 16px;
  border-radius: 10px;
}

/* character / roleplay quips: prominent, warm */
.quip-overlay.character .quip-bubble {
  background: rgba(18, 18, 38, 0.62);
  border: 1px solid rgba(183, 215, 255, 0.18);
  font-size: 15px;
}

/* enter / leave transitions */
.quip-enter-active {
  transition: opacity 0.28s ease-out, transform 0.28s ease-out;
}
.quip-leave-active {
  transition: opacity 0.36s ease-in, transform 0.36s ease-in;
}
.quip-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}
.quip-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-6px);
}
</style>
