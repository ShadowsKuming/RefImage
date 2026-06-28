<template>
  <div class="cf-root">

    <div class="figure-wrap">

      <!-- inline SVG so currentColor is CSS-controllable -->
      <div class="figure-svg" v-html="svgContent" />

      <!-- connector lines -->
      <svg class="overlay-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
        <line v-for="dot in BODY_DOTS" :key="dot.field + '-line'"
          :x1="dot.x" :y1="dot.y" x2="76" :y2="dot.y"
          class="connector"
        />
      </svg>

      <!-- dots — interactive -->
      <div v-for="dot in BODY_DOTS" :key="dot.field + '-dot'"
        class="dot-pin"
        :style="{ top: dot.y + '%', left: dot.x + '%' }"
        :class="[dotClass(dot.field), { 'dot-hoverable': true }]"
        @mouseenter="showTooltip($event, dot.field, dot.label)"
        @mousemove="moveTooltip"
        @mouseleave="hideTooltip"
      >
        <div v-if="extracted[dot.field] != null" class="dot-core" />
      </div>

      <!-- labels -->
      <div v-for="dot in BODY_DOTS" :key="dot.field + '-label'"
        class="label-pin"
        :style="{ top: dot.y + '%' }"
        :class="extracted[dot.field] != null ? 'label-done' : ''"
      >{{ dot.label }}</div>

    </div>

    <!-- 3 extra fields below figure — interactive -->
    <div class="extra-fields">
      <div v-for="f in EXTRA_FIELDS" :key="f.field"
        class="extra-row"
        :class="extracted[f.field] != null ? 'extra-done' : ''"
        @mouseenter="showTooltip($event, f.field, f.label)"
        @mousemove="moveTooltip"
        @mouseleave="hideTooltip"
      >
        <span class="extra-dot" :class="dotClass(f.field)" />
        <span>{{ f.label }}</span>
      </div>
    </div>

    <!-- Tooltip portal -->
    <Teleport to="body">
      <div
        v-if="tooltip.visible"
        class="cf-tooltip"
        :style="{ left: tooltip.x + 'px', top: tooltip.y + 'px' }"
      >
        <div class="tt-label">{{ tooltip.label }}</div>
        <div class="tt-value">{{ tooltip.value || '尚未识别' }}</div>
      </div>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, reactive } from 'vue'

const props = defineProps<{
  extracted: Record<string, string | null>
  gender:    'male' | 'female'
  loading:   boolean
}>()

const BODY_DOTS = [
  { field: 'hairstyle',   label: '发型',    x: 58, y: 10 },
  { field: 'face_makeup', label: '脸型妆容', x: 58, y: 19 },
  { field: 'upper_body',  label: '上身衣服', x: 62, y: 38 },
  { field: 'lower_body',  label: '下身衣服', x: 62, y: 62 },
  { field: 'shoes',       label: '鞋子',    x: 58, y: 91 },
]

const EXTRA_FIELDS = [
  { field: 'proportions',   label: '身材比例'  },
  { field: 'distinctive',   label: '标志性特征' },
  { field: 'color_palette', label: '配色'      },
]

// Tooltip state
const tooltip = reactive({ visible: false, x: 0, y: 0, label: '', value: '' })

function showTooltip(e: MouseEvent, field: string, label: string) {
  tooltip.visible = true
  tooltip.label   = label
  tooltip.value   = props.extracted[field] ?? ''
  tooltip.x       = e.clientX + 14
  tooltip.y       = e.clientY - 10
}

function moveTooltip(e: MouseEvent) {
  tooltip.x = e.clientX + 14
  tooltip.y = e.clientY - 10
}

function hideTooltip() {
  tooltip.visible = false
}

// SVG loading
const svgContent = ref('')

async function loadSvg(gender: 'male' | 'female') {
  const url = gender === 'female' ? '/figure-female.svg' : '/figure-male.svg'
  svgContent.value = await fetch(url).then(r => r.text())
}

onMounted(() => {
  loadSvg(props.gender)
  watch(() => props.gender, loadSvg)
})

function dotClass(field: string) {
  if (props.extracted[field] != null) return 'dot-done'
  if (props.loading) return 'dot-pulse'
  return 'dot-empty'
}
</script>

<style scoped>
.cf-root {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  width: 100%;
}

/* Figure */
.figure-wrap {
  position: relative;
  height: 340px;
  aspect-ratio: 2 / 3;
}
.figure-svg {
  width: 100%;
  height: 100%;
  line-height: 0;
  color: var(--figure-color, #9b8fcc);
}
.figure-svg :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}

/* SVG connector lines */
.overlay-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.connector {
  stroke: var(--border-md);
  stroke-width: 0.5;
  stroke-dasharray: 1.5 1.5;
}

/* Dots */
.dot-pin {
  position: absolute;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
  cursor: pointer;
  pointer-events: auto;
}
.dot-pin:hover { transform: translate(-50%, -50%) scale(1.4); }
.dot-empty { background: var(--surface-2); border: 1px solid var(--border-focus); }
.dot-done  { background: var(--badge-done-bg); border: 1.5px solid var(--badge-done-text); }
.dot-pulse {
  background: var(--surface-2); border: 1px solid var(--border-focus);
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { border-color: var(--border-focus); }
  50%       { border-color: var(--accent-dim); }
}
.dot-core {
  width: 4px; height: 4px;
  border-radius: 50%;
  background: var(--badge-done-text);
  pointer-events: none;
}

/* Labels */
.label-pin {
  position: absolute;
  left: 77%;
  transform: translateY(-50%);
  font-size: 9.5px;
  color: var(--border-focus);
  white-space: nowrap;
  transition: color 0.3s;
  pointer-events: none;
}
.label-done { color: var(--badge-done-text); }

/* Extra 3 fields */
.extra-fields {
  display: flex; gap: 14px; flex-wrap: wrap; justify-content: center;
}
.extra-row {
  display: flex; align-items: center; gap: 5px;
  font-size: 10.5px; color: var(--border-focus); transition: color 0.3s;
  cursor: pointer;
}
.extra-row:hover { color: var(--accent); }
.extra-done { color: var(--badge-done-text); }
.extra-done:hover { color: var(--badge-done-text); }
.extra-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
  transition: all 0.3s;
}
.extra-dot.dot-empty { background: var(--surface-2); border: 1px solid var(--border-focus); }
.extra-dot.dot-done  { background: var(--badge-done-bg); border: 1.5px solid var(--badge-done-text); }
.extra-dot.dot-pulse { background: var(--surface-2); border: 1px solid var(--border-focus); animation: pulse 1.4s ease-in-out infinite; }
</style>

<!-- Tooltip: not scoped so it can break out of the component -->
<style>
.cf-tooltip {
  position: fixed;
  z-index: 9999;
  pointer-events: none;
  max-width: 260px;
  background: var(--surface-2);
  border: 1px solid var(--border-focus);
  border-radius: 8px;
  padding: 10px 13px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
}
.cf-tooltip .tt-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-bottom: 4px;
}
.cf-tooltip .tt-value {
  font-size: 12px;
  color: var(--text-accent);
  line-height: 1.6;
}
</style>
