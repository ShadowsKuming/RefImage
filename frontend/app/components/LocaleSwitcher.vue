<template>
  <div class="locale-switcher" ref="paletteEl">
    <transition name="palette-fade">
      <div v-if="paletteOpen" class="lp-panel">
        <button
          v-for="l in LOCALE_META"
          :key="l.id"
          class="lp-item"
          :class="{ active: locale === l.id }"
          @click="apply(l.id); paletteOpen = false"
        >{{ l.label }}</button>
      </div>
    </transition>
    <button class="lp-trigger" @click="paletteOpen = !paletteOpen" :title="t('common.switchLanguage')">
      <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
        <circle cx="7.5" cy="7.5" r="6.5" stroke="currentColor" stroke-width="1.4"/>
        <path d="M1 7.5H14" stroke="currentColor" stroke-width="1.2"/>
        <path d="M7.5 1C9.5 3 9.5 12 7.5 14C5.5 12 5.5 3 7.5 1Z" stroke="currentColor" stroke-width="1.2"/>
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
const { locale, LOCALE_META, apply, t } = useLocale()

const paletteOpen = ref(false)
const paletteEl   = ref<HTMLElement | null>(null)

function onDocClick(e: MouseEvent) {
  if (paletteEl.value && !paletteEl.value.contains(e.target as Node)) {
    paletteOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<style scoped>
/* Stacked directly above the theme-palette trigger (app.vue) — one settings corner */
.locale-switcher {
  position: fixed;
  top: 50%;
  left: 20px;
  transform: translateY(calc(-50% - 44px));
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.lp-trigger {
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
.lp-trigger:hover { border-color: var(--accent); color: var(--accent); }
.lp-panel {
  background: var(--surface);
  border: 1px solid var(--border-md);
  border-radius: 14px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 96px;
  box-shadow: 0 8px 32px var(--shadow);
}
.lp-item {
  padding: 7px 10px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--text-dim);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.lp-item:hover { background: var(--surface-2); color: var(--text); }
.lp-item.active { background: var(--surface-raised); color: var(--text); font-weight: 600; }
.palette-fade-enter-active,
.palette-fade-leave-active { transition: opacity 0.15s, transform 0.15s; }
.palette-fade-enter-from,
.palette-fade-leave-to { opacity: 0; transform: translateY(8px) scale(0.97); }
</style>
