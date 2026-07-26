<template>
  <span class="el">
    <template v-for="(item, i) in items" :key="i">
      <span v-if="editIndex !== i" class="el-item" :title="editHint" @click="startEdit(i)">{{ item }}</span>
      <input
        v-else
        ref="fieldEl"
        v-model="draft"
        class="el-input"
        @blur="commit"
        @keydown.enter.prevent="commit"
        @keydown.esc.prevent="cancel"
      />
      <span v-if="i < items.length - 1" class="el-sep"> · </span>
    </template>

    <!-- add -->
    <input
      v-if="editIndex === items.length"
      ref="addEl"
      v-model="draft"
      class="el-input el-add-input"
      :placeholder="addPlaceholder"
      @blur="commit"
      @keydown.enter.prevent="commit"
      @keydown.esc.prevent="cancel"
    />
    <button v-else class="el-add" :title="addHint" @click="startAdd">＋</button>
  </span>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'

const props = defineProps<{
  items: string[]
  editHint?: string
  addHint?: string
  addPlaceholder?: string
}>()
const emit = defineEmits<{ (e: 'change', items: string[]): void }>()

const editIndex = ref(-1)   // -1 none, 0..n-1 editing an item, n adding a new one
const draft = ref('')
const fieldEl = ref<HTMLInputElement[] | null>(null)
const addEl = ref<HTMLInputElement | null>(null)

async function focusInput() {
  await nextTick()
  const el = editIndex.value === props.items.length
    ? addEl.value
    : (Array.isArray(fieldEl.value) ? fieldEl.value[0] : fieldEl.value)
  el?.focus(); el?.select?.()
}

function startEdit(i: number) {
  editIndex.value = i; draft.value = props.items[i]; focusInput()
}
function startAdd() {
  editIndex.value = props.items.length; draft.value = ''; focusInput()
}

function commit() {
  if (editIndex.value < 0) return
  const i = editIndex.value
  const v = draft.value.trim()
  const next = [...props.items]
  if (i === props.items.length) {
    if (v) next.push(v)                       // add (empty = discard)
  } else if (!v) {
    next.splice(i, 1)                         // clear = remove
  } else {
    next[i] = v                               // edit
  }
  editIndex.value = -1
  if (JSON.stringify(next) !== JSON.stringify(props.items)) emit('change', next)
}
function cancel() { editIndex.value = -1 }
</script>

<style scoped>
.el { display: inline; line-height: 1.9; }
.el-item {
  cursor: text; border-radius: 4px; padding: 1px 2px;
  transition: background 0.12s;
}
.el-item:hover { background: var(--surface-inset); box-shadow: 0 0 0 3px var(--surface-inset); }
.el-sep { color: var(--text-ghost); }
.el-input {
  font: inherit; color: var(--text-hi); background: var(--surface);
  border: 1px solid var(--accent); border-radius: 5px;
  padding: 1px 6px; outline: none; width: 9em; max-width: 100%;
}
.el-add {
  margin-left: 6px; width: 16px; height: 16px; padding: 0; cursor: pointer;
  border: none; background: none;
  color: var(--text-quiet); font-size: 14px; line-height: 1;
  vertical-align: middle; transition: color 0.12s;
}
.el-add:hover { color: var(--accent); }
.el-add-input { width: 7em; }
</style>
