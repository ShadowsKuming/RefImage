<template>
  <NuxtPage />
  <div class="theme-palette" ref="paletteEl">
    <transition name="palette-fade">
      <div v-if="paletteOpen" class="tp-panel">
        <button
          v-for="t in THEMES"
          :key="t.id"
          class="tp-item"
          :class="{ active: theme === t.id }"
          @click="apply(t.id); paletteOpen = false"
          :title="t.label"
        >
          <span class="tp-dot" :style="{ background: t.accent }"></span>
          <span class="tp-name">{{ t.label }}</span>
        </button>
      </div>
    </transition>
    <button class="tp-trigger" @click="paletteOpen = !paletteOpen" title="切换主题">
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <circle cx="7.5" cy="7.5" r="6.5" stroke="currentColor" stroke-width="1.4"/>
        <circle cx="7.5" cy="3" r="1.5" fill="currentColor"/>
        <circle cx="12" cy="10.5" r="1.5" fill="currentColor"/>
        <circle cx="3" cy="10.5" r="1.5" fill="currentColor"/>
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
const { theme, THEMES, init, apply } = useTheme()

const paletteOpen = ref(false)
const paletteEl   = ref<HTMLElement | null>(null)

function onDocClick(e: MouseEvent) {
  if (paletteEl.value && !paletteEl.value.contains(e.target as Node)) {
    paletteOpen.value = false
  }
}

onMounted(() => {
  init()
  document.addEventListener('click', onDocClick)
})
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<style>
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';
@import '@vue-flow/controls/dist/style.css';
@import '@vue-flow/minimap/dist/style.css';

/* ── Theme tokens ───────────────────────────────────────── */
:root {
  --bg:            #0d0d1a;
  --surface:       #12121f;
  --surface-inset: #0f0f1e;
  --surface-2:     #1a1a2e;
  --surface-3:     #1a1a28;
  --border:        #1e1e30;
  --border-md:     #2a2a3a;
  --border-strong: #2e2e48;
  --text:          #e0e0f0;
  --text-hi:       #d0d0e8;
  --text-accent:   #c0b8f0;
  --text-2:        #a098d0;
  --text-muted:    #888;
  --text-dim:      #666;
  --text-sub:      #555;
  --text-quiet:    #444;
  --text-ghost:    #333;
  --accent:        #7c6af7;
  --accent-dim:    #5a4aaa;
  --shadow:        rgba(0,0,0,0.35);
  --border-focus:  #3a3a5c;
  --accent-hover:  #9480ff;
  --text-neutral:  #aaa;
  --surface-raised:#1a1a38;
  --warning:       #f0c040;
  --orange:        #f7a94a;
  --error:         #e07070;
  --avatar-bg:         #2a1a5a;
  --avatar-text:       #9a80ff;
  --bubble-user-bg:    #1e1848;
  --bubble-user-bdr:   #2e2868;
  --bubble-user-text:  #c0b8f0;
  --badge-done-bg:     #1a3028;
  --badge-done-text:   #4caf82;
  --badge-partial-bg:  #2d2510;
  --badge-partial-text:#e8a838;
  --badge-pending-bg:  #1a1a2a;
  --badge-pending-text:#555;
}

[data-theme="light"] {
  --bg:            #f0f0f8;
  --surface:       #ffffff;
  --surface-inset: #f4f4fa;
  --surface-2:     #ededf8;
  --surface-3:     #f0f0fc;
  --border:        #dcdcea;
  --border-md:     #ccccdc;
  --border-strong: #bebece;
  --text:          #1a1a2e;
  --text-hi:       #2a2a4a;
  --text-accent:   #4a3a9a;
  --text-2:        #6a5aaa;
  --text-muted:    #7a7a9a;
  --text-dim:      #999;
  --text-sub:      #aaa;
  --text-quiet:    #bbb;
  --text-ghost:    #ccc;
  --accent:        #7c6af7;
  --accent-dim:    #5a4aaa;
  --shadow:        rgba(80,80,120,0.10);
  --border-focus:  #9090b8;
  --accent-hover:  #9480ff;
  --text-neutral:  #9090a8;
  --surface-raised:#e0e0f8;
  --warning:       #a08020;
  --orange:        #b06820;
  --error:         #c04040;
  --avatar-bg:         #e0daf8;
  --avatar-text:       #5a4aaa;
  --bubble-user-bg:    #eae8f8;
  --bubble-user-bdr:   #d4d0f0;
  --bubble-user-text:  #4a3a9a;
  --badge-done-bg:     #e8f5ee;
  --badge-done-text:   #2a7a55;
  --badge-partial-bg:  #fef3e2;
  --badge-partial-text:#a06820;
  --badge-pending-bg:  #f0f0f8;
  --badge-pending-text:#999;
}

/* ── Sakura 樱花 (light) ──────────────────────────────────── */
[data-theme="sakura"] {
  --bg:            #fff5f8;
  --surface:       #ffffff;
  --surface-inset: #fdf0f5;
  --surface-2:     #fce8f0;
  --surface-3:     #fdf2f6;
  --surface-raised:#f8dce8;
  --border:        #f0c8d8;
  --border-md:     #e0b0c4;
  --border-strong: #d090a8;
  --border-focus:  #c06080;
  --text:          #2a0e18;
  --text-hi:       #1a0810;
  --text-accent:   #a03060;
  --text-2:        #c04878;
  --text-muted:    #a07888;
  --text-dim:      #b88898;
  --text-sub:      #c898a8;
  --text-quiet:    #d8a8b8;
  --text-ghost:    #e8c0cc;
  --accent:        #d44880;
  --accent-dim:    #a03060;
  --accent-hover:  #e860a0;
  --shadow:        rgba(160,60,80,0.12);
  --text-neutral:  #b08898;
  --warning:       #c09820;
  --orange:        #c07040;
  --error:         #c83050;
  --avatar-bg:     #fce0ec;
  --avatar-text:   #c04070;
  --bubble-user-bg:    #fce8f0;
  --bubble-user-bdr:   #f0c0d4;
  --bubble-user-text:  #a03060;
  --badge-done-bg:     #e8f8ee;
  --badge-done-text:   #2a7850;
  --badge-partial-bg:  #fdf4e0;
  --badge-partial-text:#a07020;
  --badge-pending-bg:  #f8f0f4;
  --badge-pending-text:#b08898;
}

/* ── Matcha 抹茶 (light) ──────────────────────────────────── */
[data-theme="matcha"] {
  --bg:            #f4f9f5;
  --surface:       #ffffff;
  --surface-inset: #eff7f1;
  --surface-2:     #e8f5ea;
  --surface-3:     #f0faf2;
  --surface-raised:#dff0e2;
  --border:        #c0d8c4;
  --border-md:     #a8c8ac;
  --border-strong: #88a88c;
  --border-focus:  #4a8858;
  --text:          #0e2018;
  --text-hi:       #081408;
  --text-accent:   #2a6040;
  --text-2:        #3a7850;
  --text-muted:    #6a8870;
  --text-dim:      #809888;
  --text-sub:      #98a898;
  --text-quiet:    #b0c0b0;
  --text-ghost:    #c8d8c8;
  --accent:        #2d7a50;
  --accent-dim:    #1e5438;
  --accent-hover:  #3a9862;
  --shadow:        rgba(40,100,60,0.12);
  --text-neutral:  #789880;
  --warning:       #a09010;
  --orange:        #a87020;
  --error:         #c03838;
  --avatar-bg:     #d8f0de;
  --avatar-text:   #2a6040;
  --bubble-user-bg:    #e4f5e8;
  --bubble-user-bdr:   #b8d8be;
  --bubble-user-text:  #246040;
  --badge-done-bg:     #e0f4e8;
  --badge-done-text:   #287848;
  --badge-partial-bg:  #fef8e0;
  --badge-partial-text:#907820;
  --badge-pending-bg:  #eef5ef;
  --badge-pending-text:#7a9880;
}

/* ── Ocean 海洋 (light) ───────────────────────────────────── */
[data-theme="ocean"] {
  --bg:            #f2f7fc;
  --surface:       #ffffff;
  --surface-inset: #edf4fa;
  --surface-2:     #e4f0f8;
  --surface-3:     #eef6fc;
  --surface-raised:#d8eaf8;
  --border:        #b8d4e8;
  --border-md:     #98c0dc;
  --border-strong: #78a8cc;
  --border-focus:  #3a78b8;
  --text:          #08182e;
  --text-hi:       #040e1e;
  --text-accent:   #1850a0;
  --text-2:        #2468c0;
  --text-muted:    #6080a0;
  --text-dim:      #7898b0;
  --text-sub:      #90aac0;
  --text-quiet:    #a8c0d0;
  --text-ghost:    #c0d4e0;
  --accent:        #2060b0;
  --accent-dim:    #144080;
  --accent-hover:  #3880d0;
  --shadow:        rgba(20,60,120,0.12);
  --text-neutral:  #7090a8;
  --warning:       #a08818;
  --orange:        #a86820;
  --error:         #c03038;
  --avatar-bg:     #d4e8f8;
  --avatar-text:   #1858a8;
  --bubble-user-bg:    #e0eef8;
  --bubble-user-bdr:   #b0cce0;
  --bubble-user-text:  #1458a8;
  --badge-done-bg:     #e0f4ee;
  --badge-done-text:   #207858;
  --badge-partial-bg:  #fef8e0;
  --badge-partial-text:#907820;
  --badge-pending-bg:  #edf4f8;
  --badge-pending-text:#7090a8;
}

/* ── Amber 琥珀 (light) ───────────────────────────────────── */
[data-theme="amber"] {
  --bg:            #fdf8f0;
  --surface:       #ffffff;
  --surface-inset: #faf4e8;
  --surface-2:     #f8f0e0;
  --surface-3:     #faf5ea;
  --surface-raised:#f5e8cc;
  --border:        #e8d4b0;
  --border-md:     #d8c098;
  --border-strong: #c8a878;
  --border-focus:  #a07828;
  --text:          #1e1208;
  --text-hi:       #120a00;
  --text-accent:   #884018;
  --text-2:        #a05820;
  --text-muted:    #907860;
  --text-dim:      #a89070;
  --text-sub:      #bca880;
  --text-quiet:    #d0c098;
  --text-ghost:    #e0d0b0;
  --accent:        #b06820;
  --accent-dim:    #804810;
  --accent-hover:  #d08830;
  --shadow:        rgba(100,60,10,0.12);
  --text-neutral:  #a08870;
  --warning:       #b08818;
  --orange:        #c06828;
  --error:         #c03030;
  --avatar-bg:     #f5e4c8;
  --avatar-text:   #904818;
  --bubble-user-bg:    #f8f0de;
  --bubble-user-bdr:   #e0c890;
  --bubble-user-text:  #884018;
  --badge-done-bg:     #e8f4e8;
  --badge-done-text:   #287848;
  --badge-partial-bg:  #fef4e0;
  --badge-partial-text:#986820;
  --badge-pending-bg:  #f8f4ec;
  --badge-pending-text:#a08870;
}

/* ── Cyber 赛博 ──────────────────────────────────────────── */
[data-theme="cyber"] {
  --bg:            #060614;
  --surface:       #0b0b20;
  --surface-inset: #08081a;
  --surface-2:     #11112c;
  --surface-3:     #0f0f28;
  --surface-raised:#181840;
  --border:        #161630;
  --border-md:     #202048;
  --border-strong: #2c2c60;
  --border-focus:  #5050a0;
  --accent:        #a060ff;
  --accent-dim:    #6030c0;
  --accent-hover:  #c090ff;
  --text-accent:   #c090ff;
  --text-2:        #9070e0;
  --avatar-bg:     #180840;
  --avatar-text:   #c090ff;
  --bubble-user-bg:  #100828;
  --bubble-user-bdr: #220c50;
  --bubble-user-text:#c090ff;
  --badge-done-text: #a060ff;
  --badge-done-bg:   #0e0830;
}

/* ── Parchment 书卷 (warm light) ─────────────────────────── */
[data-theme="parchment"] {
  --bg:            #f8f4ec;
  --surface:       #fefaf4;
  --surface-inset: #f4f0e8;
  --surface-2:     #ede8dc;
  --surface-3:     #f0ece4;
  --surface-raised:#e8e2d4;
  --border:        #d8cbb8;
  --border-md:     #c8baa8;
  --border-strong: #b8a898;
  --border-focus:  #a07858;
  --text:          #2a1e0e;
  --text-hi:       #1a1008;
  --text-accent:   #6a4828;
  --text-2:        #8a6040;
  --text-muted:    #9a8060;
  --text-dim:      #b09878;
  --text-sub:      #c0a888;
  --text-quiet:    #d0b898;
  --text-ghost:    #e0c8a8;
  --accent:        #8b6a3e;
  --accent-dim:    #5a4828;
  --accent-hover:  #c09060;
  --shadow:        rgba(80,60,20,0.15);
  --border-focus:  #a07858;
  --text-neutral:  #a89070;
  --surface-raised:#e8e2d4;
  --warning:       #a08020;
  --orange:        #b06820;
  --error:         #c04040;
  --avatar-bg:     #ede0cc;
  --avatar-text:   #6a4828;
  --bubble-user-bg:  #f0e8d4;
  --bubble-user-bdr: #d4c0a0;
  --bubble-user-text:#4a3018;
  --badge-done-bg:   #e8f0e0;
  --badge-done-text: #3a7040;
  --badge-partial-bg: #f8f0e0;
  --badge-partial-text:#a06820;
  --badge-pending-bg: #f0ece4;
  --badge-pending-text:#b09878;
}

/* ── Global reset & base ─────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 13px;
}

.canvas-page { display: flex; flex-direction: column; height: 100vh; }

.toolbar {
  height: 48px;
  background: var(--surface);
  border-bottom: 1px solid var(--border-md);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 16px;
  z-index: 10;
}
.logo         { font-weight: 700; font-size: 15px; color: var(--accent); letter-spacing: 0.5px; }
.project-name { color: var(--text-muted); flex: 1; }
.tb-btn {
  padding: 5px 12px;
  background: var(--border-md);
  border: 1px solid var(--border-focus);
  border-radius: 6px;
  color: var(--text-hi);
  cursor: pointer;
  font-size: 12px;
}
.tb-btn:hover { background: var(--border-focus); }

.flow-canvas { flex: 1; background: var(--bg); }

.vue-flow__edge-path     { stroke: var(--border-focus); }
.vue-flow__edge.animated .vue-flow__edge-path { stroke: var(--accent); }

.node {
  background: var(--surface-2);
  border: 1px solid var(--border-md);
  border-radius: 10px;
  width: 280px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  transition: border-color 0.2s;
}
.node:hover  { border-color: var(--border-focus); }
.node.loading { border-color: var(--accent); }

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-md);
  cursor: pointer;
  user-select: none;
}
.node-icon   { font-size: 15px; }
.node-title  { font-weight: 600; font-size: 13px; flex: 1; }
.node-status { font-size: 11px; color: var(--text-muted); }
.node-status.done { color: var(--badge-done-text); }
.expand-btn  { font-size: 10px; color: var(--text-dim); }
.node-body   { padding: 12px 14px; }

.text-input {
  width: 100%;
  padding: 7px 10px;
  background: var(--bg);
  border: 1px solid var(--border-md);
  border-radius: 6px;
  color: var(--text);
  font-size: 13px;
  margin-bottom: 8px;
  outline: none;
}
.text-input:focus { border-color: var(--accent); }

.upload-btn {
  display: block;
  width: 100%;
  padding: 7px 10px;
  background: var(--bg);
  border: 1px solid var(--border-md);
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  margin-bottom: 8px;
  text-align: center;
  transition: border-color 0.2s;
}
.upload-btn:hover { border-color: var(--accent); color: var(--text); }

.action-btn {
  width: 100%;
  padding: 8px;
  background: var(--accent);
  border: none;
  border-radius: 6px;
  color: white;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
}
.action-btn:hover    { background: var(--accent-hover); }
.action-btn:disabled { background: var(--border-focus); color: var(--text-dim); cursor: not-allowed; }
.action-btn.small    { padding: 5px 8px; font-size: 11px; width: auto; }

.reset-btn {
  margin-top: 8px;
  padding: 4px 10px;
  background: transparent;
  border: 1px solid var(--border-md);
  border-radius: 5px;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
}
.reset-btn:hover { border-color: var(--text-dim); color: var(--text-hi); }

.character-name  { font-size: 15px; font-weight: 700; margin-bottom: 2px; }
.character-series { font-size: 11px; color: var(--text-muted); margin-bottom: 8px; }
.signature-tags  { display: flex; flex-wrap: wrap; gap: 4px; }
.tag {
  padding: 2px 7px;
  background: var(--surface-raised);
  border: 1px solid var(--border-focus);
  border-radius: 4px;
  font-size: 10px;
  color: var(--text-neutral);
}

.scenes-list { display: flex; flex-direction: column; gap: 4px; }
.scene-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: var(--bg);
  border: 1px solid var(--border-md);
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.scene-item:hover  { border-color: var(--border-focus); }
.scene-item.active { border-color: var(--accent); background: var(--surface-raised); }
.scene-icon  { font-size: 16px; }
.scene-title { font-size: 12px; font-weight: 600; }
.scene-mood  { font-size: 10px; color: var(--text-muted); }

.image-preview img { width: 100%; border-radius: 6px; margin-bottom: 8px; display: block; }
.slider-group { margin-bottom: 12px; display: flex; flex-direction: column; gap: 6px; }
.slider-row   { display: flex; align-items: center; gap: 8px; }
.slider-label { font-size: 11px; color: var(--text-muted); width: 72px; flex-shrink: 0; }
.slider       { flex: 1; accent-color: var(--accent); }
.slider-value { font-size: 11px; color: var(--text-dim); width: 24px; text-align: right; }

.guide-node          { width: 260px; }
.guide-node.expanded { width: 300px; }
.guide-sketch { width: 100%; border-radius: 6px; margin-bottom: 8px; display: block; border: 1px solid var(--border-md); }
.guide-desc   { font-size: 11px; color: var(--text-neutral); margin-bottom: 8px; line-height: 1.5; }
.directions-list { display: flex; flex-direction: column; gap: 5px; margin-bottom: 8px; }
.direction-item  { display: flex; gap: 6px; font-size: 11px; color: var(--text-hi); line-height: 1.5; }
.dir-num {
  width: 16px; height: 16px;
  background: var(--accent);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700;
  flex-shrink: 0; margin-top: 1px;
}
.checkpoints   { display: flex; flex-wrap: wrap; gap: 4px; }
.checkpoint    { font-size: 10px; color: var(--badge-done-text); }
.locations-list { display: flex; flex-direction: column; gap: 3px; margin-bottom: 6px; }
.location-item { font-size: 11px; color: var(--text-hi); padding: 3px 0; }
.best-time     { font-size: 10px; color: var(--warning); margin-top: 4px; }
.budget-note   { font-size: 10px; color: var(--warning); margin-top: 6px; }

.empty-state   { text-align: center; color: var(--text-sub); font-size: 11px; padding: 8px 0; }
.loading-state { display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-size: 11px; padding: 4px 0; }
.spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--border-focus);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Theme palette switcher ──────────────────────────────── */
.theme-palette {
  position: fixed;
  top: 50%;
  left: 20px;
  transform: translateY(-50%);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.tp-trigger {
  width: 36px; height: 36px;
  background: var(--surface-2);
  border: 1px solid var(--border-md);
  border-radius: 50%;
  color: var(--text-muted);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 12px var(--shadow);
  transition: border-color 0.2s, color 0.2s;
}
.tp-trigger:hover { border-color: var(--accent); color: var(--accent); }
.tp-panel {
  background: var(--surface);
  border: 1px solid var(--border-md);
  border-radius: 14px;
  padding: 10px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
  box-shadow: 0 8px 32px var(--shadow);
}
.tp-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 8px 6px;
  border-radius: 10px;
  border: 1.5px solid transparent;
  background: transparent;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  min-width: 46px;
}
.tp-item:hover { background: var(--surface-2); }
.tp-item.active { border-color: var(--border-md); background: var(--surface-raised); }
.tp-dot {
  width: 22px; height: 22px;
  border-radius: 50%;
  display: block;
  box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  transition: transform 0.15s;
}
.tp-item:hover .tp-dot { transform: scale(1.12); }
.tp-item.active .tp-dot {
  box-shadow: 0 0 0 2px var(--bg), 0 0 0 3.5px var(--border-md);
}
.tp-name {
  font-size: 10px;
  color: var(--text-dim);
  line-height: 1;
  white-space: nowrap;
}
.tp-item.active .tp-name { color: var(--text); }
.palette-fade-enter-active,
.palette-fade-leave-active { transition: opacity 0.15s, transform 0.15s; }
.palette-fade-enter-from,
.palette-fade-leave-to { opacity: 0; transform: translateY(8px) scale(0.97); }
</style>
