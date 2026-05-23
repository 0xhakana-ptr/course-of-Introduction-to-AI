<script setup lang="ts">
// Pixel loading animation — Tokyo Night aesthetic
// No props needed; just shows while mounted
</script>

<template>
  <div class="pixel-loading">
    <div class="pixel-row">
      <span class="pixel-dot" style="--i:0; --color:#bb9af7"></span>
      <span class="pixel-dot" style="--i:1; --color:#7aa2f7"></span>
      <span class="pixel-dot" style="--i:2; --color:#7dcfff"></span>
      <span class="pixel-dot" style="--i:3; --color:#9ece6a"></span>
    </div>
    <span class="pixel-label">thinking...</span>
  </div>
</template>

<style scoped>
.pixel-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  margin: 4px 0;
  user-select: none;
}

.pixel-row {
  display: flex;
  gap: 5px;
  align-items: flex-end;
}

.pixel-dot {
  display: block;
  width: 6px;
  height: 6px;
  background: var(--color);
  image-rendering: pixelated;
  animation: pixel-bounce 1.2s ease-in-out infinite;
  animation-delay: calc(var(--i) * 0.15s);
}

@keyframes pixel-bounce {
  0%, 100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  40% {
    transform: translateY(-8px);
    opacity: 1;
  }
  60% {
    transform: translateY(0);
    opacity: 0.7;
  }
}

.pixel-label {
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'Courier New', monospace;
  letter-spacing: 0.05em;
  animation: label-flicker 2s ease-in-out infinite;
}

@keyframes label-flicker {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 0.85; }
}
</style>
