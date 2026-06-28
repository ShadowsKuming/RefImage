<template>
  <div class="guide-content">
    <img v-if="sketchUrl" :src="sketchUrl" class="guide-sketch" />
    <p class="guide-desc">{{ guide.description }}</p>
    <ul class="guide-list">
      <li v-for="(d, i) in guide.directions" :key="i">
        <span class="dir-num" :style="{ background: color }">{{ i + 1 }}</span>{{ d }}
      </li>
    </ul>
    <div v-if="guide.checkpoints" class="checkpoints">
      <span v-for="c in guide.checkpoints" :key="c" class="cp-tag">✓ {{ c }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ guide: any; color: string; sketchUrl: string | null }>()
</script>

<style scoped>
.guide-content { display: flex; flex-direction: column; gap: 10px; }
.guide-sketch  { width: 100%; border-radius: 8px; border: 1px solid var(--border-md); display: block; }
.guide-desc    { font-size: 11px; color: var(--text-muted); line-height: 1.6; margin: 0; }
.guide-list    { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.guide-list li { display: flex; gap: 7px; font-size: 11px; color: var(--text-dim); line-height: 1.5; align-items: flex-start; }
.dir-num       { width: 16px; height: 16px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 700; color: white; flex-shrink: 0; margin-top: 1px; }
.checkpoints   { display: flex; flex-wrap: wrap; gap: 5px; }
.cp-tag        { font-size: 10px; color: var(--badge-done-text); background: var(--badge-done-bg); padding: 2px 7px; border-radius: 4px; }
</style>
