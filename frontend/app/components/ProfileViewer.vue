<template>
  <div class="pv-root">

    <!-- Identity header -->
    <div class="pv-identity">
      <input v-model="local.character" class="pv-name" placeholder="角色名" />
      <input v-model="local.series" class="pv-series" placeholder="作品名" />
    </div>

    <!-- 作品 section -->
    <div v-if="local.worldSetting" class="pv-section">
      <div class="pv-section-head" @click="openDialog('world')">
        <span class="pv-section-title">作品</span>
        <div class="pv-summary-chips">
          <span v-if="local.worldSetting.genre" class="pv-chip">{{ local.worldSetting.genre }}</span>
          <span v-if="local.worldSetting.era" class="pv-chip">{{ local.worldSetting.era }}</span>
          <span v-for="t in (local.worldSetting.themes || []).slice(0, 2)" :key="t" class="pv-chip accent">{{ t }}</span>
        </div>
        <span class="pv-expand-icon">›</span>
      </div>
      <p v-if="local.worldSetting.synopsis" class="pv-synopsis">{{ local.worldSetting.synopsis }}</p>
    </div>

    <div class="pv-divider" />

    <!-- 角色 section -->
    <div v-if="local.characterBackground" class="pv-section">
      <div class="pv-section-head" @click="openDialog('char')">
        <span class="pv-section-title">角色</span>
        <div class="pv-summary-chips">
          <span v-if="local.characterBackground.role" class="pv-chip accent">{{ local.characterBackground.role }}</span>
          <span v-if="local.characterBackground.age" class="pv-chip">{{ local.characterBackground.age }}</span>
          <span v-if="local.characterBackground.personality?.surface" class="pv-chip dim">{{ local.characterBackground.personality.surface }}</span>
        </div>
        <span class="pv-expand-icon">›</span>
      </div>
      <div v-if="(local.characterBackground.relations || []).length" class="pv-relations-summary">
        <span v-for="r in local.characterBackground.relations" :key="r.name" class="pv-rel-chip">
          <span class="rel-name">{{ r.name }}</span>
          <span class="rel-type">{{ r.relationship }}</span>
        </span>
      </div>
    </div>

    <!-- Detail dialog -->
    <Teleport to="body">
      <Transition name="dlg">
        <div v-if="dialog" class="pv-backdrop" @click.self="closeDialog">
          <div class="pv-dialog" @keydown.esc="closeDialog">
            <div class="pv-dialog-head">
              <span class="pv-dialog-title">{{ dialog === 'world' ? '作品设定' : '角色设定' }}</span>
              <button class="pv-dialog-close" @click="closeDialog">✕</button>
            </div>
            <div class="pv-dialog-body">
              <DynamicBlock
                v-for="(val, key) in dialogData"
                :key="key"
                :label="label(String(key))"
                :value="val"
                @update="v => updateDialogField(String(key), v)"
              />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick } from 'vue'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: Record<string, any>): void }>()

const local = ref<Record<string, any>>(JSON.parse(JSON.stringify(props.modelValue)))

let _fromProp = false

watch(() => props.modelValue, v => {
  _fromProp = true
  local.value = JSON.parse(JSON.stringify(v))
  nextTick(() => { _fromProp = false })
}, { deep: true })

watch(local, v => {
  if (!_fromProp) emit('update:modelValue', v)
}, { deep: true })

// Dialog
const dialog = ref<'world' | 'char' | null>(null)
function openDialog(k: 'world' | 'char') { dialog.value = k }
function closeDialog() { dialog.value = null }

const WORLD_SUMMARY_KEYS = new Set(['genre', 'era', 'themes', 'synopsis'])
const CHAR_SUMMARY_KEYS  = new Set(['role', 'age', 'relations'])

const dialogData = computed(() => {
  if (dialog.value === 'world') {
    const ws = local.value.worldSetting || {}
    return Object.fromEntries(Object.entries(ws).filter(([k]) => !WORLD_SUMMARY_KEYS.has(k)))
  }
  if (dialog.value === 'char') {
    const cb = local.value.characterBackground || {}
    return Object.fromEntries(Object.entries(cb).filter(([k]) => !CHAR_SUMMARY_KEYS.has(k)))
  }
  return {}
})

function updateDialogField(key: string, val: any) {
  const section = dialog.value === 'world' ? 'worldSetting' : 'characterBackground'
  local.value = {
    ...local.value,
    [section]: { ...local.value[section], [key]: val },
  }
}

const LABELS: Record<string, string> = {
  genre: '类型', era: '时代', timeline: '时间线', synopsis: '作品简介',
  themes: '主题', iconic_settings: '标志场景', tone: '风格基调',
  visual: '视觉', narrative: '叙事', emotion: '情感',
  role: '定位', age: '年龄', backstory: '身世',
  personality: '性格', surface: '外在', inner: '内心',
  strength: '优点', weakness: '弱点', core_desire: '渴望', fear: '恐惧',
  emotional_range: '情绪范围', baseline: '日常', stress: '压力',
  breaking_point: '崩溃点', recovery: '复原',
  behavior: '行为模式', speech_style: '说话风格',
  tone_speech: '语气', volume: '音量', humor: '幽默', vocabulary: '用词',
  habits: '习惯', values: '价值观', likes: '喜好', dislikes: '厌恶',
  key_events: '关键事件', iconic_moments: '代表场景', relations: '关系',
  name: '姓名', relationship: '关系', importance: '重要性',
}
function label(key: string) { return LABELS[key] || key }
</script>

<style scoped>
.pv-root { display: flex; flex-direction: column; gap: 16px; overflow-y: auto; padding: 4px 2px; height: 100%; scrollbar-width: none; }
.pv-root::-webkit-scrollbar { display: none; }

.pv-identity { display: flex; flex-direction: column; gap: 6px; flex-shrink: 0; }
.pv-name {
  background: none; border: none; border-bottom: 1px solid var(--border-md);
  color: var(--text); font-size: 22px; font-weight: 700; outline: none; padding: 4px 0; width: 100%;
  transition: border-color 0.2s;
}
.pv-name:focus { border-bottom-color: var(--accent); }
.pv-series {
  background: none; border: none; color: var(--text-dim); font-size: 13px; outline: none;
  padding: 2px 0; border-bottom: 1px solid transparent; width: 100%;
  transition: border-color 0.2s, color 0.2s;
}
.pv-series:focus { border-bottom-color: var(--border-focus); color: var(--text-neutral); }

.pv-section { display: flex; flex-direction: column; gap: 8px; }
.pv-section-head {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
  padding: 6px 0; user-select: none; border-radius: 6px;
  transition: background 0.15s;
}
.pv-section-head:hover { background: rgba(124,106,247,0.06); }
.pv-section-title { font-size: 11px; font-weight: 700; color: var(--text-sub); text-transform: uppercase; letter-spacing: 0.8px; flex-shrink: 0; }
.pv-summary-chips { display: flex; flex-wrap: wrap; gap: 4px; flex: 1; }
.pv-expand-icon { font-size: 14px; color: var(--border-focus); flex-shrink: 0; transition: color 0.15s; }
.pv-section-head:hover .pv-expand-icon { color: var(--accent); }

.pv-chip {
  padding: 2px 8px; background: var(--surface-raised); border: 1px solid var(--border-focus);
  border-radius: 4px; font-size: 10px; color: var(--text-muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 160px;
}
.pv-chip.accent { border-color: var(--accent-dim); color: var(--accent-hover); }
.pv-chip.dim { color: var(--text-sub); border-color: var(--border-md); }

.pv-synopsis { font-size: 12px; color: var(--text-muted); line-height: 1.7; margin: 0; }

.pv-relations-summary { display: flex; flex-wrap: wrap; gap: 6px; }
.pv-rel-chip {
  display: flex; align-items: center; gap: 4px;
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 6px; padding: 3px 8px;
}
.rel-name { font-size: 11px; color: var(--text-hi); font-weight: 600; }
.rel-type { font-size: 10px; color: var(--text-sub); }

.pv-divider { height: 1px; background: var(--border); flex-shrink: 0; }

/* ── Dialog ── */
.pv-backdrop {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0, 0, 0, 0.6);
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
}

.pv-dialog {
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 14px;
  width: 480px; max-width: 90vw; max-height: 80vh;
  display: flex; flex-direction: column;
  box-shadow: 0 24px 60px rgba(0,0,0,0.6);
}

.pv-dialog-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.pv-dialog-title { font-size: 14px; font-weight: 700; color: var(--text); }
.pv-dialog-close {
  background: none; border: none; color: var(--text-sub); font-size: 14px;
  cursor: pointer; padding: 2px 6px; border-radius: 4px; transition: color 0.15s;
}
.pv-dialog-close:hover { color: var(--text); }

.pv-dialog-body {
  flex: 1; overflow-y: auto; padding: 20px;
  display: flex; flex-direction: column; gap: 14px;
  scrollbar-width: none;
}
.pv-dialog-body::-webkit-scrollbar { display: none; }

/* Dialog enter/leave transitions */
.dlg-enter-active { transition: all 0.2s ease; }
.dlg-leave-active { transition: all 0.15s ease; }
.dlg-enter-from { opacity: 0; }
.dlg-leave-to   { opacity: 0; }
.dlg-enter-from .pv-dialog { transform: scale(0.96) translateY(8px); }
.dlg-leave-to   .pv-dialog { transform: scale(0.96) translateY(8px); }
</style>
