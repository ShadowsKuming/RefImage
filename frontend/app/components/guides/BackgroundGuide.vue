<template>
  <div class="guide-content">
    <p class="guide-desc">{{ guide.description }}</p>
    <ul class="guide-list">
      <li v-for="(l, i) in guide.locations" :key="i">{{ l }}</li>
    </ul>
    <div class="best-time">⏰ {{ guide.bestTime }}</div>
    <div v-if="guide.checkpoints" class="checkpoints">
      <span v-for="c in guide.checkpoints" :key="c" class="cp-tag">✓ {{ c }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ guide: any; color: string }>()
</script>

<style scoped>
.guide-content { display: flex; flex-direction: column; gap: 10px; }
.guide-desc    { font-size: 11px; color: var(--text-muted); line-height: 1.6; margin: 0; }
.guide-list    { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.guide-list li { padding-left: 10px; font-size: 11px; color: var(--text-dim); line-height: 1.5; }
.best-time     { font-size: 10px; color: var(--warning); }
.checkpoints   { display: flex; flex-wrap: wrap; gap: 5px; }
.cp-tag        { font-size: 10px; color: var(--badge-done-text); background: var(--badge-done-bg); padding: 2px 7px; border-radius: 4px; }
</style>
