<script setup lang="ts">
import type { ChatLine } from '../composables/useAgentMessages'

defineProps<{
  lines: ChatLine[]
  shouldRenderRichMessage: (line: ChatLine) => boolean
  renderAssistantText: (text: string) => string
  hasCodeBlocks: (text: string) => boolean
  copyLastCodeBlock: (text: string) => Promise<void>
  copyMessage: (text: string) => void
}>()
</script>

<template>
  <div v-for="(l, i) in lines" :key="i" class="msg-row" :class="l.role">
    <!-- Assistant with rich text -->
    <div v-if="shouldRenderRichMessage(l)" class="msg-bubble assistant">
      <button class="msg-copy-btn" @click="copyMessage(l.text)" title="复制">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      </button>
      <div class="msg-content rich" v-html="renderAssistantText(l.text)" />
      <div class="msg-copy-row" v-if="hasCodeBlocks(l.text)">
        <button class="copy-code-btn" @click="copyLastCodeBlock(l.text)">复制代码</button>
      </div>
    </div>
    <!-- File action card -->
    <div v-else-if="l.fileAction" class="msg-bubble assistant">
      <div class="file-action-card" :class="l.fileAction.status">
        <div class="file-action-head">
          <span class="file-action-title">{{ l.fileAction.title }}</span>
          <span class="file-action-badge">{{ l.fileAction.status }}</span>
        </div>
        <button class="msg-copy-btn" @click="copyMessage(l.fileAction.title + ' - ' + l.fileAction.status)" title="复制">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        </button>
        <div class="file-action-boxes">
          <div class="fa-box" v-if="l.fileAction.actionName">
            <span class="fa-box-label">动作</span>
            <code class="fa-box-value">{{ l.fileAction.actionName }}</code>
          </div>
          <div class="fa-box" v-if="l.fileAction.tool">
            <span class="fa-box-label">工具</span>
            <code class="fa-box-value">{{ l.fileAction.tool }}</code>
          </div>
          <div class="fa-box fa-box-error" v-if="l.fileAction.error">
            <span class="fa-box-label">错误</span>
            <code class="fa-box-value">{{ l.fileAction.error }}</code>
          </div>
        </div>
        <div class="file-action-meta" v-if="l.fileAction.source || l.fileAction.target || l.fileAction.query || typeof l.fileAction.matchCount === 'number'">
          <span v-if="l.fileAction.source">来源: {{ l.fileAction.source }}</span>
          <span v-if="l.fileAction.target">目标: {{ l.fileAction.target }}</span>
          <span v-if="l.fileAction.query">查询: {{ l.fileAction.query }}</span>
          <span v-if="typeof l.fileAction.matchCount === 'number'">命中: {{ l.fileAction.matchCount }}</span>
        </div>
      </div>
    </div>
    <!-- User message -->
    <div v-else-if="l.role === 'user'" class="msg-bubble user">
      <div class="msg-content">{{ l.text }}</div>
      <button class="msg-copy-btn" @click="copyMessage(l.text)" title="复制">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      </button>
    </div>
    <!-- System / error -->
    <div v-else class="msg-bubble system">
      <div class="msg-content">{{ l.text }}</div>
      <button class="msg-copy-btn" @click="copyMessage(l.text)" title="复制">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      </button>
    </div>
  </div>
  <slot name="after-messages" />
</template>

<style scoped>
.msg-row {
  display: flex;
  animation: fadeInUp 0.28s ease-out;
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

.msg-row.user {
  justify-content: flex-end;
}
.msg-row.assistant {
  justify-content: flex-start;
}
.msg-row.system, .msg-row.err {
  justify-content: center;
}

/* ---- Message Bubbles ---- */
.msg-bubble {
  max-width: 85%;
  border-radius: 14px;
  padding: 12px 16px;
  padding-right: 36px;
  word-break: break-word;
  overflow-wrap: anywhere;
  position: relative;
}

.msg-bubble.user {
  background: rgba(var(--accent-indigo-rgb), 0.1);
  border: 1px solid rgba(var(--accent-indigo-rgb), 0.16);
  color: var(--text-primary);
  border-bottom-right-radius: 4px;
}

.msg-bubble.assistant {
  background: rgba(var(--accent-sakura-rgb), 0.2);
  border: 1px solid rgba(var(--accent-sakura-rgb), 0.25);
  border-radius: 14px;
  padding: 10px 14px;
  border-bottom-left-radius: 4px;
}

.msg-bubble.system {
  background: rgba(var(--border-rgb), 0.06);
  color: var(--text-muted);
  font-size: 12px;
  padding: 6px 14px;
  border-radius: 8px;
}

.msg-row.err .msg-bubble {
  background: rgba(var(--accent-error-rgb), 0.1);
  border: 1px solid rgba(var(--accent-error-rgb), 0.2);
  color: var(--accent-error-text);
  font-size: 12.5px;
  border-radius: 8px;
}

.msg-content {
  white-space: pre-wrap;
}

.msg-content.rich {
  white-space: normal;
}

/* ---- Rich Markdown ---- */
.msg-content.rich :deep(p) {
  margin: 0 0 0.8em;
}
.msg-content.rich :deep(p:last-child) {
  margin-bottom: 0;
}
.msg-content.rich :deep(ul),
.msg-content.rich :deep(ol) {
  margin: 0.5em 0 0.8em;
  padding-left: 1.6em;
}
.msg-content.rich :deep(li + li) {
  margin-top: 0.3em;
}
.msg-content.rich :deep(code) {
  padding: 0.15em 0.4em;
  border-radius: 5px;
  background: rgba(var(--border-rgb), 0.08);
  color: var(--text-secondary);
  font-size: 0.9em;
  font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', ui-monospace, monospace;
}

/* ---- Code Blocks ---- */
.msg-content.rich :deep(pre) {
  overflow-x: auto;
  margin: 0.65em 0 0.85em;
  padding: 14px 16px;
  border-radius: 10px;
  background: var(--bg-code);
  border: 1px solid rgba(var(--border-rgb), 0.12);
  position: relative;
}
.msg-content.rich :deep(pre code) {
  padding: 0;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.88em;
  line-height: 1.6;
}

/* ---- Blockquote ---- */
.msg-content.rich :deep(blockquote) {
  margin: 0.6em 0;
  padding-left: 1em;
  border-left: 3px solid rgba(var(--border-rgb), 0.3);
  color: var(--text-primary);
}

.msg-content.rich :deep(a) {
  color: var(--accent-link);
}

.msg-content.rich :deep(.katex-display) {
  overflow-x: auto;
  margin: 0.7em 0;
  padding: 0.25em 0;
}

/* ---- Code Copy Button ---- */
.msg-copy-row {
  margin-top: 6px;
  display: flex;
  justify-content: flex-end;
}

.copy-code-btn {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid rgba(var(--border-rgb), 0.12);
  background: rgba(var(--border-rgb), 0.06);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
}
.copy-code-btn:hover {
  background: rgba(var(--border-rgb), 0.1);
  color: var(--text-primary);
}

/* ---- File Action Card ---- */
.file-action-card {
  padding: 12px 14px;
  border: 1px solid rgba(var(--border-rgb), 0.15);
  border-radius: 10px;
  background: rgba(var(--border-rgb), 0.05);
  color: var(--text-primary);
}
.file-action-card.failed {
  border-color: rgba(var(--accent-error-rgb), 0.25);
  background: rgba(var(--accent-error-rgb), 0.06);
}
.file-action-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.file-action-title {
  font-weight: 700;
}
.file-action-badge {
  padding: 2px 8px;
  border-radius: 99px;
  background: rgba(var(--border-rgb), 0.12);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.file-action-boxes {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.fa-box {
  flex: 1;
  min-width: 130px;
  max-width: 280px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(var(--border-rgb), 0.06);
  border: 1px solid rgba(var(--border-rgb), 0.1);
  overflow: hidden;
}
.fa-box-error {
  background: rgba(var(--accent-error-rgb), 0.08);
  border-color: rgba(var(--accent-error-rgb), 0.18);
}
.fa-box-label {
  display: block;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}
.fa-box-value {
  display: block;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fa-box-error .fa-box-value {
  color: var(--accent-error-text);
}
.file-action-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 10.5px;
  color: var(--text-muted);
}
.file-action-meta span {
  white-space: nowrap;
}
.file-action-error code { color: var(--accent-sakura-text); }

/* ---- Copy Button ---- */
.msg-copy-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: rgba(var(--border-rgb), 0.06);
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s, background 0.15s;
  z-index: 2;
}
.msg-bubble:hover .msg-copy-btn,
.msg-copy-btn:focus-visible {
  opacity: 1;
}
.msg-copy-btn:hover {
  background: rgba(var(--border-rgb), 0.12);
  color: var(--text-primary);
}
.msg-copy-btn:active {
  transform: scale(0.9);
}
</style>
