<template>
  <div class="pv-root">

    <!-- Mode toggle -->
    <div class="pv-mode-row">
      <button class="pv-mode-btn" @click="mode = mode === 'browse' ? 'edit' : 'browse'">
        {{ mode === 'browse' ? t('profileViewer.editToggle') : t('profileViewer.browseToggle') }}
      </button>
    </div>

    <!-- Hero -->
    <div class="pv-hero">
      <div class="pv-hero-photo">
        <img v-if="refImageUrl" :src="refImageUrl" class="pv-hero-img" :alt="local.character" />
        <div v-else class="pv-hero-photo-empty">{{ (local.character || '?')[0] }}</div>
      </div>
      <div class="pv-hero-body">
        <template v-if="mode === 'edit'">
          <input v-model="local.character" class="pv-name-input" :placeholder="t('profileViewer.characterNamePlaceholder')" />
          <input v-model="local.series" class="pv-series-input" :placeholder="t('profileViewer.seriesPlaceholder')" />
        </template>
        <template v-else>
          <h2 class="pv-hero-name">{{ local.character || t('profileViewer.characterNamePlaceholder') }}</h2>
          <p v-if="local.series" class="pv-hero-series">{{ local.series }}</p>
        </template>
        <div v-if="heroFacts.length" class="pv-hero-facts">
          <span v-for="(f, i) in heroFacts" :key="i">{{ f }}</span>
        </div>
      </div>
    </div>
    <p v-if="mode === 'browse' && heroQuote" class="pv-hero-quote">{{ heroQuote }}</p>

    <!-- 作品 / 角色 tab switch -->
    <div class="pv-tab-nav">
      <button
        v-if="local.worldSetting"
        class="pv-tab-btn" :class="{ active: activeTab === 'world' }"
        @click="activeTab = 'world'"
      >{{ t('profileViewer.worldSectionTitle') }}</button>
      <button
        v-if="local.characterBackground"
        class="pv-tab-btn" :class="{ active: activeTab === 'char' }"
        @click="activeTab = 'char'"
      >{{ t('profileViewer.charSectionTitle') }}</button>
    </div>

    <!-- 作品 panel -->
    <div v-if="activeTab === 'world' && local.worldSetting" class="pv-panel">

      <!-- Edit mode: existing form -->
      <template v-if="mode === 'edit'">
        <div class="pv-chips">
          <span v-if="local.worldSetting.genre" class="pv-chip">{{ local.worldSetting.genre }}</span>
          <span v-if="local.worldSetting.era" class="pv-chip">{{ local.worldSetting.era }}</span>
          <span v-for="th in (local.worldSetting.themes || [])" :key="th" class="pv-chip accent">{{ th }}</span>
        </div>
        <p v-if="local.worldSetting.synopsis" class="pv-text">{{ local.worldSetting.synopsis }}</p>
        <div class="pv-expanded">
          <DynamicBlock
            v-for="(val, key) in worldExtra"
            :key="key"
            :label="label(String(key))"
            :value="val"
            @update="v => updateField('worldSetting', String(key), v)"
          />
        </div>
      </template>

      <!-- Browse mode: bespoke read view -->
      <template v-else>
        <div class="pv-card">
          <div class="pv-chips">
            <span v-if="ws.genre" class="pv-chip">{{ ws.genre }}</span>
            <span v-if="ws.era" class="pv-chip">{{ ws.era }}</span>
            <span v-for="th in ws.themes || []" :key="th" class="pv-chip accent">{{ th }}</span>
          </div>
          <p v-if="ws.synopsis" class="pv-text">{{ ws.synopsis }}</p>
          <div v-if="ws.timeline" class="pv-row">
            <span class="pv-row-label">{{ label('timeline') }}</span>
            <span class="pv-row-val">{{ ws.timeline }}</span>
          </div>
        </div>

        <div v-if="ws.tone" class="pv-card">
          <div class="pv-card-title">{{ label('tone') }}</div>
          <div class="pv-rows">
            <div v-if="ws.tone.visual" class="pv-row"><span class="pv-row-label">{{ label('visual') }}</span><span class="pv-row-val">{{ ws.tone.visual }}</span></div>
            <div v-if="ws.tone.narrative" class="pv-row"><span class="pv-row-label">{{ label('narrative') }}</span><span class="pv-row-val">{{ ws.tone.narrative }}</span></div>
            <div v-if="ws.tone.emotion" class="pv-row"><span class="pv-row-label">{{ label('emotion') }}</span><span class="pv-row-val">{{ ws.tone.emotion }}</span></div>
          </div>
        </div>

        <div v-if="ws.iconic_settings?.length" class="pv-card">
          <div class="pv-card-title">{{ label('iconic_settings') }}</div>
          <div class="pv-chips">
            <span v-for="s in ws.iconic_settings" :key="s" class="pv-chip">{{ s }}</span>
          </div>
        </div>
      </template>
    </div>

    <!-- 角色 panel -->
    <div v-else-if="activeTab === 'char' && local.characterBackground" class="pv-panel">

      <!-- Edit mode: existing form -->
      <template v-if="mode === 'edit'">
        <div class="pv-chips">
          <span v-if="local.characterBackground.role" class="pv-chip accent">{{ local.characterBackground.role }}</span>
          <span v-if="local.characterBackground.age" class="pv-chip">{{ local.characterBackground.age }}</span>
        </div>
        <div v-if="(local.characterBackground.relations || []).length" class="pv-relations-summary">
          <span v-for="r in local.characterBackground.relations" :key="r.name" class="pv-rel-chip">
            <span class="rel-name">{{ r.name }}</span>
            <span class="rel-type">{{ r.relationship }}</span>
          </span>
        </div>
        <div class="pv-expanded">
          <DynamicBlock
            v-for="(val, key) in charExtra"
            :key="key"
            :label="label(String(key))"
            :value="val"
            @update="v => updateField('characterBackground', String(key), v)"
          />
        </div>
      </template>

      <!-- Browse mode: bespoke read view -->
      <template v-else>
        <div v-if="(cb.relations || []).length" class="pv-card">
          <div class="pv-card-title">{{ label('relations') }}</div>
          <div class="pv-rel-grid">
            <div v-for="r in cb.relations" :key="r.name" class="pv-rel-card">
              <div class="pv-rel-card-name">{{ r.name }}</div>
              <div class="pv-rel-card-type">{{ r.relationship }}</div>
            </div>
          </div>
        </div>

        <div v-if="cb.backstory" class="pv-card">
          <div class="pv-card-title">{{ label('backstory') }}</div>
          <p class="pv-text">{{ cb.backstory }}</p>
        </div>

        <div v-if="cb.personality" class="pv-card">
          <div class="pv-card-title">{{ label('personality') }}</div>
          <div v-if="cb.personality.surface || cb.personality.inner" class="pv-contrast">
            <div v-if="cb.personality.surface" class="pv-contrast-half surface">
              <div class="pv-contrast-label">{{ label('surface') }}</div>
              <p class="pv-contrast-text">{{ cb.personality.surface }}</p>
            </div>
            <div v-if="cb.personality.inner" class="pv-contrast-half inner">
              <div class="pv-contrast-label">{{ label('inner') }}</div>
              <p class="pv-contrast-text">{{ cb.personality.inner }}</p>
            </div>
          </div>
          <div class="pv-trait-grid">
            <div v-if="cb.personality.strength" class="pv-trait-mini"><div class="pv-trait-mini-label">{{ label('strength') }}</div><p>{{ cb.personality.strength }}</p></div>
            <div v-if="cb.personality.weakness" class="pv-trait-mini"><div class="pv-trait-mini-label">{{ label('weakness') }}</div><p>{{ cb.personality.weakness }}</p></div>
            <div v-if="cb.personality.core_desire" class="pv-trait-mini"><div class="pv-trait-mini-label">{{ label('core_desire') }}</div><p>{{ cb.personality.core_desire }}</p></div>
            <div v-if="cb.personality.fear" class="pv-trait-mini"><div class="pv-trait-mini-label">{{ label('fear') }}</div><p>{{ cb.personality.fear }}</p></div>
          </div>
        </div>

        <div v-if="cb.emotional_range" class="pv-card">
          <div class="pv-card-title">{{ label('emotional_range') }}</div>
          <div class="pv-timeline">
            <div v-if="cb.emotional_range.baseline" class="pv-tl-item">
              <span class="pv-tl-dot"></span>
              <div class="pv-tl-label">{{ label('baseline') }}</div>
              <p class="pv-tl-text">{{ cb.emotional_range.baseline }}</p>
            </div>
            <div v-if="cb.emotional_range.stress" class="pv-tl-item">
              <span class="pv-tl-dot"></span>
              <div class="pv-tl-label">{{ label('stress') }}</div>
              <p class="pv-tl-text">{{ cb.emotional_range.stress }}</p>
            </div>
            <div v-if="cb.emotional_range.breaking_point" class="pv-tl-item">
              <span class="pv-tl-dot"></span>
              <div class="pv-tl-label">{{ label('breaking_point') }}</div>
              <p class="pv-tl-text">{{ cb.emotional_range.breaking_point }}</p>
            </div>
            <div v-if="cb.emotional_range.recovery" class="pv-tl-item">
              <span class="pv-tl-dot"></span>
              <div class="pv-tl-label">{{ label('recovery') }}</div>
              <p class="pv-tl-text">{{ cb.emotional_range.recovery }}</p>
            </div>
          </div>
        </div>

        <div v-if="cb.behavior" class="pv-card">
          <div class="pv-card-title">{{ label('behavior') }}</div>
          <template v-if="cb.behavior.speech_style">
            <div class="pv-sub-title">{{ label('speech_style') }}</div>
            <div class="pv-rows">
              <div v-if="cb.behavior.speech_style.tone" class="pv-row"><span class="pv-row-label">{{ label('tone_speech') }}</span><span class="pv-row-val">{{ cb.behavior.speech_style.tone }}</span></div>
              <div v-if="cb.behavior.speech_style.volume" class="pv-row"><span class="pv-row-label">{{ label('volume') }}</span><span class="pv-row-val">{{ cb.behavior.speech_style.volume }}</span></div>
              <div v-if="cb.behavior.speech_style.humor" class="pv-row"><span class="pv-row-label">{{ label('humor') }}</span><span class="pv-row-val">{{ cb.behavior.speech_style.humor }}</span></div>
              <div v-if="cb.behavior.speech_style.vocabulary" class="pv-row"><span class="pv-row-label">{{ label('vocabulary') }}</span><span class="pv-row-val">{{ cb.behavior.speech_style.vocabulary }}</span></div>
            </div>
          </template>
          <template v-if="cb.behavior.habits?.length">
            <div class="pv-sub-title">{{ label('habits') }}</div>
            <div class="pv-chips">
              <span v-for="h in cb.behavior.habits" :key="h" class="pv-chip">{{ h }}</span>
            </div>
          </template>
        </div>

        <div v-if="cb.behavior && (cb.behavior.values?.length || cb.behavior.likes?.length || cb.behavior.dislikes?.length)" class="pv-card">
          <div class="pv-pref-grid">
            <div v-if="cb.behavior.values?.length" class="pv-pref-col">
              <div class="pv-card-title">{{ label('values') }}</div>
              <p v-for="v in cb.behavior.values" :key="v" class="pv-pref-line">{{ v }}</p>
            </div>
            <div v-if="cb.behavior.likes?.length" class="pv-pref-col">
              <div class="pv-card-title">{{ label('likes') }}</div>
              <p v-for="v in cb.behavior.likes" :key="v" class="pv-pref-line">{{ v }}</p>
            </div>
            <div v-if="cb.behavior.dislikes?.length" class="pv-pref-col">
              <div class="pv-card-title">{{ label('dislikes') }}</div>
              <p v-for="v in cb.behavior.dislikes" :key="v" class="pv-pref-line">{{ v }}</p>
            </div>
          </div>
        </div>

        <div v-if="cb.key_events?.length" class="pv-card">
          <div class="pv-card-title">{{ label('key_events') }}</div>
          <div class="pv-timeline plain">
            <div v-for="(ev, i) in cb.key_events" :key="i" class="pv-tl-item">
              <span class="pv-tl-dot"></span>
              <p class="pv-tl-text">{{ ev }}</p>
            </div>
          </div>
        </div>

        <div v-if="cb.iconic_moments?.length" class="pv-card">
          <div class="pv-card-title">{{ label('iconic_moments') }}</div>
          <p v-for="(m, i) in cb.iconic_moments" :key="i" class="pv-quote">「{{ m }}」</p>
        </div>
      </template>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps<{ modelValue: Record<string, any>; refImageUrl?: string | null }>()
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

// Browse (read-only, styled) vs edit (form inputs) — a wall of input boxes
// makes sense while actively editing, but is the wrong default for reading.
const mode = ref<'browse' | 'edit'>('browse')

// 作品/角色 tab switch
const activeTab = ref<'world' | 'char'>('world')

const ws = computed(() => local.value.worldSetting || {})
const cb = computed(() => local.value.characterBackground || {})

const heroFacts = computed(() => [cb.value.role, cb.value.age].filter(Boolean))
const heroQuote = computed(() => cb.value.personality?.surface || '')

// Fields already shown in the browse-mode hero/summary — the rest renders
// as a plain edit form when mode === 'edit'.
const WORLD_SUMMARY_KEYS = new Set(['genre', 'era', 'themes', 'synopsis'])
const CHAR_SUMMARY_KEYS  = new Set(['role', 'age', 'relations'])

const worldExtra = computed(() =>
  Object.fromEntries(Object.entries(ws.value).filter(([k]) => !WORLD_SUMMARY_KEYS.has(k)))
)
const charExtra = computed(() =>
  Object.fromEntries(Object.entries(cb.value).filter(([k]) => !CHAR_SUMMARY_KEYS.has(k)))
)

function updateField(section: 'worldSetting' | 'characterBackground', key: string, val: any) {
  local.value = {
    ...local.value,
    [section]: { ...local.value[section], [key]: val },
  }
}

const { fieldLabel: label } = useFieldLabels()
const { t } = useLocale()
</script>

<style scoped>
.pv-root {
  --pv-primary: #4F4A8A;
  --pv-primary-tint: #ECEBF6;
  --pv-accent: #A45B72;
  --pv-accent-tint: #F5E9ED;
  --pv-bg: #F7F6FB;
  --pv-card: #FFFFFF;
  --pv-text: #29283A;
  --pv-text-dim: #6E6C85;
  --pv-text-sub: #9694A8;
  --pv-border: #E5E2F0;
  font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
  background: var(--pv-bg);
  color: var(--pv-text);
  display: flex; flex-direction: column; gap: 16px;
  overflow-y: auto; padding: 16px; border-radius: 14px; height: 100%;
  scrollbar-width: none;
}
.pv-root::-webkit-scrollbar { display: none; }

.pv-mode-row { display: flex; justify-content: flex-end; flex-shrink: 0; }
.pv-mode-btn {
  background: var(--pv-card); border: 1px solid var(--pv-border); border-radius: 20px;
  padding: 5px 14px; font-size: 12px; font-weight: 600; color: var(--pv-primary);
  cursor: pointer; transition: background 0.15s;
}
.pv-mode-btn:hover { background: var(--pv-primary-tint); }

/* Hero */
.pv-hero { display: flex; gap: 14px; flex-shrink: 0; }
.pv-hero-photo {
  width: 76px; height: 76px; border-radius: 14px; overflow: hidden; flex-shrink: 0;
  background: var(--pv-primary-tint); border: 1px solid var(--pv-border);
}
.pv-hero-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.pv-hero-photo-empty {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
  font-size: 30px; font-weight: 700; color: var(--pv-primary);
}
.pv-hero-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; justify-content: center; }
.pv-hero-name { font-size: 24px; font-weight: 700; color: var(--pv-text); margin: 0; }
.pv-hero-series { font-size: 13px; color: var(--pv-accent); margin: 0; font-weight: 500; }
.pv-hero-facts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 2px; }
.pv-hero-facts span {
  font-size: 12px; color: var(--pv-text-dim); font-weight: 600;
  padding-right: 8px; border-right: 1px solid var(--pv-border);
}
.pv-hero-facts span:last-child { border-right: none; padding-right: 0; }

.pv-name-input {
  background: none; border: none; border-bottom: 1px solid var(--pv-border);
  color: var(--pv-text); font-size: 22px; font-weight: 700; outline: none; padding: 2px 0; width: 100%;
  font-family: inherit; transition: border-color 0.2s;
}
.pv-name-input:focus { border-bottom-color: var(--pv-primary); }
.pv-series-input {
  background: none; border: none; color: var(--pv-text-dim); font-size: 13px; outline: none;
  padding: 1px 0; border-bottom: 1px solid transparent; width: 100%; font-family: inherit;
  transition: border-color 0.2s;
}
.pv-series-input:focus { border-bottom-color: var(--pv-border); }

.pv-hero-quote {
  font-size: 13px; font-style: italic; color: var(--pv-primary); line-height: 1.6;
  margin: 0; padding-left: 10px; border-left: 2px solid var(--pv-accent); flex-shrink: 0;
}

/* Tab nav — compact pills */
.pv-tab-nav { display: inline-flex; gap: 6px; flex-shrink: 0; }
.pv-tab-btn {
  padding: 6px 16px; border-radius: 20px; border: 1px solid var(--pv-border);
  background: var(--pv-card); font-size: 12.5px; font-weight: 600; color: var(--pv-text-dim);
  cursor: pointer; transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.pv-tab-btn.active { background: var(--pv-primary); border-color: var(--pv-primary); color: #fff; }
.pv-tab-btn:hover:not(.active) { border-color: var(--pv-primary); color: var(--pv-primary); }

.pv-panel { display: flex; flex-direction: column; gap: 16px; }

.pv-card {
  background: var(--pv-card); border: 1px solid var(--pv-border); border-radius: 14px;
  padding: 16px; display: flex; flex-direction: column; gap: 10px;
  box-shadow: 0 4px 16px rgba(50, 40, 90, 0.06);
}
.pv-card-title { font-size: 13px; font-weight: 700; color: var(--pv-text); }
.pv-sub-title { font-size: 11px; font-weight: 700; color: var(--pv-text-sub); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }

.pv-text { font-size: 14px; color: var(--pv-text-dim); line-height: 1.7; margin: 0; }

.pv-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.pv-chip {
  padding: 3px 10px; background: var(--pv-card); border: 1px solid var(--pv-border);
  border-radius: 20px; font-size: 12px; color: var(--pv-text-dim);
}
.pv-chip.accent { background: var(--pv-primary-tint); border-color: transparent; color: var(--pv-primary); font-weight: 600; }

.pv-rows { display: flex; flex-direction: column; }
.pv-row {
  display: flex; gap: 12px; align-items: baseline;
  padding: 6px 0; border-bottom: 1px dashed var(--pv-border);
}
.pv-row:last-child { border-bottom: none; padding-bottom: 0; }
.pv-row:first-child { padding-top: 0; }
.pv-row-label { font-size: 12px; font-weight: 600; color: var(--pv-text-sub); flex-shrink: 0; width: 52px; }
.pv-row-val { font-size: 13px; color: var(--pv-text-dim); line-height: 1.6; }

/* Relations */
.pv-rel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 420px) { .pv-rel-grid { grid-template-columns: 1fr; } }
.pv-rel-card {
  background: var(--pv-bg); border: 1px solid var(--pv-border); border-radius: 10px; padding: 9px 12px;
}
.pv-rel-card-name { font-size: 13px; font-weight: 700; color: var(--pv-text); }
.pv-rel-card-type { font-size: 11.5px; color: var(--pv-text-sub); margin-top: 2px; }

.pv-relations-summary { display: flex; flex-wrap: wrap; gap: 6px; }
.pv-rel-chip {
  display: flex; align-items: center; gap: 4px;
  background: var(--pv-bg); border: 1px solid var(--pv-border); border-radius: 6px; padding: 3px 8px;
}
.rel-name { font-size: 11px; color: var(--pv-text); font-weight: 600; }
.rel-type { font-size: 10px; color: var(--pv-text-sub); }

/* Personality contrast */
.pv-contrast { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 420px) { .pv-contrast { grid-template-columns: 1fr; } }
.pv-contrast-half { border-radius: 10px; padding: 10px 12px; }
.pv-contrast-half.surface { background: var(--pv-primary-tint); }
.pv-contrast-half.inner { background: var(--pv-accent-tint); }
.pv-contrast-label { font-size: 11px; font-weight: 700; color: var(--pv-text-sub); margin-bottom: 4px; }
.pv-contrast-half.surface .pv-contrast-label { color: var(--pv-primary); }
.pv-contrast-half.inner .pv-contrast-label { color: var(--pv-accent); }
.pv-contrast-text { font-size: 12.5px; color: var(--pv-text-dim); line-height: 1.65; margin: 0; }

.pv-trait-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 420px) { .pv-trait-grid { grid-template-columns: 1fr; } }
.pv-trait-mini { background: var(--pv-bg); border-radius: 8px; padding: 8px 10px; }
.pv-trait-mini-label { font-size: 10.5px; font-weight: 700; color: var(--pv-text-sub); margin-bottom: 3px; }
.pv-trait-mini p { font-size: 12px; color: var(--pv-text-dim); line-height: 1.6; margin: 0; }

/* Timeline */
.pv-timeline { position: relative; padding-left: 16px; display: flex; flex-direction: column; gap: 14px; }
.pv-timeline::before {
  content: ''; position: absolute; left: 3px; top: 5px; bottom: 5px; width: 1px; background: var(--pv-border);
}
.pv-tl-item { position: relative; }
.pv-tl-dot {
  position: absolute; left: -16px; top: 4px; width: 7px; height: 7px; border-radius: 50%;
  background: var(--pv-primary);
}
.pv-timeline.plain .pv-tl-dot { background: var(--pv-accent); }
.pv-tl-label { font-size: 11px; font-weight: 700; color: var(--pv-text-sub); margin-bottom: 2px; }
.pv-tl-text { font-size: 12.5px; color: var(--pv-text-dim); line-height: 1.65; margin: 0; }

/* Preferences */
.pv-pref-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
@media (max-width: 480px) { .pv-pref-grid { grid-template-columns: 1fr; } }
.pv-pref-col { display: flex; flex-direction: column; gap: 4px; }
.pv-pref-line { font-size: 12.5px; color: var(--pv-text-dim); line-height: 1.6; margin: 0; }

.pv-quote {
  font-size: 13px; font-style: italic; color: var(--pv-text-dim);
  line-height: 1.7; margin: 0; padding-left: 8px; border-left: 2px solid var(--pv-accent);
}
.pv-quote + .pv-quote { margin-top: 6px; }

/* Edit-mode-only spacing for DynamicBlock list */
.pv-expanded {
  display: flex; flex-direction: column; gap: 14px;
  padding-top: 12px; margin-top: 4px; border-top: 1px solid var(--pv-border);
}
</style>
