<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getIpcRenderer } from '../platform/electronIpc'

const ipcRenderer = getIpcRenderer()

const workspacePath = ref('')
const isEditing = ref(false)
const editValue = ref('')

defineEmits<{
  updateWorkspace: [path: string]
}>()

async function loadWorkspace() {
  if (!ipcRenderer?.invoke) {
    workspacePath.value = 'D:\\workspace'
    return
  }
  try {
    const result = await ipcRenderer.invoke('chat:getWorkspace')
    if (result?.ok && result.path) {
      workspacePath.value = result.path
    }
  } catch {
    workspacePath.value = 'D:\\workspace'
  }
}

function startEdit() {
  editValue.value = workspacePath.value
  isEditing.value = true
}

function confirmEdit() {
  const p = editValue.value.trim()
  if (p) {
    workspacePath.value = p
    if (ipcRenderer?.send) {
      ipcRenderer.send('chat:setWorkspace', { path: p })
    }
  }
  isEditing.value = false
}

function cancelEdit() {
  isEditing.value = false
}

onMounted(() => loadWorkspace())
</script>

<template>
  <div class="workspace-bar">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" class="ws-icon">
      <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
    </svg>

    <template v-if="!isEditing">
      <span class="ws-path" @dblclick="startEdit" :title="workspacePath">
        {{ workspacePath.split('\\').pop() || workspacePath }}
      </span>
      <button class="ws-edit-btn" @click="startEdit" title="更改工作区">
        <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
      </button>
    </template>

    <template v-else>
      <input
        ref="wsInput"
        v-model="editValue"
        class="ws-input"
        @keydown.enter="confirmEdit"
        @keydown.escape="cancelEdit"
        @blur="confirmEdit"
      />
    </template>
  </div>
</template>

<style scoped>
.workspace-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.06);
}

.ws-icon {
  color: rgba(255,255,255,0.4);
  flex-shrink: 0;
}

.ws-path {
  font-size: 11px;
  color: rgba(255,255,255,0.55);
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 120px;
}
.ws-path:hover {
  color: rgba(255,255,255,0.8);
}

.ws-edit-btn {
  background: none;
  border: none;
  color: rgba(255,255,255,0.3);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
}
.ws-edit-btn:hover {
  color: rgba(255,255,255,0.7);
}

.ws-input {
  background: rgba(0,0,0,0.3);
  border: 1px solid rgba(100,180,255,0.3);
  color: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  width: 150px;
  outline: none;
}
</style>
