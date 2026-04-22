<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getIpcRenderer } from '../platform/electronIpc'

type ConsoleLine = { kind: 'in' | 'out' | 'err'; text: string }

type CommandResponse = { ok: boolean; output: string }

const ipcRenderer = getIpcRenderer()

const lines = ref<ConsoleLine[]>([])
const input = ref('help')
const canInvoke = computed(() => Boolean(ipcRenderer?.invoke))

function push(kind: ConsoleLine['kind'], text: string) {
  lines.value.push({ kind, text })
  // Keep last ~300 lines
  if (lines.value.length > 300) lines.value.splice(0, lines.value.length - 300)
}

async function runCommand(cmd: string) {
  const trimmed = cmd.trim()
  if (!trimmed) return

  push('in', `> ${trimmed}`)

  if (!ipcRenderer?.invoke) {
    push('err', '当前窗口没有可用的 ipcRenderer.invoke（请确认在 Electron 中运行）')
    return
  }

  try {
    const res = (await ipcRenderer.invoke('live2d:command', trimmed)) as CommandResponse
    if (res?.ok) push('out', res.output || '(ok)')
    else push('err', res?.output || '(error)')
  } catch (e) {
    push('err', String(e))
  }
}

function onSubmit() {
  void runCommand(input.value)
  input.value = ''
}

onMounted(() => {
  push('out', 'Live2D 控制台已启动。输入 help 查看命令。')
  if (input.value.trim() === 'help') void runCommand('help')
})
</script>

<template>
  <div class="console-root">
    <div class="header">
      <div class="title">Live2D 控制台</div>
      <div class="hint" v-if="!canInvoke">（仅 Electron 可用）</div>
    </div>

    <div class="output" role="log" aria-live="polite">
      <div v-for="(l, i) in lines" :key="i" class="line" :class="l.kind">
        {{ l.text }}
      </div>
    </div>

    <form class="input" @submit.prevent="onSubmit">
      <input
        v-model="input"
        class="cmd"
        placeholder="输入命令，例如：list motions / motion TapBody 0 / expr Smile"
        autocomplete="off"
        spellcheck="false"
      />
      <button class="btn" type="submit">发送</button>
    </form>
  </div>
</template>

<style scoped>
.console-root {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  padding: 10px;
  gap: 8px;
  background: #111;
  color: #eaeaea;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.header {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.title {
  font-size: 14px;
  font-weight: 700;
}

.hint {
  font-size: 12px;
  opacity: 0.8;
}

.output {
  flex: 1;
  overflow: auto;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 10px;
  background: rgba(255, 255, 255, 0.04);
  white-space: pre-wrap;
}

.line {
  line-height: 1.5;
  font-size: 12px;
}

.line.in {
  color: #b7d7ff;
}

.line.out {
  color: #eaeaea;
}

.line.err {
  color: #ffb4b4;
}

.input {
  display: flex;
  gap: 8px;
}

.cmd {
  flex: 1;
  height: 36px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.35);
  color: inherit;
  padding: 0 10px;
  outline: none;
}

.btn {
  height: 36px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  cursor: pointer;
}
</style>
