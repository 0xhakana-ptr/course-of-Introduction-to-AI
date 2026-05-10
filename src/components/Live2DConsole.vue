<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getIpcRenderer } from '../platform/electronIpc'

type ConsoleLine = { kind: 'in' | 'out' | 'err'; text: string }
type CommandResponse = { ok: boolean; output: string }

// AI Agent 消息类型定义
type QuipMessage = {
  type: 'quip'
  content: string
  node_name: string
  timestamp: string
  metadata?: {
    priority: 'low' | 'medium' | 'high'
    duration?: number
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

const ipcRenderer = getIpcRenderer()

const lines = ref<ConsoleLine[]>([])
const input = ref('help')
const canInvoke = computed(() => Boolean(ipcRenderer?.invoke))

// Quip 和表情状态
const currentQuip = ref('')
const currentExpression = ref('neutral')

function push(kind: ConsoleLine['kind'], text: string) {
  lines.value.push({ kind, text })
  // Keep last ~300 lines
  if (lines.value.length > 300) lines.value.splice(0, lines.value.length - 300)
}

// 处理 Quip 消息
function handleQuip(_event: any, data: QuipMessage) {
  currentQuip.value = data.content
  push('out', `[Quip] ${data.content} (from node: ${data.node_name})`)
  
  // 根据元数据设置显示时长
  const duration = data.metadata?.duration || 3000
  setTimeout(() => {
    currentQuip.value = ''
  }, duration)
}

// 处理表情消息
function handleExpression(_event: any, data: ExpressionMessage) {
  currentExpression.value = data.expression
  push('out', `[Expression] ${data.expression} (intensity: ${data.intensity})`)  
  // 实际切换 Live2D 表情
  if (ipcRenderer?.invoke) {
    ipcRenderer.invoke('live2d:command', `expr ${data.expression}`).then((res: unknown) => {
      const commandResult = res as CommandResponse | null
      if (commandResult?.ok) {
        push('out', `已切换到表情: ${data.expression}`)
      } else {
        push('err', `切换表情失败: ${commandResult?.output || '未知错误'}`)
      }
    }).catch((e) => {
      push('err', `切换表情异常: ${String(e)}`)
    })
  } else {
    push('err', 'IPC 不可用，无法切换表情')
  }
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
  
  // 监听 Quip 和表情消息
  if (ipcRenderer?.on) {
    ipcRenderer.on('agent:quip', handleQuip)
    ipcRenderer.on('agent:expression', handleExpression)
  } else {
    push('err', 'IPC 不可用，无法接收 AI Agent 消息')
  }
})

onUnmounted(() => {
  if (ipcRenderer?.removeListener) {
    ipcRenderer.removeListener('agent:quip', handleQuip)
    ipcRenderer.removeListener('agent:expression', handleExpression)
  }
})
</script>

<template>
  <div class="console-root">
    <div class="header">
      <div class="title">Live2D 控制台</div>
      <div class="hint" v-if="!canInvoke">（仅 Electron 可用）</div>
    </div>

    <!-- 显示当前 Quip -->
    <div v-if="currentQuip" class="quip-display">
      {{ currentQuip }}
    </div>

    <!-- 显示当前表情 -->
    <div v-if="currentExpression !== 'neutral'" class="expression-display">
      当前表情: {{ currentExpression }}
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

.quip-display {
  padding: 8px 12px;
  background: rgba(183, 215, 255, 0.1);
  border: 1px solid rgba(183, 215, 255, 0.3);
  border-radius: 8px;
  color: #b7d7ff;
  font-size: 14px;
  margin-bottom: 8px;
  text-align: center;
}

.expression-display {
  padding: 6px 12px;
  background: rgba(255, 180, 180, 0.1);
  border: 1px solid rgba(255, 180, 180, 0.3);
  border-radius: 8px;
  color: #ffb4b4;
  font-size: 12px;
  margin-bottom: 8px;
  text-align: center;
}
</style>
