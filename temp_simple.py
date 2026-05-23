comp = r"""<template>
  <div class="pixel-pet">
    <div class="pet-sprite" />
  </div>
</template>

<style scoped>
.pixel-pet {
  width: 48px;
  height: 48px;
  overflow: hidden;
  border-radius: 6px;
  flex-shrink: 0;
}
.pet-sprite {
  width: 100%;
  height: 100%;
  background: url('/pixelmotion-transparent-1779526610852.png') no-repeat;
  background-size: 400% 400%;
  image-rendering: pixelated;
  animation: sprite16 1.2s steps(16) infinite;
}

@keyframes sprite16 {
  0%   { background-position: 0% 0%; }
  6.25%  { background-position: 33.333% 0%; }
  12.5%  { background-position: 66.667% 0%; }
  18.75% { background-position: 100% 0%; }
  25%   { background-position: 0% 33.333%; }
  31.25% { background-position: 33.333% 33.333%; }
  37.5%  { background-position: 66.667% 33.333%; }
  43.75% { background-position: 100% 33.333%; }
  50%   { background-position: 0% 66.667%; }
  56.25% { background-position: 33.333% 66.667%; }
  62.5%  { background-position: 66.667% 66.667%; }
  68.75% { background-position: 100% 66.667%; }
  75%   { background-position: 0% 100%; }
  81.25% { background-position: 33.333% 100%; }
  87.5%  { background-position: 66.667% 100%; }
  93.75% { background-position: 100% 100%; }
  100%  { background-position: 0% 0%; }
}
</style>
"""

with open(r"D:\codeAIAGENT\cyber-waifu-vue\src\components\PixelPet.vue", "w", encoding="utf-8") as f:
    f.write(comp)
print("Simplified!")
