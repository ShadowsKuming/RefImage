<template>
  <div class="db-root">
    <div class="db-label">{{ label }}</div>

    <!-- string[] → chip list -->
    <div v-if="isStringArray" class="db-chips">
      <span v-for="(item, i) in (value as string[])" :key="i" class="db-chip">{{ item }}</span>
    </div>

    <!-- object[] (e.g. relations) → mini cards -->
    <div v-else-if="isObjectArray" class="db-cards">
      <div v-for="(item, i) in (value as Record<string, any>[])" :key="i" class="db-card">
        <div v-for="(v, k) in item" :key="k" class="db-card-row">
          <span class="db-card-key">{{ labelOf(k as string) }}</span>
          <span class="db-card-val">{{ v }}</span>
        </div>
      </div>
    </div>

    <!-- nested object → recurse -->
    <div v-else-if="isObject" class="db-object">
      <DynamicBlock
        v-for="(v, k) in (value as Record<string, any>)"
        :key="k"
        :label="labelOf(k as string)"
        :value="v"
        @update="nv => emitNested(k as string, nv)"
      />
    </div>

    <!-- plain string → textarea -->
    <textarea
      v-else-if="isLongString"
      class="db-textarea"
      :value="(value as string)"
      rows="3"
      @input="emit('update', ($event.target as HTMLTextAreaElement).value)"
    />

    <!-- short string → input -->
    <input
      v-else
      class="db-input"
      :value="(value as string)"
      @input="emit('update', ($event.target as HTMLInputElement).value)"
    />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ label: string; value: unknown }>()
const emit = defineEmits<{ (e: 'update', v: any): void }>()

const isStringArray = computed(() =>
  Array.isArray(props.value) && props.value.every(x => typeof x === 'string'),
)
const isObjectArray = computed(() =>
  Array.isArray(props.value) && props.value.length > 0 && typeof props.value[0] === 'object',
)
const isObject = computed(() =>
  !Array.isArray(props.value) && typeof props.value === 'object' && props.value !== null,
)
const isLongString = computed(() =>
  typeof props.value === 'string' && props.value.length > 40,
)

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
function labelOf(key: string) { return LABELS[key] || key }

function emitNested(key: string, newVal: any) {
  const copy = JSON.parse(JSON.stringify(props.value as object))
  ;(copy as any)[key] = newVal
  emit('update', copy)
}
</script>

<style scoped>
.db-root { display: flex; flex-direction: column; gap: 4px; }
.db-label { font-size: 10px; font-weight: 700; color: var(--text-quiet); text-transform: uppercase; letter-spacing: 0.5px; }

.db-input {
  background: var(--bg); border: 1px solid var(--border); border-radius: 5px;
  padding: 5px 8px; color: var(--text-hi); font-size: 12px; outline: none;
  transition: border-color 0.2s; width: 100%; box-sizing: border-box;
}
.db-input:focus { border-color: var(--border-focus); }

.db-textarea {
  background: var(--bg); border: 1px solid var(--border); border-radius: 5px;
  padding: 8px; color: var(--text-neutral); font-size: 12px; line-height: 1.7;
  outline: none; resize: vertical; width: 100%; box-sizing: border-box;
  font-family: inherit; transition: border-color 0.2s;
}
.db-textarea:focus { border-color: var(--border-focus); }

.db-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.db-chip {
  padding: 2px 8px; background: var(--surface-2); border: 1px solid var(--border-focus);
  border-radius: 4px; font-size: 11px; color: var(--text-muted);
}

.db-cards { display: flex; flex-direction: column; gap: 6px; }
.db-card {
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 6px;
  padding: 8px 10px; display: flex; flex-direction: column; gap: 3px;
}
.db-card-row { display: flex; gap: 8px; align-items: baseline; }
.db-card-key { font-size: 10px; color: var(--text-quiet); text-transform: uppercase; flex-shrink: 0; min-width: 36px; }
.db-card-val { font-size: 12px; color: var(--text-neutral); }

.db-object { display: flex; flex-direction: column; gap: 8px; padding-left: 10px; border-left: 1px solid var(--border-md); }
</style>
