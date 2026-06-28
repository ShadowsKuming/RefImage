<template>
  <div class="guide-content">

    <!-- Top badges: orientation · shotType · framing -->
    <div class="meta-row">
      <span class="meta-badge">{{ guide.orientation }}</span>
      <span class="meta-sep">·</span>
      <span class="meta-badge">{{ guide.shotType }}</span>
      <span class="meta-sep">·</span>
      <span class="meta-badge framing">{{ guide.framing }}</span>
    </div>

    <!-- Camera -->
    <div class="section">
      <div class="section-label">📷 镜头</div>
      <div class="row">
        <span class="row-key">高度</span>
        <span class="row-val">{{ guide.camera.height }}
          <span class="row-reason">— {{ guide.camera.heightReason }}</span>
        </span>
      </div>
      <div class="row">
        <span class="row-key">倾斜</span>
        <span class="row-val">{{ guide.camera.tilt }}</span>
      </div>
      <div class="row">
        <span class="row-key">焦段感</span>
        <span class="row-val">{{ guide.camera.lensSuggestion }}</span>
      </div>
    </div>

    <!-- Subject -->
    <div class="section">
      <div class="section-label">👤 人物</div>
      <div class="row">
        <span class="row-key">视线</span>
        <span class="row-val">{{ guide.subject.gazeDirection }}</span>
      </div>
      <div class="row">
        <span class="row-key">头部</span>
        <span class="row-val">{{ guide.subject.headDirection }}</span>
      </div>
      <div class="row">
        <span class="row-key">身体</span>
        <span class="row-val">{{ guide.subject.bodyOrientation }}</span>
      </div>
    </div>

    <!-- Composition -->
    <div class="section">
      <div class="section-label">▦ 构图</div>
      <div class="row">
        <span class="row-key">规则</span>
        <span class="row-val">{{ guide.composition.rule }}</span>
      </div>
      <div class="row">
        <span class="row-key">位置</span>
        <span class="row-val">{{ guide.composition.subjectPlacement }}</span>
      </div>
      <div class="row">
        <span class="row-key">视觉流</span>
        <span class="row-val">{{ guide.composition.visualFlow }}</span>
      </div>
    </div>

    <!-- Lighting mood -->
    <div class="lighting-mood">💡 {{ guide.lightingMood }}</div>

    <!-- Key visual factors -->
    <div class="kvf-block">
      <div class="kvf-label" :style="{ color }">✦ 关键视觉因素</div>
      <div class="kvf-tags">
        <span v-for="f in guide.keyVisualFactors" :key="f" class="kvf-tag" :style="{ borderColor: color + '55', color }">
          {{ f }}
        </span>
      </div>
    </div>

    <!-- Execution tips -->
    <ul class="exec-list">
      <li v-for="t in guide.executionTips" :key="t">→ {{ t }}</li>
    </ul>

  </div>
</template>

<script setup lang="ts">
defineProps<{ guide: any; color: string }>()
</script>

<style scoped>
.guide-content  { display: flex; flex-direction: column; gap: 10px; }

.meta-row       { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.meta-badge     { font-size: 10px; font-weight: 600; background: var(--surface-2); color: var(--text-muted); padding: 2px 7px; border-radius: 4px; }
.meta-badge.framing { color: var(--text-dim); font-weight: 400; }
.meta-sep       { font-size: 10px; color: var(--border-strong); }

.section        { display: flex; flex-direction: column; gap: 4px; }
.section-label  { font-size: 10px; font-weight: 700; color: var(--text-sub); letter-spacing: 0.03em; margin-bottom: 2px; }
.row            { display: flex; gap: 6px; align-items: baseline; }
.row-key        { font-size: 10px; color: var(--text-ghost); min-width: 36px; flex-shrink: 0; }
.row-val        { font-size: 11px; color: var(--text-dim); line-height: 1.5; }
.row-reason     { font-size: 10px; color: var(--text-ghost); font-style: italic; }

.lighting-mood  { font-size: 10px; color: var(--text-ghost); font-style: italic; }

.kvf-block      { display: flex; flex-direction: column; gap: 6px; }
.kvf-label      { font-size: 10px; font-weight: 700; letter-spacing: 0.04em; }
.kvf-tags       { display: flex; flex-wrap: wrap; gap: 5px; }
.kvf-tag        { font-size: 10px; border: 1px solid; padding: 2px 7px; border-radius: 4px; }

.exec-list      { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }
.exec-list li   { font-size: 11px; color: var(--text-dim); line-height: 1.5; }
</style>
