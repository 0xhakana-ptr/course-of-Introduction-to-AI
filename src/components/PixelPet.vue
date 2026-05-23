<template>
  <div class="pixel-pet">
    <img
      ref="spriteRef"
      src="/pixelmotion-transparent-1779526610852.png"
      class="pet-sprite"
      alt="pet"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

const spriteRef = ref<HTMLImageElement>()

/*
  Source: 1024x1024, 4x4 grid = 16 frames
  img element CSS: 256x256 (source scaled 1/4)
  Each frame in scaled space: 256/4 = 64px
  Container clips 64x64 window -> shows exactly 1 frame
*/
const COLS = 4
const TOTAL = 16
const FRAME = 40   // frame size in scaled CSS pixels

let idx = 0
let timer: ReturnType<typeof setInterval> | null = null

function tick() {
  const el = spriteRef.value
  if (!el) return
  const col = idx % COLS
  const row = Math.floor(idx / COLS) % COLS
  el.style.objectPosition = `${-col * FRAME}px ${-row * FRAME}px`
  idx = (idx + 1) % TOTAL
}

onMounted(() => { timer = setInterval(tick, 180) })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.pixel-pet {
  width: 40px;
  height: 40px;
  overflow: hidden;
  border-radius: 6px;
  flex-shrink: 0;
}
.pet-sprite {
  width: 160px;
  height: 160px;
  max-width: none;
  object-fit: fill;
  object-position: 0 0;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
}
</style>
