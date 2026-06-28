<template>
  <div class="guide-content">
    <div class="guide-emoji">{{ guide.emoji }}</div>
    <p class="guide-desc">{{ guide.description }}</p>
    <ul class="guide-list">
      <li v-for="(k, i) in guide.keyPoints" :key="i">{{ k }}</li>
    </ul>
    <div class="guide-cue">{{ guide.cue }}</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ guide: any; color: string }>()
</script>

<style scoped>
.guide-content { display: flex; flex-direction: column; gap: 10px; }
.guide-emoji   { font-size: 40px; text-align: center; line-height: 1; }
.guide-desc    { font-size: 11px; color: var(--text-muted); line-height: 1.6; margin: 0; text-align: center; font-weight: 600; }
.guide-list    { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.guide-list li { padding-left: 10px; font-size: 11px; color: var(--text-dim); line-height: 1.5; }
.guide-cue     { font-size: 11px; color: var(--text-muted); font-style: italic; border-left: 2px solid var(--border-md); padding-left: 8px; line-height: 1.6; }
</style>
