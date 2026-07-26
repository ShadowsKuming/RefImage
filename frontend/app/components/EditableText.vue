<template>
  <!-- editing: input/textarea -->
  <textarea
    v-if="editing && multiline"
    ref="fieldEl"
    v-model="draft"
    class="et-input et-ta"
    :placeholder="placeholder"
    rows="3"
    @blur="commit"
    @keydown.esc.prevent="cancel"
    @keydown.enter.exact="onEnter"
  />
  <input
    v-else-if="editing"
    ref="fieldEl"
    v-model="draft"
    class="et-input"
    :placeholder="placeholder"
    @blur="commit"
    @keydown.enter.prevent="commit"
    @keydown.esc.prevent="cancel"
  />
  <!-- display: click to edit -->
  <span
    v-else
    class="et-view" :class="{ empty: !modelValue }"
    :title="editHint"
    tabindex="0"
    @click="startEdit"
    @keydown.enter.prevent="startEdit"
  >{{ modelValue || placeholder }}<Pencil class="et-pencil" /></span>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { Pencil } from 'lucide-vue-next'

const props = defineProps<{
  modelValue: string
  multiline?: boolean
  placeholder?: string
  editHint?: string
}>()
const emit = defineEmits<{ (e: 'save', value: string): void }>()

const editing = ref(false)
const draft = ref('')
const fieldEl = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

async function startEdit() {
  draft.value = props.modelValue
  editing.value = true
  await nextTick()
  fieldEl.value?.focus()
  if (fieldEl.value instanceof HTMLInputElement) fieldEl.value.select()
}

function commit() {
  if (!editing.value) return
  editing.value = false
  const v = draft.value.trim()
  if (v !== (props.modelValue || '').trim()) emit('save', v)
}

function cancel() {
  editing.value = false
}

// In a textarea, Enter inserts a newline; Cmd/Ctrl+Enter commits.
function onEnter(e: KeyboardEvent) {
  if (e.metaKey || e.ctrlKey) { e.preventDefault(); commit() }
}
</script>

<style scoped>
.et-view {
  display: inline; cursor: text; border-radius: 4px;
  transition: background 0.12s;
}
.et-view:hover, .et-view:focus {
  background: var(--surface-inset); outline: none;
  box-shadow: 0 0 0 4px var(--surface-inset);
}
.et-view.empty { color: var(--text-ghost); }
.et-pencil {
  width: 11px; height: 11px; margin-left: 5px; vertical-align: baseline;
  color: var(--text-ghost); opacity: 0; transition: opacity 0.12s;
}
.et-view:hover .et-pencil, .et-view:focus .et-pencil { opacity: 1; }

.et-input {
  width: 100%; box-sizing: border-box; font: inherit; color: var(--text-hi);
  background: var(--surface); border: 1px solid var(--accent-dim);
  border-radius: 6px; padding: 4px 8px; outline: none; line-height: 1.5;
}
.et-input:focus { border-color: var(--accent); }
.et-ta { resize: vertical; }
</style>
