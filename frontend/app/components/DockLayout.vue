<script setup lang="ts">
import { Splitpanes, Pane } from 'splitpanes'
import { computed, ref } from 'vue'

defineOptions({ name: 'DockLayout' })

export type PanelId = string
export type Edge = 'left' | 'right' | 'top' | 'bottom'
export type PanelNode = { type: 'panel'; id: PanelId }
export type SplitNode = { type: 'split'; dir: 'h' | 'v'; ratio: number; a: LayoutNode; b: LayoutNode }
export type LayoutNode = PanelNode | SplitNode

const props = defineProps<{
  node:        LayoutNode
  dragging:    PanelId | null
  hoverInfo:   { panelId: PanelId; edge: Edge } | null
  titles:      Record<PanelId, string>
  collapsible: PanelId[]
  collapsed:   PanelId[]
  collapseDir: 'h' | 'v' | null  // direction inherited from parent split
}>()

const emit = defineEmits<{
  'panel-mousedown': [id: PanelId]
  'move':            [p: { target: PanelId; panel: PanelId; edge: Edge }]
  'toggle-collapse': [id: PanelId]
}>()

// ── Split node helpers ─────────────────────────────────────
const sn = computed(() => props.node.type === 'split' ? props.node as SplitNode : null)

// leaf panel ID directly inside pane a / b (null if pane is itself a split)
const aLeaf = computed(() => sn.value?.a.type === 'panel' ? (sn.value.a as PanelNode).id : null)
const bLeaf = computed(() => sn.value?.b.type === 'panel' ? (sn.value.b as PanelNode).id : null)

const aCollapsed = computed(() => !!aLeaf.value && props.collapsed.includes(aLeaf.value))
const bCollapsed = computed(() => !!bLeaf.value && props.collapsed.includes(bLeaf.value))

// How small a collapsed pane becomes (%)
const SMALL_H = 5   // thin sidebar strip
const SMALL_V = 6   // just the header bar (≈ 38px at typical heights)

const smallPct = computed(() => sn.value?.dir === 'h' ? SMALL_H : SMALL_V)
const ratio    = computed(() => sn.value?.ratio ?? 50)

const sizeA = computed(() => {
  if (aCollapsed.value) return smallPct.value
  if (bCollapsed.value) return 100 - smallPct.value
  return ratio.value
})
const sizeB = computed(() => 100 - sizeA.value)

// ── Panel node helpers ─────────────────────────────────────
const pn         = computed(() => props.node.type === 'panel' ? props.node as PanelNode : null)
const myId       = computed(() => pn.value?.id ?? null)
const canCollapse = computed(() => !!myId.value && props.collapsible.includes(myId.value))
const isCollapsed = computed(() => !!myId.value && props.collapsed.includes(myId.value))

// From the parent split's direction we know how this panel collapses
const colDir = computed(() => props.collapseDir)   // 'h' | 'v' | null

// Edge highlight during drag-over
const activeEdge = computed(() => {
  if (!myId.value) return null
  if (props.hoverInfo?.panelId !== myId.value) return null
  return props.hoverInfo.edge
})
</script>

<template>
  <!-- ── Split node ── -->
  <Splitpanes
    v-if="node.type === 'split'"
    :horizontal="(node as SplitNode).dir === 'v'"
    class="dock-split"
  >
    <Pane :size="sizeA" :min-size="aCollapsed ? 0 : 8">
      <DockLayout
        :node="(node as SplitNode).a"
        :dragging="dragging"
        :hoverInfo="hoverInfo"
        :titles="titles"
        :collapsible="collapsible"
        :collapsed="collapsed"
        :collapse-dir="(node as SplitNode).dir"
        @panel-mousedown="$emit('panel-mousedown', $event)"
        @move="$emit('move', $event)"
        @toggle-collapse="$emit('toggle-collapse', $event)"
      >
        <template v-for="(_, name) in $slots" #[name]="sd">
          <slot :name="name" v-bind="sd || {}" />
        </template>
      </DockLayout>
    </Pane>
    <Pane :size="sizeB" :min-size="bCollapsed ? 0 : 8">
      <DockLayout
        :node="(node as SplitNode).b"
        :dragging="dragging"
        :hoverInfo="hoverInfo"
        :titles="titles"
        :collapsible="collapsible"
        :collapsed="collapsed"
        :collapse-dir="(node as SplitNode).dir"
        @panel-mousedown="$emit('panel-mousedown', $event)"
        @move="$emit('move', $event)"
        @toggle-collapse="$emit('toggle-collapse', $event)"
      >
        <template v-for="(_, name) in $slots" #[name]="sd">
          <slot :name="name" v-bind="sd || {}" />
        </template>
      </DockLayout>
    </Pane>
  </Splitpanes>

  <!-- ── Panel node ── -->
  <div
    v-else
    class="dock-panel"
    :class="[
      { 'is-source':    dragging === node.id },
      { 'col-h':        isCollapsed && colDir === 'h' },
      { 'col-v':        isCollapsed && colDir === 'v' },
      activeEdge ? `edge-${activeEdge}` : '',
    ]"
    :data-panel-id="node.id"
  >
    <!-- Header -->
    <div
      class="dock-header"
      @mousedown="$emit('panel-mousedown', node.id)"
    >
      <span class="panel-name">{{ titles[node.id] ?? node.id }}</span>
      <button
        v-if="canCollapse"
        class="collapse-btn"
        @click.stop="$emit('toggle-collapse', node.id)"
        :title="isCollapsed ? '展开' : '折叠'"
      >
        <!-- h-collapse: left/right arrows -->
        <template v-if="colDir === 'h'">
          <span v-if="!isCollapsed">◀▶</span>
          <span v-else>▶◀</span>
        </template>
        <!-- v-collapse: up/down arrows -->
        <template v-else>
          <span v-if="!isCollapsed">▾</span>
          <span v-else>▴</span>
        </template>
      </button>
    </div>

    <!-- Body: hidden when collapsed -->
    <div v-show="!isCollapsed" class="dock-body">
      <slot :name="node.id" />
    </div>
  </div>
</template>

<!-- global splitpanes overrides -->
<style>
@import 'splitpanes/dist/splitpanes.css';

.dock-split > .splitpanes__splitter {
  background: var(--bg) !important;
  flex-shrink: 0;
  z-index: 1;
}
.dock-split.splitpanes--vertical > .splitpanes__splitter {
  width: 10px !important;
  cursor: col-resize;
}
.dock-split.splitpanes--horizontal > .splitpanes__splitter {
  height: 10px !important;
  cursor: row-resize;
}
</style>

<style scoped>
.dock-split { width: 100%; height: 100%; }

/* ── Panel card ── */
.dock-panel {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-radius: 14px;
  overflow: hidden;
  box-sizing: border-box;
  border: 1.5px solid transparent;
  box-shadow: 0 2px 16px var(--shadow);
  transition: border-color 0.12s, opacity 0.15s;
}
.dock-panel.is-source { opacity: 0.25; }

/* Edge highlight on drag-over */
.dock-panel.edge-left   { border-left-color:   var(--accent); }
.dock-panel.edge-right  { border-right-color:  var(--accent); }
.dock-panel.edge-top    { border-top-color:    var(--accent); }
.dock-panel.edge-bottom { border-bottom-color: var(--accent); }

/* ── Collapsed: horizontal (thin sidebar strip) ── */
.dock-panel.col-h {
  border-radius: 14px;
}
.dock-panel.col-h .dock-header {
  flex-direction: column-reverse;
  height: 100%;
  border-bottom: none;
  border-radius: 14px;
  padding: 16px 0 10px;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}
.dock-panel.col-h .panel-name {
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  font-size: 11px;
  letter-spacing: 0.08em;
}
.dock-panel.col-h .collapse-btn {
  margin: 0;
}

/* ── Collapsed: vertical (header-only bar) ── */
.dock-panel.col-v .dock-header {
  border-radius: 14px;
  border-bottom: none;
  cursor: pointer;
}

/* ── Header ── */
.dock-header {
  height: 38px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  background: var(--surface);
  border-bottom: 1px solid var(--surface-2);
  border-radius: 14px 14px 0 0;
  cursor: grab;
  flex-shrink: 0;
  user-select: none;
  gap: 8px;
}
.dock-header:active { cursor: grabbing; }

.panel-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-2);
  flex: 1;
}

/* ── Collapse button ── */
.collapse-btn {
  width: 26px; height: 26px;
  background: none; border: none; cursor: pointer;
  color: var(--text-quiet); border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; letter-spacing: -1px;
  flex-shrink: 0;
  transition: background 0.15s, color 0.15s;
}
.collapse-btn:hover { background: var(--border); color: var(--text-muted); }

/* ── Body ── */
.dock-body { flex: 1; overflow: auto; min-height: 0; }
</style>
