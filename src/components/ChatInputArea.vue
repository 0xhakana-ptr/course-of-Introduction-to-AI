<script setup lang="ts">
defineProps<{
  modelValue: string
  isSending: boolean
  onKeydown: (e: KeyboardEvent) => void
  onSubmit: () => void
  autoResizeInput: () => void
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="input-area">
    <div class="input-row">
      <textarea
        :value="modelValue"
        :disabled="isSending"
        class="chat-input"
        rows="1"
        placeholder="输入消息... (Enter 发送, Shift+Enter 换行, ↑↓ 历史)"
        @input="(e) => { emit('update:modelValue', (e.target as HTMLTextAreaElement).value); autoResizeInput() }"
        @keydown="onKeydown"
      />
      <button class="send-btn" :disabled="isSending || !modelValue.trim()" @click="onSubmit">
        <svg class="send-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
      </button>
    </div>
    <div class="input-hint">Enter 发送 · Shift+Enter 换行 · Ctrl+L 清屏 · ↑↓ 历史</div>
  </div>
</template>

<style scoped>
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

.chat-input {
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
.chat-input:focus {
  border-color: var(--input-border-focus);
  background: var(--bg-input-focus);
}
.chat-input::placeholder {
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

.send-icon {
  pointer-events: none;
}

.input-hint {
  margin-top: 6px;
  font-size: 10.5px;
  color: var(--input-hint);
  text-align: center;
}
</style>
