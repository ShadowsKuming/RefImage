<template>
  <div class="shot-page">

    <!-- Top bar -->
    <div class="top-bar">
      <div class="breadcrumb">
        <button class="back-btn" @click="goBack">← 返回</button>
        <span class="bc-sep">/</span>
        <span class="bc-item">{{ characterName }}</span>
        <span class="bc-sep">/</span>
        <span v-if="!editingTitle" class="bc-current" title="点击重命名" @click="startRenameTitle">
          {{ shot.title }}{{ hasUnsavedChanges ? ' *' : '' }}
        </span>
        <input
          v-else
          ref="titleInputRef"
          v-model="titleDraft"
          class="bc-title-input"
          @blur="commitRename"
          @keydown.enter.prevent="commitRename"
          @keydown.escape.prevent="cancelRename"
        />
        <span class="shot-mood-badge">{{ shot.mood }}</span>
      </div>
      <div class="tb-actions">
        <span v-if="generating" class="tb-generating">✦ 生成中…</span>
        <template v-else-if="isRefined">
          <span class="tb-refined-badge">✓ 已完善</span>
          <button class="tb-btn" @click="unlockShot">解锁编辑</button>
        </template>
        <button
          v-else-if="shot.status === 'done'"
          class="tb-btn primary"
          @click="guardAction(refineShot)"
        >标记完善</button>
      </div>
    </div>

    <!-- Main layout: left AI | center canvas | right guide -->
    <div class="main-layout">

      <!-- ── Left: AI generation panel ── -->
      <div class="ai-col" :style="{ width: leftWidth + 'px' }">
        <div class="col-header">AI 生成助手</div>

        <div class="ai-messages" ref="aiMsgContainer">
          <div v-for="(msg, i) in aiMessages" :key="i" class="ai-msg" :class="msg.role">
            <div v-if="msg.role === 'agent'" class="ai-avatar">AI</div>
            <div class="ai-bubble">{{ msg.text }}</div>
          </div>
          <div v-if="chatLoading" class="ai-msg agent">
            <div class="ai-avatar">AI</div>
            <div class="ai-bubble typing"><span /><span /><span /></div>
          </div>
        </div>

        <div v-if="selectedVersionIds.length > 0 || selectedRefIds.length > 0" class="selection-hint">
          <template v-if="selectedVersionIds.length > 0">已选 {{ selectedVersionIds.length }} 张版本</template>
          <template v-if="selectedVersionIds.length > 0 && selectedRefIds.length > 0"> · </template>
          <template v-if="selectedRefIds.length > 0">{{ selectedRefIds.length }} 张参考图</template>
          · 框选内容将告知 AI 助手
        </div>
        <div class="ref-upload-row">
          <button class="ref-upload-btn" @click="triggerRefUpload" title="上传参考图（姿势/背景/武器/服装等）">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
              <path d="M10 3v10M6 7l4-4 4 4"/><path d="M3 14v1a2 2 0 002 2h10a2 2 0 002-2v-1"/>
            </svg>
            上传参考图
          </button>
          <input ref="refFileInput" type="file" accept="image/*" style="display:none" @change="onRefFileInputChange" />
        </div>

        <div class="ai-input-row">
          <input v-model="chatInput" class="ai-input"
                 :placeholder="isRefined ? '已完善，解锁后可继续编辑' : '调整例图或提问…'"
                 :disabled="generating || chatLoading || isRefined"
                 @keydown.enter.exact.prevent="sendChat" />
          <button class="ai-send" :disabled="generating || chatLoading || isRefined" @click="sendChat">↑</button>
        </div>
      </div>

      <!-- Resizer: left | canvas -->
      <div class="resizer" @mousedown.prevent="startResize2('left', $event)" />

      <!-- ── Center: Canvas ── -->
      <div class="canvas-col">

        <!-- Generating overlay — blocks all canvas interaction during image gen -->
        <Transition name="gen-overlay">
          <div v-if="generating" class="gen-overlay">
            <div class="gen-overlay-card">
              <div class="gen-spinner"></div>
              <span class="gen-label">参考图生成中</span>
              <span class="gen-sub">大约需要 30–60 秒</span>
            </div>
          </div>
        </Transition>

        <div
          class="canvas-wrap"
          ref="canvasWrapRef"
          :class="{ panning: dragMode === 'pan', 'crop-active': editMode === 'crop' }"
          :style="gridStyle"
          @mousedown.self="startPan"
          @dblclick.self="onCanvasDblClick"
          @wheel.prevent="onWheel"
        >
          <div class="canvas-scene" :style="{ transform: sceneTransform }">

            <!-- SVG edges -->
            <svg v-if="allNodes.length > 1" class="edges-svg">
              <path
                v-for="e in treeEdges"
                :key="e.id"
                :d="edgePath(e)"
                class="edge-path"
              />
            </svg>

            <!-- ── Version cards ── -->
            <template v-for="node in layoutNodes" :key="node.id">

              <!-- Active version card -->
              <div
                v-if="node.id === activeVersionId"
                class="version-card active-card"
                :class="{ 'in-crop': editMode === 'crop', 'is-selected': selectedVersionIds.includes(node.id) }"
                :style="cardStyle(node)"
                @mousedown.stop="startVersionCardDrag(node.id, $event)"
                @click.stop="toggleSelectVersion(node.id)"
              >
                <!-- Image -->
                <div class="img-clip">
                  <img :src="currentDisplayUrl" class="gen-img" draggable="false" />

                  <!-- Crop layer -->
                  <template v-if="editMode === 'crop'">
                    <div class="crop-layer" @mousedown.stop="onCropLayerDown" />
                    <div v-if="inlineCrop"
                         class="crop-rect"
                         :style="{
                           left: inlineCrop.x + 'px', top: inlineCrop.y + 'px',
                           width: inlineCrop.w + 'px', height: inlineCrop.h + 'px',
                         }"
                         @mousedown.stop="onCropRectDown"
                    >
                      <div class="ch tl" @mousedown.stop="startCropHandle('tl', $event)" />
                      <div class="ch tr" @mousedown.stop="startCropHandle('tr', $event)" />
                      <div class="ch bl" @mousedown.stop="startCropHandle('bl', $event)" />
                      <div class="ch br" @mousedown.stop="startCropHandle('br', $event)" />
                    </div>
                  </template>
                </div>

                <!-- Crop button (normal mode only) -->
                <template v-if="editMode !== 'crop'">
                  <button class="crop-btn" @click.stop="toggleRatioPanel" :class="{ active: showRatioPanel }">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                      <path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/>
                    </svg>
                  </button>
                  <div v-if="showRatioPanel" class="ratio-panel" @click.stop @mousedown.stop>
                    <button v-for="r in RATIOS" :key="r.label" class="ratio-chip" @click.stop="selectRatio(r.value)">{{ r.label }}</button>
                  </div>
                </template>

                <!-- Active badge -->
                <div class="card-active-badge">v{{ node.index + 1 }} · 当前</div>

                <!-- Delete button — hidden during crop to avoid accidental deletion -->
                <button v-if="editMode !== 'crop'" class="card-delete" @click.stop="deleteVersionCard(node.id)" title="删除当前版本">×</button>

                <!-- Resize handles — hidden during crop -->
                <template v-if="editMode !== 'crop'">
                  <div class="rh tl" @mousedown.stop="startVersionCardResize(node.id, 'tl', $event)" />
                  <div class="rh tr" @mousedown.stop="startVersionCardResize(node.id, 'tr', $event)" />
                  <div class="rh bl" @mousedown.stop="startVersionCardResize(node.id, 'bl', $event)" />
                  <div class="rh br" @mousedown.stop="startVersionCardResize(node.id, 'br', $event)" />
                </template>
              </div>

              <!-- Thumbnail cards -->
              <div
                v-else
                class="version-card thumb-card"
                :class="{ 'is-selected': selectedVersionIds.includes(node.id) }"
                :style="cardStyle(node)"
                @mousedown.stop="startVersionCardDrag(node.id, $event)"
                @click.stop="toggleSelectVersion(node.id)"
                @dblclick.stop="activateVersionCard(node.id)"
              >
                <img v-if="node.imageUrl" :src="node.imageUrl" class="gen-img" draggable="false" />
                <div class="card-label">v{{ node.index + 1 }}</div>
                <button class="card-delete" @click.stop="deleteVersionCard(node.id)" title="删除此版本">×</button>
                <div class="card-dblclick-hint">双击切换当前</div>

                <!-- Resize handles -->
                <div class="rh tl" @mousedown.stop="startVersionCardResize(node.id, 'tl', $event)" />
                <div class="rh tr" @mousedown.stop="startVersionCardResize(node.id, 'tr', $event)" />
                <div class="rh bl" @mousedown.stop="startVersionCardResize(node.id, 'bl', $event)" />
                <div class="rh br" @mousedown.stop="startVersionCardResize(node.id, 'br', $event)" />
              </div>

            </template>

            <!-- ── Blank placeholder nodes ── -->
            <div
              v-for="(bn, bi) in blankNodes"
              :key="bn.id"
              class="version-card blank-card"
              :class="{ 'drag-over': bn.isDragOver, 'is-selected': selectedBlankIds.includes(bn.id) }"
              :style="cardStyle(bn)"
              @mousedown.stop="startBlankNodeDrag(bi, $event)"
              @click.stop="onBlankNodeClick(bn)"
              @dblclick.stop
              @dragover.prevent="bn.isDragOver = true"
              @dragleave.prevent="bn.isDragOver = false"
              @drop.prevent="onDropToBlankNode(bn, $event)"
            >
              <div class="blank-inner">
                <template v-if="bn.isInitial">
                  <span class="eh-icon">{{ shot.icon }}</span>
                  <span class="eh-text">在左侧输入描述，AI 生成例图</span>
                  <span class="eh-sub">或点击 / 拖拽上传参考图</span>
                  <span class="eh-dbl">双击画布空白处可添加图片框</span>
                </template>
                <template v-else>
                  <span class="blank-icon">+</span>
                  <span class="blank-hint">拖入或点击上传</span>
                </template>
              </div>
              <button class="card-delete" @click.stop="removeBlankNode(bn.id)" title="移除">×</button>

              <!-- Resize handles -->
              <div class="rh tl" @mousedown.stop="startBlankNodeResize(bi, 'tl', $event)" />
              <div class="rh tr" @mousedown.stop="startBlankNodeResize(bi, 'tr', $event)" />
              <div class="rh bl" @mousedown.stop="startBlankNodeResize(bi, 'bl', $event)" />
              <div class="rh br" @mousedown.stop="startBlankNodeResize(bi, 'br', $event)" />
            </div>

            <!-- ── Reference nodes (r-nodes) ── -->
            <div
              v-for="(rn, ri) in refNodes"
              :key="rn.id"
              class="version-card ref-card"
              :class="{ 'is-selected': selectedRefIds.includes(rn.id) }"
              :style="refCardStyle(rn)"
              @mousedown.stop="startRefNodeDrag(ri, $event)"
              @click.stop="toggleSelectRef(rn.id)"
            >
              <div class="img-clip">
                <img
                  v-if="rn.processed_url && rn.status === 'ready'"
                  :src="BASE_URL + rn.processed_url"
                  class="gen-img"
                  draggable="false"
                />
                <img
                  v-else-if="rn.original_url"
                  :src="BASE_URL + rn.original_url"
                  class="gen-img ref-dim"
                  draggable="false"
                />
                <div v-if="rn.status === 'processing'" class="ref-processing-overlay">
                  <span class="ref-spin" />
                </div>
              </div>
              <div class="ref-badge">
                <span v-if="!rn.type" class="ref-badge-label pending">待分类</span>
                <span v-else class="ref-badge-label" :class="rn.type">{{ REF_TYPE_ZH[rn.type] || rn.type }}</span>
              </div>
              <button class="card-delete" @click.stop="deleteRef(rn.id)" title="删除参考图">×</button>
              <div class="rh tl" @mousedown.stop="startRefNodeResize(ri, 'tl', $event)" />
              <div class="rh tr" @mousedown.stop="startRefNodeResize(ri, 'tr', $event)" />
              <div class="rh bl" @mousedown.stop="startRefNodeResize(ri, 'bl', $event)" />
              <div class="rh br" @mousedown.stop="startRefNodeResize(ri, 'br', $event)" />
            </div>

            <input
              ref="uploadFileInput"
              type="file"
              accept="image/*"
              style="display:none"
              @change="onFileInputChange"
            />

          </div>

          <div class="canvas-controls">
            <button class="cc-btn" @click="zoomOut">−</button>
            <span class="zoom-label">{{ Math.round(canvasZoom * 100) }}%</span>
            <button class="cc-btn" @click="zoomIn">+</button>
            <button class="cc-btn fit-btn" @click="fitToView">⊞</button>
          </div>

          <!-- Crop confirm bar -->
          <div v-if="editMode === 'crop'" class="crop-confirm-bar">
            <button class="ccb-cancel" @click="cancelCrop">取消</button>
            <button class="ccb-confirm" :disabled="!inlineCropValid" @click="applyCrop">确认裁剪</button>
          </div>

        </div>

        <!-- Bottom info bar -->
        <div class="info-bar">
          <span class="shot-icon-lg">{{ shot.icon }}</span>
          <div class="shot-meta">
            <span class="shot-title-lg">{{ shot.title }}</span>
            <span class="shot-mood-lg" v-if="shot.mood">{{ shot.mood }}</span>
          </div>
          <span v-if="versions.length > 0" class="version-count">{{ versions.length }} 个版本</span>
        </div>
      </div>

      <!-- Resizer: canvas | right -->
      <div class="resizer" @mousedown.prevent="startResize2('right', $event)" />

      <!-- ── Right: Guide detail panel ── -->
      <div class="detail-col" :style="{ width: rightWidth + 'px' }">
        <div class="col-header">拍摄指南</div>

        <div class="hs-tabs">
          <button
            v-for="hs in hotspots"
            :key="hs.id"
            class="hs-tab"
            :class="{ active: activeId === hs.id }"
            :style="activeId === hs.id ? { color: hs.color, boxShadow: `inset 0 -2px 0 ${hs.color}` } : {}"
            @click="clickHotspot(hs)"
          >{{ hs.label }}</button>
        </div>

        <div class="detail-body">
          <div v-if="layoutNodes.length === 0" class="detail-empty">
            <span>先生成例图<br>再查看拍摄指南</span>
          </div>
          <div v-else-if="!activeId" class="detail-empty">
            <span>点击上方标注点<br>查看指南</span>
          </div>
          <div v-else-if="guideLoading" class="detail-loading">
            <div class="spinner" />
            <span>生成指南中…</span>
          </div>
          <div v-else-if="guide" class="guide-panel">
            <div class="gc-label" :style="{ color: activeHs!.color }">{{ activeHs!.label }}</div>
            <ActionGuide     v-if="activeHs!.guideType === 'action'"     :guide="guide" :color="activeHs!.color" :sketch-url="sketchUrl" />
            <BackgroundGuide v-if="activeHs!.guideType === 'background'" :guide="guide" :color="activeHs!.color" />
            <ExpressionGuide v-if="activeHs!.guideType === 'expression'" :guide="guide" :color="activeHs!.color" />
            <CameraGuide     v-if="activeHs!.guideType === 'camera'"     :guide="guide" :color="activeHs!.color" />
          </div>
        </div>
      </div>

    </div>
  </div>

  <Teleport to="body">
    <div v-if="editMode === 'crop'" class="crop-dim-overlay" />
  </Teleport>

  <Teleport to="body">
    <div v-if="unsavedDialog" class="ud-backdrop">
      <div class="ud-modal">
        <div class="ud-title">有未保存的修改</div>
        <div class="ud-body">图片已编辑但尚未保存，是否保存？</div>
        <div class="ud-actions">
          <button class="ud-btn ud-cancel"  @click="unsavedDialog = null">取消</button>
          <button class="ud-btn ud-discard" @click="unsavedDialog.onDiscard()">不保存</button>
          <button class="ud-btn ud-save"    @click="unsavedDialog.onSave()">保存</button>
        </div>
      </div>
    </div>
  </Teleport>

</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { useApi } from '~/composables/useApi'

definePageMeta({ ssr: false })

const route = useRoute()
const api   = useApi()
const { public: { apiBase: BASE_URL } } = useRuntimeConfig()

const projectId = computed(() =>
  Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
)
const shotId = computed(() =>
  Array.isArray(route.params.shotId) ? route.params.shotId[0] : route.params.shotId
)

// ── Shot data ─────────────────────────────────────────────
const shotData    = ref<any>(null)
const projectData = ref<any>(null)

const shot = computed(() => ({
  title:  shotData.value?.title  ?? '加载中…',
  mood:   shotData.value?.mood   ?? '',
  icon:   '🎬',
  status: shotData.value?.status ?? 'pending',
}))
const isRefined = computed(() => shot.value.status === 'refined')

// ── Inline title rename ───────────────────────────────────
const editingTitle  = ref(false)
const titleDraft    = ref('')
const titleInputRef = ref<HTMLInputElement | null>(null)

function startRenameTitle() {
  titleDraft.value = shotData.value?.title ?? ''
  editingTitle.value = true
  nextTick(() => titleInputRef.value?.select())
}
async function commitRename() {
  const t = titleDraft.value.trim()
  editingTitle.value = false
  if (!t || t === shotData.value?.title) return
  await api.updateShotTitle(projectId.value, shotId.value, t)
  if (shotData.value) shotData.value.title = t
}
function cancelRename() { editingTitle.value = false }

const characterName = computed(() =>
  projectData.value?.character ?? projectData.value?.character_data?.character ?? ''
)

// ── Hotspots ──────────────────────────────────────────────
const hotspots = [
  { id: 'expression', label: '表情', guideType: 'expression' as const, color: '#f472b6' },
  { id: 'pose',       label: '动作', guideType: 'action'     as const, color: '#34d399' },
  { id: 'camera',     label: '构图', guideType: 'camera'     as const, color: '#fbbf24' },
  { id: 'background', label: '背景', guideType: 'background' as const, color: '#60a5fa' },
]
type Hotspot = typeof hotspots[number]

// ── Panel resize ──────────────────────────────────────────
const leftWidth  = ref(280)
const rightWidth = ref(280)
const MIN_W = 180, MAX_W = 520
type ResizeSide = 'left' | 'right'
let resizeSide: ResizeSide | null = null, resizeStartX = 0, resizeStartW = 0

function startResize2(side: ResizeSide, e: MouseEvent) {
  resizeSide = side; resizeStartX = e.clientX
  resizeStartW = side === 'left' ? leftWidth.value : rightWidth.value
  document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none'
}
function onResizeMove(e: MouseEvent) {
  if (!resizeSide) return
  const dx = e.clientX - resizeStartX
  if (resizeSide === 'left') leftWidth.value  = Math.min(MAX_W, Math.max(MIN_W, resizeStartW + dx))
  else                       rightWidth.value = Math.min(MAX_W, Math.max(MIN_W, resizeStartW - dx))
}
function stopResize2() {
  if (!resizeSide) return; resizeSide = null
  document.body.style.cursor = ''; document.body.style.userSelect = ''
}

// ── Canvas state ──────────────────────────────────────────
const canvasWrapRef = ref<HTMLElement | null>(null)
const canvasPan     = ref({ x: 0, y: 0 })
const canvasZoom    = ref(1)

const sceneTransform = computed(() =>
  `translate(${canvasPan.value.x}px, ${canvasPan.value.y}px) scale(${canvasZoom.value})`
)
const gridStyle = computed(() => ({
  backgroundPosition: `${canvasPan.value.x % 32}px ${canvasPan.value.y % 32}px`,
}))

// ── Version data ──────────────────────────────────────────
const CARD_W_ACTIVE = 260, CARD_H_ACTIVE = 346
const CARD_W_THUMB  = 160, CARD_H_THUMB  = 213
const COL_GAP = 100, ROW_GAP = 36

interface VersionNode {
  id: string; parent_ids: string[]; prompt: string; created_at: string; image_url: string | null
}
interface LayoutNode extends VersionNode {
  index: number; x: number; y: number; w: number; h: number; imageUrl: string | null
}

const versions           = ref<VersionNode[]>([])
const activeVersionId    = ref<string | null>(null)
const selectedVersionIds = ref<string[]>([])

// Per-card positions and sizes (user-draggable/resizable, override tree layout)
const cardPositions = ref<Record<string, { x: number; y: number }>>({})
const cardSizes     = ref<Record<string, { w: number; h: number }>>({})

// ── Blank placeholder nodes ───────────────────────────────
interface BlankNode { id: string; x: number; y: number; w: number; h: number; isDragOver: boolean; isInitial?: boolean }
const blankNodes       = ref<BlankNode[]>([])
const selectedBlankIds = ref<string[]>([])
const blankFileInput   = ref<{ [id: string]: HTMLInputElement | null }>({})

// ── Reference nodes (r-nodes) ─────────────────────────────
interface RefNode {
  id: string; type: string | null; status: string; created_at: string
  original_url: string; processed_url?: string | null; processed_text?: string
  x: number; y: number; w: number; h: number
}
const REF_TYPE_ZH: Record<string, string> = {
  pose: '动作', background: '背景', weapon: '武器', costume: '服装', lighting: '打光', expression: '表情',
}
const REF_W = 180, REF_H = 240
const refNodes       = ref<RefNode[]>([])
const selectedRefIds = ref<string[]>([])
const refFileInput   = ref<HTMLInputElement | null>(null)

function refCardStyle(rn: RefNode) {
  return {
    left: `${rn.x}px`, top: `${rn.y}px`,
    width: `${rn.w}px`, height: `${rn.h}px`,
  }
}

async function loadRefs() {
  try {
    const data = await api.listShotRefs(projectId.value, shotId.value)
    refNodes.value = data.map((r, i) => ({
      ...r,
      x: refNodes.value.find(e => e.id === r.id)?.x ?? (CARD_W_ACTIVE + COL_GAP + i * (REF_W + 20)),
      y: refNodes.value.find(e => e.id === r.id)?.y ?? (CARD_H_ACTIVE + ROW_GAP * 2),
      w: refNodes.value.find(e => e.id === r.id)?.w ?? REF_W,
      h: refNodes.value.find(e => e.id === r.id)?.h ?? REF_H,
    }))
  } catch (e) { console.error('loadRefs', e) }
}

function triggerRefUpload() { refFileInput.value?.click() }

async function onRefFileInputChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  ;(e.target as HTMLInputElement).value = ''
  try {
    const entry = await api.uploadShotRef(projectId.value, shotId.value, file)
    const placed: RefNode = {
      ...entry, original_url: `/projects/${projectId.value}/shots/${shotId.value}/refs/${entry.id}/original`,
      processed_url: null,
      x: (CARD_W_ACTIVE + COL_GAP) + refNodes.value.length * (REF_W + 20),
      y: CARD_H_ACTIVE + ROW_GAP * 2,
      w: REF_W, h: REF_H,
    }
    refNodes.value.push(placed)
    // Tell the AI a new ref was uploaded so it can ask for the type
    chatInput.value = `我上传了一张参考图（ref_id=${entry.id}），请问我想参考什么方面`
  } catch (e) { console.error('uploadShotRef', e) }
}

function toggleSelectRef(id: string) {
  const idx = selectedRefIds.value.indexOf(id)
  if (idx >= 0) selectedRefIds.value.splice(idx, 1)
  else selectedRefIds.value.push(id)
}

async function deleteRef(id: string) {
  try {
    await api.deleteShotRef(projectId.value, shotId.value, id)
    refNodes.value = refNodes.value.filter(r => r.id !== id)
    selectedRefIds.value = selectedRefIds.value.filter(s => s !== id)
  } catch (e) { console.error('deleteRef', e) }
}

let refDragState: { ri: number; sx: number; sy: number; ox: number; oy: number } | null = null
function startRefNodeDrag(ri: number, e: MouseEvent) {
  const rn = refNodes.value[ri]
  refDragState = { ri, sx: e.clientX, sy: e.clientY, ox: rn.x, oy: rn.y }
}

function startRefNodeResize(ri: number, corner: Corner, e: MouseEvent) {
  const rn = refNodes.value[ri]
  startResize(corner,
    () => ({ x: rn.x, y: rn.y, w: rn.w, h: rn.h }),
    s  => { refNodes.value[ri] = { ...refNodes.value[ri], ...s } },
    e,
  )
}

// Poll r-nodes that are processing until they become ready
let refPollTimer: ReturnType<typeof setInterval> | null = null
function startRefPoll() {
  if (refPollTimer) return
  refPollTimer = setInterval(async () => {
    const processing = refNodes.value.some(r => r.status === 'processing')
    if (!processing) { clearInterval(refPollTimer!); refPollTimer = null; return }
    await loadRefs()
  }, 4000)
}
watch(refNodes, (nodes) => {
  if (nodes.some(r => r.status === 'processing')) startRefPoll()
}, { deep: true })

// ── Pure tree layout (for initial positioning) ────────────
function computeDefaultLayout(
  versionList: VersionNode[],
  activeId: string | null,
): Record<string, { x: number; y: number; w: number; h: number }> {
  if (!versionList.length) return {}
  const depthMap: Record<string, number> = {}
  for (const v of versionList) {
    if (!v.parent_ids.length) depthMap[v.id] = 0
  }
  for (const v of versionList) {
    if (v.parent_ids.length) {
      depthMap[v.id] = Math.max(...v.parent_ids.map(pid => (depthMap[pid] ?? 0) + 1))
    }
  }
  const columns: Record<number, string[]> = {}
  for (const [id, d] of Object.entries(depthMap)) {
    (columns[d] = columns[d] || []).push(id)
  }
  const positions: Record<string, { x: number; y: number; w: number; h: number }> = {}
  for (const colStr of Object.keys(columns).sort((a, b) => Number(a) - Number(b))) {
    const col  = Number(colStr)
    const ids  = columns[col]
    const totalH = ids.reduce((s, id) => {
      return s + (id === activeId ? CARD_H_ACTIVE : CARD_H_THUMB) + ROW_GAP
    }, -ROW_GAP)
    let y = -totalH / 2
    const x = col * (CARD_W_ACTIVE + COL_GAP)
    for (const id of ids) {
      const w = id === activeId ? CARD_W_ACTIVE : CARD_W_THUMB
      const h = id === activeId ? CARD_H_ACTIVE : CARD_H_THUMB
      positions[id] = { x, y, w, h }
      y += h + ROW_GAP
    }
  }
  return positions
}

// Initialize card positions/sizes when new versions arrive
watch([versions, activeVersionId], () => {
  const defaults = computeDefaultLayout(versions.value, activeVersionId.value)
  for (const [id, def] of Object.entries(defaults)) {
    if (!(id in cardPositions.value)) cardPositions.value[id] = { x: def.x, y: def.y }
    if (!(id in cardSizes.value))     cardSizes.value[id]     = { w: def.w, h: def.h }
  }
  // Auto-manage the initial blank node (same size as active card)
  if (versions.value.length === 0) {
    if (!blankNodes.value.some(b => b.isInitial)) {
      blankNodes.value.push({ id: 'blank-initial', x: 0, y: 0, w: CARD_W_ACTIVE, h: CARD_H_ACTIVE, isDragOver: false, isInitial: true })
    }
  } else {
    blankNodes.value = blankNodes.value.filter(b => !b.isInitial)
  }
}, { deep: false })

// layoutNodes: versions with user-overridden positions/sizes
const layoutNodes = computed((): LayoutNode[] =>
  versions.value.map((v, i) => {
    const pos  = cardPositions.value[v.id] ?? { x: 0, y: 0 }
    const def  = v.id === activeVersionId.value
      ? { w: CARD_W_ACTIVE, h: CARD_H_ACTIVE }
      : { w: CARD_W_THUMB,  h: CARD_H_THUMB  }
    const size = cardSizes.value[v.id] ?? def
    return {
      ...v, index: i,
      x: pos.x, y: pos.y, w: size.w, h: size.h,
      imageUrl: v.image_url ? BASE_URL + v.image_url + '?t=' + (v as any)._ts : null,
    }
  })
)

// All draggable nodes (for fitToView bounding box)
const allNodes = computed(() => [
  ...layoutNodes.value,
  ...blankNodes.value,
])

// ── Edges ──────────────────────────────────────────────────
const treeEdges = computed(() => {
  const edges: { id: string; from: string; to: string }[] = []
  for (const v of versions.value)
    for (const pid of v.parent_ids)
      edges.push({ id: `${pid}→${v.id}`, from: pid, to: v.id })
  return edges
})

function edgePath(edge: { from: string; to: string }): string {
  const nm = Object.fromEntries(layoutNodes.value.map(n => [n.id, n]))
  const f  = nm[edge.from], t = nm[edge.to]
  if (!f || !t) return ''
  const x1 = f.x + f.w, y1 = f.y + f.h / 2
  const x2 = t.x,       y2 = t.y + t.h / 2
  const cx = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`
}

// ── Card style helper ──────────────────────────────────────
function cardStyle(node: { x: number; y: number; w: number; h: number }) {
  return { left: node.x + 'px', top: node.y + 'px', width: node.w + 'px', height: node.h + 'px' }
}

// ── Card drag ─────────────────────────────────────────────
function startDrag(
  getPos: () => { x: number; y: number },
  setPos: (p: { x: number; y: number }) => void,
  e: MouseEvent,
) {
  const sx = e.clientX, sy = e.clientY
  const sp = { ...getPos() }
  const onMove = (me: MouseEvent) => setPos({
    x: sp.x + (me.clientX - sx) / canvasZoom.value,
    y: sp.y + (me.clientY - sy) / canvasZoom.value,
  })
  const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

function startVersionCardDrag(id: string, e: MouseEvent) {
  if (e.button !== 0) return
  startDrag(
    () => cardPositions.value[id] ?? { x: 0, y: 0 },
    p  => { cardPositions.value = { ...cardPositions.value, [id]: p } },
    e,
  )
}

function startBlankNodeDrag(bi: number, e: MouseEvent) {
  if (e.button !== 0) return
  startDrag(
    () => ({ x: blankNodes.value[bi].x, y: blankNodes.value[bi].y }),
    p  => { blankNodes.value[bi].x = p.x; blankNodes.value[bi].y = p.y },
    e,
  )
}

// ── Card resize ───────────────────────────────────────────
type Corner = 'tl' | 'tr' | 'bl' | 'br'
const MIN_CARD_W = 120, MIN_CARD_H = 160

function startResize(
  corner: Corner,
  getState: () => { x: number; y: number; w: number; h: number },
  setState: (s: { x: number; y: number; w: number; h: number }) => void,
  e: MouseEvent,
  lockRatio = false,
) {
  e.stopPropagation()
  const sx = e.clientX, sy = e.clientY
  const s  = { ...getState() }
  const ratio = s.h / s.w   // locked at drag start

  const onMove = (me: MouseEvent) => {
    const dx = (me.clientX - sx) / canvasZoom.value
    const dy = (me.clientY - sy) / canvasZoom.value
    let { x, y, w, h } = s

    if (lockRatio) {
      // Bottom corners: width drives → height follows
      // Top corners: height drives (drag up/down) → width follows
      if (corner === 'br') {
        w = Math.max(MIN_CARD_W, s.w + dx)
        h = Math.max(MIN_CARD_H, Math.round(w * ratio))
        w = Math.round(h / ratio)
      } else if (corner === 'bl') {
        w = Math.max(MIN_CARD_W, s.w - dx)
        h = Math.max(MIN_CARD_H, Math.round(w * ratio))
        w = Math.round(h / ratio)
        x = s.x + s.w - w
      } else if (corner === 'tr') {
        h = Math.max(MIN_CARD_H, s.h - dy)
        w = Math.max(MIN_CARD_W, Math.round(h / ratio))
        h = Math.round(w * ratio)
        y = s.y + s.h - h
      } else if (corner === 'tl') {
        h = Math.max(MIN_CARD_H, s.h - dy)
        w = Math.max(MIN_CARD_W, Math.round(h / ratio))
        h = Math.round(w * ratio)
        x = s.x + s.w - w
        y = s.y + s.h - h
      }
    } else {
      // Free resize (blank nodes)
      if (corner === 'br') { w = Math.max(MIN_CARD_W, s.w + dx); h = Math.max(MIN_CARD_H, s.h + dy) }
      if (corner === 'bl') { w = Math.max(MIN_CARD_W, s.w - dx); x = s.x + s.w - w; h = Math.max(MIN_CARD_H, s.h + dy) }
      if (corner === 'tr') { w = Math.max(MIN_CARD_W, s.w + dx); h = Math.max(MIN_CARD_H, s.h - dy); y = s.y + s.h - h }
      if (corner === 'tl') { w = Math.max(MIN_CARD_W, s.w - dx); x = s.x + s.w - w; h = Math.max(MIN_CARD_H, s.h - dy); y = s.y + s.h - h }
    }
    setState({ x, y, w, h })
  }
  const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

function startVersionCardResize(id: string, corner: Corner, e: MouseEvent) {
  startResize(
    corner,
    () => {
      const n = layoutNodes.value.find(n => n.id === id)!
      return { x: n.x, y: n.y, w: n.w, h: n.h }
    },
    s => {
      cardPositions.value = { ...cardPositions.value, [id]: { x: s.x, y: s.y } }
      cardSizes.value     = { ...cardSizes.value,     [id]: { w: s.w, h: s.h } }
    },
    e,
    true,  // lock aspect ratio
  )
}

function startBlankNodeResize(bi: number, corner: Corner, e: MouseEvent) {
  startResize(
    corner,
    () => { const b = blankNodes.value[bi]; return { x: b.x, y: b.y, w: b.w, h: b.h } },
    s  => { blankNodes.value[bi] = { ...blankNodes.value[bi], ...s } },
    e,
  )
}

// ── Version CRUD ──────────────────────────────────────────
async function loadVersions() {
  try {
    const [data, shot] = await Promise.all([
      api.listVersions(projectId.value, shotId.value),
      api.getShot(projectId.value, shotId.value),
    ])
    // Set both synchronously so Vue batches them into one watcher flush —
    // activeVersionId must be correct when the versions watch fires.
    activeVersionId.value = shot.active_version_id ?? (data[data.length - 1]?.id ?? null)
    versions.value = data.map(v => ({ ...v, _ts: Date.now() } as any))
  } catch (e) { console.error('loadVersions', e) }
}

function toggleSelectVersion(id: string) {
  const idx = selectedVersionIds.value.indexOf(id)
  if (idx >= 0) selectedVersionIds.value.splice(idx, 1)
  else           selectedVersionIds.value.push(id)
}

async function activateVersionCard(id: string) {
  await api.activateVersion(projectId.value, shotId.value, id)
  activeVersionId.value = id
  selectedVersionIds.value = []
  closePopup()
  versions.value = versions.value.map(v => ({ ...v, _ts: Date.now() } as any))
}

async function deleteVersionCard(id: string) {
  try {
    await api.deleteVersion(projectId.value, shotId.value, id)
    delete cardPositions.value[id]
    delete cardSizes.value[id]
    selectedVersionIds.value = selectedVersionIds.value.filter(s => s !== id)
    if (id === activeVersionId.value) {
      editHistory.value  = []
      historyIndex.value = -1
    }
    await loadVersions()
  } catch (e) { console.error('deleteVersion', e) }
}

// ── Blank node CRUD ───────────────────────────────────────
function onCanvasDblClick(e: MouseEvent) {
  const wrap = canvasWrapRef.value
  if (!wrap) return
  const rect = wrap.getBoundingClientRect()
  const x = (e.clientX - rect.left  - canvasPan.value.x) / canvasZoom.value - CARD_W_THUMB / 2
  const y = (e.clientY - rect.top   - canvasPan.value.y) / canvasZoom.value - CARD_H_THUMB / 2
  blankNodes.value.push({ id: `blank-${Date.now()}`, x, y, w: CARD_W_THUMB, h: CARD_H_THUMB, isDragOver: false })
}

function removeBlankNode(id: string) {
  blankNodes.value = blankNodes.value.filter(b => b.id !== id)
  selectedBlankIds.value = selectedBlankIds.value.filter(s => s !== id)
}

function onBlankNodeClick(bn: BlankNode) {
  const input = document.createElement('input')
  input.type = 'file'; input.accept = 'image/*'
  input.onchange = async (ev) => {
    const file = (ev.target as HTMLInputElement).files?.[0]
    if (!file) return
    await _uploadToBlankSlot(bn, file)
  }
  input.click()
}

async function onDropToBlankNode(bn: BlankNode, e: DragEvent) {
  bn.isDragOver = false
  const file = e.dataTransfer?.files[0]
  if (file?.type.startsWith('image/')) await _uploadToBlankSlot(bn, file)
}

async function _uploadToBlankSlot(bn: BlankNode, file: File) {
  const savedPos = { x: bn.x, y: bn.y }
  const savedId  = bn.id
  blankNodes.value = blankNodes.value.filter(b => b.id !== savedId)
  selectedBlankIds.value = selectedBlankIds.value.filter(s => s !== savedId)

  if (versions.value.length === 0) {
    // No versions yet → first upload becomes v1
    const blob = new Blob([await file.arrayBuffer()], { type: file.type })
    await api.saveImage(projectId.value, shotId.value, blob)
    await loadVersions()
    const newest = versions.value[versions.value.length - 1]
    if (newest && !(newest.id in cardPositions.value)) {
      cardPositions.value = { ...cardPositions.value, [newest.id]: savedPos }
    }
  } else {
    // Versions already exist → treat upload as r-node reference
    const entry = await api.uploadShotRef(projectId.value, shotId.value, file)
    const placed: RefNode = {
      ...entry,
      original_url: `/projects/${projectId.value}/shots/${shotId.value}/refs/${entry.id}/original`,
      processed_url: null,
      x: savedPos.x,
      y: savedPos.y,
      w: REF_W,
      h: REF_H,
    }
    refNodes.value.push(placed)
    chatInput.value = `我上传了一张参考图（ref_id=${entry.id}），请问我想参考什么方面`
  }
}

// ── img ref: active card geometry (for crop math) ─────────
const img = computed(() => {
  const active = layoutNodes.value.find(n => n.id === activeVersionId.value)
  if (!active) return null
  return { x: active.x, y: active.y, w: active.w, h: active.h }
})

// ── Edit history (crop) ───────────────────────────────────
type HistoryEntry = { url: string; imgState: { x: number; y: number; w: number; h: number } }
const editHistory  = ref<HistoryEntry[]>([])
const historyIndex = ref(-1)

const currentDisplayUrl = computed((): string => {
  if (historyIndex.value >= 0 && editHistory.value.length > 0)
    return editHistory.value[historyIndex.value].url
  const active = layoutNodes.value.find(n => n.id === activeVersionId.value)
  return active?.imageUrl ?? ''
})

const canUndo           = computed(() => historyIndex.value > 0)
const canRedo           = computed(() => historyIndex.value < editHistory.value.length - 1)
const hasUnsavedChanges = computed(() => historyIndex.value > 0)

function pushHistory(url: string, imgState: { x: number; y: number; w: number; h: number }) {
  editHistory.value = editHistory.value.slice(0, historyIndex.value + 1)
  editHistory.value.push({ url, imgState: { ...imgState } })
  historyIndex.value++
}

async function initEditHistory(imageUrl: string) {
  let snapImg = img.value ? { ...img.value } : { x: 0, y: 0, w: CARD_W_ACTIVE, h: CARD_H_ACTIVE }
  try {
    const blob    = await fetch(imageUrl, { cache: 'reload' }).then(r => r.blob())
    const dataUrl = await new Promise<string>(res => {
      const reader = new FileReader()
      reader.onload = ev => res(ev.target!.result as string)
      reader.readAsDataURL(blob)
    })
    // If the card is still at default size (no custom size yet), auto-size to the
    // image's natural aspect ratio so uploaded/generated images don't get force-cropped.
    if (snapImg.w === CARD_W_ACTIVE && snapImg.h === CARD_H_ACTIVE && activeVersionId.value) {
      const nat = await new Promise<{ w: number; h: number }>(resolve => {
        const el = new window.Image(); el.onload = () => resolve({ w: el.naturalWidth, h: el.naturalHeight }); el.src = dataUrl
      })
      const scale = Math.min(CARD_W_ACTIVE / nat.w, CARD_H_ACTIVE / nat.h)
      snapImg = { ...snapImg, w: Math.round(nat.w * scale), h: Math.round(nat.h * scale) }
      cardSizes.value = { ...cardSizes.value, [activeVersionId.value]: { w: snapImg.w, h: snapImg.h } }
    }
    editHistory.value  = [{ url: dataUrl, imgState: snapImg }]
    historyIndex.value = 0
  } catch {
    editHistory.value  = [{ url: imageUrl, imgState: snapImg }]
    historyIndex.value = 0
  }
}

watch(activeVersionId, async (id, oldId) => {
  // When switching away from a version that has unsaved crop edits,
  // reset its card size to the pre-crop dimensions so the server image
  // (uncropped) fits correctly in the card frame.
  if (oldId && editHistory.value.length > 0 && historyIndex.value > 0) {
    const { w, h } = editHistory.value[0].imgState
    cardSizes.value = { ...cardSizes.value, [oldId]: { w, h } }
  }
  if (!id) return
  editMode.value = null; inlineCrop.value = null; showRatioPanel.value = false
  editHistory.value  = []
  historyIndex.value = -1
  const active = layoutNodes.value.find(n => n.id === id)
  if (active?.imageUrl) await initEditHistory(active.imageUrl)
})

function undo() { if (canUndo.value) historyIndex.value-- }
function redo() { if (canRedo.value) historyIndex.value++ }
// Restore card size when stepping through history (undo/redo after crop)
watch(historyIndex, (idx) => {
  if (idx >= 0 && editHistory.value[idx] && activeVersionId.value) {
    const { w, h } = editHistory.value[idx].imgState
    cardSizes.value = { ...cardSizes.value, [activeVersionId.value]: { w, h } }
  }
})

// ── Crop tool ─────────────────────────────────────────────
const RATIOS = [
  { label: '16:9', value: 16/9 }, { label: '3:2',  value: 3/2  },
  { label: '4:3',  value: 4/3  }, { label: '1:1',  value: 1    },
  { label: '3:4',  value: 3/4  }, { label: '2:3',  value: 2/3  },
  { label: '9:16', value: 9/16 },
]
const editMode       = ref<null | 'crop'>(null)
const showRatioPanel = ref(false)
const cropRatio      = ref(1)
const inlineCrop     = ref<{ x: number; y: number; w: number; h: number } | null>(null)
const inlineCropValid = computed(() => inlineCrop.value !== null && inlineCrop.value.w >= 4 && inlineCrop.value.h >= 4)

function toggleRatioPanel() { showRatioPanel.value = !showRatioPanel.value }
function selectRatio(ratio: number) {
  cropRatio.value = ratio; showRatioPanel.value = false; editMode.value = 'crop'
  if (!img.value) return
  const { w: iw, h: ih } = img.value
  let cw = iw, ch = cw / ratio
  if (ch > ih) { ch = ih; cw = ch * ratio }
  inlineCrop.value = { x: (iw - cw) / 2, y: (ih - ch) / 2, w: cw, h: ch }
}
function cancelCrop() { editMode.value = null; inlineCrop.value = null; showRatioPanel.value = false }

function eventToImgCoords(e: MouseEvent, clamp = false) {
  if (!img.value) return { x: 0, y: 0 }
  const x = (e.clientX - canvasPan.value.x) / canvasZoom.value - img.value.x
  const y = (e.clientY - canvasPan.value.y) / canvasZoom.value - img.value.y
  if (!clamp) return { x, y }
  return { x: Math.max(0, Math.min(x, img.value.w)), y: Math.max(0, Math.min(y, img.value.h)) }
}
function clampCrop(c: { x: number; y: number; w: number; h: number }) {
  if (!img.value) return c
  const x = Math.max(0, Math.min(c.x, img.value.w - c.w))
  const y = Math.max(0, Math.min(c.y, img.value.h - c.h))
  return { x, y, w: Math.max(8, Math.min(c.w, img.value.w - x)), h: Math.max(8, Math.min(c.h, img.value.h - y)) }
}

function onCropLayerDown(e: MouseEvent) {
  // Click outside the crop rect → re-center it (ratio-locked) at click point, then drag
  const pos = eventToImgCoords(e, true)
  if (inlineCrop.value) {
    const { w, h } = inlineCrop.value
    inlineCrop.value = clampCrop({ x: pos.x - w / 2, y: pos.y - h / 2, w, h })
  }
  const snap = { ...inlineCrop.value! }
  const onMove = (me: MouseEvent) => {
    const c = eventToImgCoords(me)
    inlineCrop.value = clampCrop({ ...snap, x: snap.x + c.x - pos.x, y: snap.y + c.y - pos.y })
  }
  const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
}
function onCropRectDown(e: MouseEvent) {
  const start = eventToImgCoords(e); const snap = { ...inlineCrop.value! }
  const onMove = (me: MouseEvent) => {
    const c = eventToImgCoords(me)
    inlineCrop.value = clampCrop({ ...snap, x: snap.x + c.x - start.x, y: snap.y + c.y - start.y })
  }
  const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
}
function startCropHandle(handle: string, e: MouseEvent) {
  const start = eventToImgCoords(e); const snap = { ...inlineCrop.value! }
  const ratio = cropRatio.value; const MIN = 20; const iw = img.value!.w; const ih = img.value!.h
  const onMove = (me: MouseEvent) => {
    const curr = eventToImgCoords(me); const dx = curr.x - start.x
    const rawDelta = handle === 'br' || handle === 'tr' ? dx : -dx
    let newW = Math.max(MIN, snap.w + rawDelta); let newH = newW / ratio
    if ((handle === 'br' || handle === 'tr') && snap.x + newW > iw) { newW = iw - snap.x; newH = newW / ratio }
    if ((handle === 'tl' || handle === 'bl') && snap.x + snap.w - newW < 0) { newW = snap.x + snap.w; newH = newW / ratio }
    if (newH > ih) { newH = ih; newW = newH * ratio }
    let newX = snap.x, newY = snap.y
    if (handle === 'tl') { newX = snap.x + snap.w - newW; newY = snap.y + snap.h - newH }
    if (handle === 'tr') { newY = snap.y + snap.h - newH }
    if (handle === 'bl') { newX = snap.x + snap.w - newW }
    inlineCrop.value = clampCrop({ x: newX, y: newY, w: newW, h: newH })
  }
  const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove); window.addEventListener('mouseup', onUp)
}

async function applyCrop() {
  const crop = inlineCrop.value; if (!crop || !img.value) return
  const el = new window.Image()
  await new Promise<void>(res => { el.onload = () => res(); el.src = currentDisplayUrl.value })
  const canvas = document.createElement('canvas')
  const sx = el.naturalWidth / img.value.w; const sy = el.naturalHeight / img.value.h
  canvas.width = Math.round(crop.w * sx); canvas.height = Math.round(crop.h * sy)
  canvas.getContext('2d')!.drawImage(el, crop.x * sx, crop.y * sy, crop.w * sx, crop.h * sy, 0, 0, canvas.width, canvas.height)
  // Resize the card to match the crop ratio, fitting within CARD_W_ACTIVE × CARD_H_ACTIVE
  if (activeVersionId.value) {
    const scale = Math.min(CARD_W_ACTIVE / crop.w, CARD_H_ACTIVE / crop.h)
    cardSizes.value = { ...cardSizes.value, [activeVersionId.value]: { w: Math.round(crop.w * scale), h: Math.round(crop.h * scale) } }
  }
  pushHistory(canvas.toDataURL('image/png'), { ...img.value })
  editMode.value = null; inlineCrop.value = null; showRatioPanel.value = false
}

async function saveImage() {
  if (!currentDisplayUrl.value || !hasUnsavedChanges.value) return
  const blob = await fetch(currentDisplayUrl.value).then(r => r.blob())
  // Crop saves are children of the version they were cropped from
  await api.saveImage(projectId.value, shotId.value, blob, activeVersionId.value ?? undefined)
  await loadVersions()
  editHistory.value = []; historyIndex.value = -1
}

// ── Unsaved guard ─────────────────────────────────────────
const unsavedDialog = ref<{ onSave: () => void; onDiscard: () => void } | null>(null)
function guardAction(action: () => void) {
  if (!hasUnsavedChanges.value) { action(); return }
  unsavedDialog.value = {
    onSave:    async () => { await saveImage(); unsavedDialog.value = null; action() },
    onDiscard: ()      => { unsavedDialog.value = null; action() },
  }
}
function goBack() { guardAction(() => navigateTo(`/projects/${route.params.id}`)) }
function onBeforeUnload(e: BeforeUnloadEvent) {
  if (hasUnsavedChanges.value) { e.preventDefault(); e.returnValue = '' }
}
function onKeyDown(e: KeyboardEvent) {
  if (!(e.metaKey || e.ctrlKey)) return
  if (e.key === 's') { e.preventDefault(); saveImage() }
  if (e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo() }
  if (e.key === 'z' &&  e.shiftKey) { e.preventDefault(); redo() }
  if (e.key === 'y')                { e.preventDefault(); redo() }
}
onBeforeRouteLeave(() => { if (hasUnsavedChanges.value && !unsavedDialog.value) return false })

// ── Guide panel ───────────────────────────────────────────
const activeId     = ref<string | null>(null)
const guideLoading = ref(false)
const guide        = ref<any>(null)
const sketchUrl    = ref<string | null>(null)
const activeHs     = computed(() => hotspots.find(h => h.id === activeId.value) ?? null)

async function clickHotspot(hs: Hotspot) {
  if (activeId.value === hs.id) { closePopup(); return }
  activeId.value = hs.id; guide.value = null; sketchUrl.value = null; guideLoading.value = true
  try {
    let result = await api.getGuide(projectId.value, shotId.value, hs.guideType)
    if (!result) result = await api.generateGuide(projectId.value, shotId.value, hs.guideType)
    guide.value     = result?.guide ?? null
    sketchUrl.value = result?.sketch_url ? BASE_URL + result.sketch_url : null
  } catch (e) { console.error('Guide error', e) }
  guideLoading.value = false
}
function closePopup() { activeId.value = null; guide.value = null; sketchUrl.value = null }

// ── Pan ───────────────────────────────────────────────────
type DragMode = null | 'pan'
const dragMode  = ref<DragMode>(null)
const dragStart = ref({ mx: 0, my: 0, panX: 0, panY: 0 })

function startPan(e: MouseEvent) {
  if (e.button !== 0) return
  if (editMode.value !== null) { editMode.value = null; inlineCrop.value = null }
  showRatioPanel.value = false; closePopup()
  dragMode.value  = 'pan'
  dragStart.value = { mx: e.clientX, my: e.clientY, panX: canvasPan.value.x, panY: canvasPan.value.y }
}
function onWindowMouseMove(e: MouseEvent) {
  if (dragMode.value === 'pan') {
    canvasPan.value = {
      x: dragStart.value.panX + e.clientX - dragStart.value.mx,
      y: dragStart.value.panY + e.clientY - dragStart.value.my,
    }
  }
  if (refDragState) {
    const { ri, sx, sy, ox, oy } = refDragState
    refNodes.value[ri].x = ox + (e.clientX - sx) / canvasZoom.value
    refNodes.value[ri].y = oy + (e.clientY - sy) / canvasZoom.value
  }
}
function onWindowMouseUp() { dragMode.value = null; refDragState = null }

// ── Upload ─────────────────────────────────────────────────
const uploadFileInput = ref<HTMLInputElement | null>(null)

function triggerUpload() { uploadFileInput.value?.click() }
function onFileInputChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (file) uploadUserImage(file)
  ;(e.target as HTMLInputElement).value = ''
}
async function uploadUserImage(file: File) {
  const blob = new Blob([await file.arrayBuffer()], { type: file.type })
  await api.saveImage(projectId.value, shotId.value, blob)
  await loadVersions()
}

// ── Zoom ──────────────────────────────────────────────────
function onWheel(e: WheelEvent) {
  const wrap = canvasWrapRef.value; if (!wrap) return
  const rect  = wrap.getBoundingClientRect()
  const mx = e.clientX - rect.left, my = e.clientY - rect.top
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
  const newZ   = Math.max(0.08, Math.min(6, canvasZoom.value * factor))
  const ratio  = newZ / canvasZoom.value
  canvasPan.value  = { x: mx - (mx - canvasPan.value.x) * ratio, y: my - (my - canvasPan.value.y) * ratio }
  canvasZoom.value = newZ
}
function zoomIn()  { applyZoomCentered(1.25) }
function zoomOut() { applyZoomCentered(1 / 1.25) }
function applyZoomCentered(factor: number) {
  const wrap = canvasWrapRef.value; if (!wrap) return
  const mx = wrap.clientWidth / 2, my = wrap.clientHeight / 2
  const newZ  = Math.max(0.08, Math.min(6, canvasZoom.value * factor))
  const ratio = newZ / canvasZoom.value
  canvasPan.value  = { x: mx - (mx - canvasPan.value.x) * ratio, y: my - (my - canvasPan.value.y) * ratio }
  canvasZoom.value = newZ
}
function fitToView() {
  const wrap = canvasWrapRef.value; if (!wrap) return
  if (!allNodes.value.length) {
    canvasPan.value = { x: (wrap.clientWidth - CARD_W_ACTIVE) / 2, y: (wrap.clientHeight - CARD_H_ACTIVE) / 2 }
    canvasZoom.value = 1; return
  }
  const pad = 60
  const xs  = allNodes.value.map(n => n.x),   ys  = allNodes.value.map(n => n.y)
  const x2s = allNodes.value.map(n => n.x + n.w), y2s = allNodes.value.map(n => n.y + n.h)
  const minX = Math.min(...xs), minY = Math.min(...ys)
  const maxX = Math.max(...x2s), maxY = Math.max(...y2s)
  const newZ = Math.min((wrap.clientWidth - pad*2) / (maxX - minX), (wrap.clientHeight - pad*2) / (maxY - minY), 1.5)
  canvasZoom.value = newZ
  canvasPan.value  = { x: wrap.clientWidth/2 - ((minX+maxX)/2)*newZ, y: wrap.clientHeight/2 - ((minY+maxY)/2)*newZ }
}

// ── Generation polling ────────────────────────────────────
const generating = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null
function stopPolling() { if (pollTimer) { clearTimeout(pollTimer); pollTimer = null } }

async function pollUntilDone() {
  stopPolling()
  try {
    const s = await api.getShot(projectId.value, shotId.value)
    if (s.status === 'done' && s.image_url) {
      generating.value = false
      await loadVersions(); await refreshHistory()
      nextTick(fitToView)
    } else if (s.status === 'error') {
      generating.value = false; await refreshHistory()
    } else {
      pollTimer = setTimeout(pollUntilDone, 3000)
    }
  } catch { pollTimer = setTimeout(pollUntilDone, 5000) }
}

// ── AI chat ───────────────────────────────────────────────
const aiMsgContainer = ref<HTMLElement | null>(null)
const chatInput      = ref('')
const chatLoading    = ref(false)
const aiMessages     = ref<{ role: string; text: string }[]>([])

async function refreshHistory() {
  const s = await api.getShot(projectId.value, shotId.value)
  aiMessages.value = s.chat_history ?? []
  await nextTick()
  if (aiMsgContainer.value) aiMsgContainer.value.scrollTop = aiMsgContainer.value.scrollHeight
}

async function refineShot() {
  await api.updateShotStatus(projectId.value, shotId.value, 'refined')
  if (shotData.value) shotData.value.status = 'refined'
}
async function unlockShot() {
  await api.updateShotStatus(projectId.value, shotId.value, 'done')
  if (shotData.value) shotData.value.status = 'done'
}

async function sendChat() {
  const text = chatInput.value.trim()
  if (!text || chatLoading.value) return
  chatInput.value = ''
  aiMessages.value.push({ role: 'user', text })
  chatLoading.value = true
  await nextTick()
  if (aiMsgContainer.value) aiMsgContainer.value.scrollTop = aiMsgContainer.value.scrollHeight
  try {
    const { reply, generating: gen } = await api.shotChat(
      projectId.value, shotId.value, text, selectedVersionIds.value, selectedRefIds.value,
    )
    if (reply) aiMessages.value.push({ role: 'agent', text: reply })
    if (gen) { generating.value = true; pollUntilDone() }
  } catch {
    aiMessages.value.push({ role: 'agent', text: '出了点问题，请稍后重试。' })
  }
  chatLoading.value = false
  await nextTick()
  if (aiMsgContainer.value) aiMsgContainer.value.scrollTop = aiMsgContainer.value.scrollHeight
}

// ── Lifecycle ─────────────────────────────────────────────
onMounted(async () => {
  window.addEventListener('mousemove',    onWindowMouseMove)
  window.addEventListener('mousemove',    onResizeMove)
  window.addEventListener('mouseup',      onWindowMouseUp)
  window.addEventListener('mouseup',      stopResize2)
  window.addEventListener('keydown',      onKeyDown)
  window.addEventListener('beforeunload', onBeforeUnload)
  try {
    projectData.value = await api.getProject(projectId.value)
    shotData.value    = await api.getShot(projectId.value, shotId.value)
    aiMessages.value  = shotData.value?.chat_history ?? []
    if (shotData.value?.status === 'generating') { generating.value = true; pollUntilDone() }
    await loadVersions()
    await loadRefs()
    nextTick(fitToView)
  } catch (e) { console.error('mount error', e) }
})

onUnmounted(() => {
  window.removeEventListener('mousemove',    onWindowMouseMove)
  window.removeEventListener('mousemove',    onResizeMove)
  window.removeEventListener('mouseup',      onWindowMouseUp)
  window.removeEventListener('mouseup',      stopResize2)
  window.removeEventListener('keydown',      onKeyDown)
  window.removeEventListener('beforeunload', onBeforeUnload)
  stopPolling()
})
</script>

<style scoped>
.shot-page { height: 100vh; background: var(--bg); display: flex; flex-direction: column; overflow: hidden; }

/* ── Top bar ── */
.top-bar { height: 48px; background: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 24px; flex-shrink: 0; }
.breadcrumb { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.back-btn { background: none; border: none; color: var(--text-sub); font-size: 12px; cursor: pointer; padding: 0; transition: color 0.15s; }
.back-btn:hover { color: var(--text); }
.bc-sep { color: var(--border-md); }
.bc-item { color: var(--text-dim); }
.bc-current { color: var(--text-accent); font-weight: 600; cursor: text; border-radius: 4px; padding: 1px 4px; }
.bc-current:hover { background: var(--surface-inset); }
.bc-title-input { color: var(--text-accent); font-weight: 600; font-size: 13px; font-family: inherit; background: var(--surface-inset); border: 1px solid var(--accent-dim); border-radius: 4px; padding: 1px 6px; outline: none; min-width: 80px; max-width: 260px; }
.shot-mood-badge { padding: 2px 8px; background: var(--surface-2); border-radius: 10px; font-size: 10px; color: var(--text-muted); margin-left: 4px; }
.tb-actions { display: flex; gap: 8px; }
.tb-btn { padding: 5px 14px; background: var(--border); border: 1px solid var(--border-strong); border-radius: 6px; color: var(--text-muted); font-size: 12px; cursor: pointer; transition: background 0.15s, color 0.15s; }
.tb-btn:hover { background: var(--border-md); color: var(--text); }
.tb-btn.primary { background: var(--accent); border-color: var(--accent); color: white; }
.tb-btn.primary:hover { background: var(--accent-dim); }
.tb-generating { font-size: 12px; color: var(--accent); animation: pulse 1.2s ease-in-out infinite; }
.tb-refined-badge { font-size: 11px; color: var(--badge-done-text); background: var(--badge-done-bg); padding: 3px 8px; border-radius: 5px; font-weight: 600; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.45} }

/* ── Layout ── */
.main-layout { flex: 1; display: flex; overflow: hidden; background-image: radial-gradient(circle, var(--border-md) 1px, transparent 1px); background-size: 32px 32px; }
.ai-col { flex-shrink: 0; display: flex; flex-direction: column; background: var(--surface); overflow: hidden; min-width: 180px; border-right: 1px solid var(--border); box-shadow: 4px 0 20px var(--shadow); z-index: 2; }
.canvas-col { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; position: relative; }
.detail-col { flex-shrink: 0; display: flex; flex-direction: column; background: var(--surface); overflow: hidden; min-width: 180px; border-left: 1px solid var(--border); box-shadow: -4px 0 20px var(--shadow); z-index: 2; }
.resizer { width: 10px; flex-shrink: 0; background: transparent; cursor: col-resize; z-index: 3; }
.col-header { height: 44px; display: flex; align-items: center; padding: 0 18px; font-size: 12px; font-weight: 600; color: var(--text-muted); border-bottom: 1px solid var(--border); flex-shrink: 0; }

/* ── Guide tabs ── */
.hs-tabs { display: flex; border-bottom: 1px solid var(--border); flex-shrink: 0; overflow-x: auto; }
.hs-tab { flex: 1; padding: 8px 4px; background: none; border: none; font-size: 11px; color: var(--text-muted); cursor: pointer; transition: color 0.15s; white-space: nowrap; }
.hs-tab:hover { color: var(--text); }
.hs-tab.active { font-weight: 600; }
.detail-body { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; }
.detail-empty { flex: 1; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 11px; color: var(--text-ghost); line-height: 1.7; }
.detail-loading { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; font-size: 11px; color: var(--text-muted); }
.guide-panel { display: flex; flex-direction: column; gap: 10px; }
.gc-label { font-size: 11px; font-weight: 700; letter-spacing: .04em; }

/* ── Canvas ── */
.canvas-wrap { flex: 1; position: relative; overflow: hidden; cursor: grab; background: transparent; }
.canvas-wrap.panning { cursor: grabbing; }
.canvas-wrap.crop-active { z-index: 31; }
.canvas-scene { position: absolute; top: 0; left: 0; transform-origin: 0 0; will-change: transform; }

/* ── SVG edges ── */
.edges-svg { position: absolute; top: 0; left: 0; overflow: visible; pointer-events: none; z-index: 0; width: 1px; height: 1px; }
.edge-path { fill: none; stroke: var(--border-md); stroke-width: 2; stroke-dasharray: 6 4; opacity: .7; }

/* ── Version cards (shared) ── */
.version-card {
  position: absolute; border-radius: 12px;
  box-shadow: 0 4px 24px var(--shadow);
  cursor: grab;
  user-select: none;
}
.version-card:active { cursor: grabbing; }

.active-card { outline: 2.5px solid var(--accent); outline-offset: 2px; z-index: 2; }
.active-card.is-selected { box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 25%, transparent), 0 4px 24px var(--shadow); }
.active-card.in-crop { z-index: 32; }

.thumb-card { outline: 2px solid transparent; z-index: 1; transition: outline-color 0.15s, box-shadow 0.15s; }
.thumb-card:hover { outline-color: var(--border-md); box-shadow: 0 6px 28px var(--shadow); }
.thumb-card.is-selected { outline: 2.5px solid var(--accent); outline-offset: 2px; }

/* Image fill */
.img-clip { position: absolute; inset: 0; overflow: hidden; border-radius: 12px; }
.gen-img  { width: 100%; height: 100%; object-fit: cover; display: block; pointer-events: none; }

/* ── Resize handles ── */
.rh {
  position: absolute; width: 12px; height: 12px;
  background: var(--surface); border: 2px solid var(--accent);
  border-radius: 3px; z-index: 10;
  opacity: 0; transition: opacity 0.15s;
}
.version-card:hover .rh, .blank-card:hover .rh, .ref-card:hover .rh { opacity: 1; }
.rh.tl { top: -6px;    left: -6px;   cursor: nw-resize; }
.rh.tr { top: -6px;    right: -6px;  cursor: ne-resize; }
.rh.bl { bottom: -6px; left: -6px;   cursor: sw-resize; }
.rh.br { bottom: -6px; right: -6px;  cursor: se-resize; }

/* Delete button */
.card-delete {
  position: absolute; top: 6px; right: 6px;
  width: 22px; height: 22px; background: rgba(0,0,0,.6); color: white;
  border: none; border-radius: 50%; font-size: 14px; line-height: 1;
  cursor: pointer; display: none; align-items: center; justify-content: center; z-index: 10;
  transition: background 0.12s;
}
.version-card:hover .card-delete, .blank-card:hover .card-delete, .ref-card:hover .card-delete { display: flex; }
.card-delete:hover { background: #e53e3e; }

/* Active badge */
.card-active-badge {
  position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%);
  background: color-mix(in srgb, var(--accent) 90%, black);
  color: white; font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 20px;
  pointer-events: none; white-space: nowrap; z-index: 5;
}

/* Thumbnail label + hint */
.card-label { position: absolute; bottom: 6px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,.55); color: rgba(255,255,255,.85); font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 20px; pointer-events: none; white-space: nowrap; z-index: 5; }
.card-dblclick-hint { position: absolute; top: 6px; left: 0; right: 0; text-align: center; font-size: 9px; color: rgba(255,255,255,.7); background: rgba(0,0,0,.4); padding: 2px; opacity: 0; transition: opacity .15s; pointer-events: none; }
.thumb-card:hover .card-dblclick-hint { opacity: 1; }

/* ── Blank card ── */
.blank-card {
  outline: 2px dashed var(--border-md);
  background: var(--surface);
  z-index: 1;
  cursor: grab;
  transition: outline-color 0.15s;
}
.blank-card:hover, .blank-card.drag-over { outline-color: var(--accent); }
.blank-card.is-selected { outline: 2.5px solid var(--accent); outline-offset: 2px; }
.blank-inner { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; pointer-events: none; }
.blank-icon { font-size: 28px; color: var(--text-ghost); }
.blank-hint { font-size: 10px; color: var(--text-ghost); text-align: center; }

/* ── Reference nodes (r-nodes) ── */
.ref-card { outline: 2px dashed color-mix(in srgb, var(--accent) 40%, transparent); z-index: 1; }
.ref-card:hover { outline-color: color-mix(in srgb, var(--accent) 70%, transparent); }
.ref-card.is-selected { outline: 2.5px solid var(--accent); outline-offset: 2px; box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 20%, transparent); }
.ref-dim { opacity: 0.55; filter: saturate(0.4); }
.ref-processing-overlay { position: absolute; inset: 0; background: rgba(0,0,0,.35); display: flex; align-items: center; justify-content: center; border-radius: 12px; }
.ref-spin { display: block; width: 22px; height: 22px; border: 2.5px solid rgba(255,255,255,.3); border-top-color: white; border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.ref-badge { position: absolute; top: 6px; left: 6px; z-index: 3; pointer-events: none; }
.ref-badge-label { display: inline-block; padding: 2px 7px; border-radius: 5px; font-size: 10px; font-weight: 600; background: var(--surface); color: var(--text-muted); border: 1px solid var(--border); }
.ref-badge-label.pending { color: var(--text-ghost); border-style: dashed; }
.ref-badge-label.pose       { background: #d1fae5; color: #065f46; border-color: #6ee7b7; }
.ref-badge-label.background { background: #dbeafe; color: #1e40af; border-color: #93c5fd; }
.ref-badge-label.weapon     { background: #fef3c7; color: #92400e; border-color: #fcd34d; }
.ref-badge-label.costume    { background: #ede9fe; color: #5b21b6; border-color: #c4b5fd; }
.ref-badge-label.lighting   { background: #fff7ed; color: #9a3412; border-color: #fdba74; }
.ref-badge-label.expression { background: #fce7f3; color: #9d174d; border-color: #f9a8d4; }
.ref-upload-row { padding: 6px 12px 2px; }
.ref-upload-btn { display: flex; align-items: center; gap: 5px; padding: 5px 10px; border: 1px dashed var(--border-md); border-radius: 7px; background: transparent; color: var(--text-muted); font-size: 11px; cursor: pointer; width: 100%; justify-content: center; transition: border-color .15s, color .15s; }
.ref-upload-btn:hover { border-color: var(--accent); color: var(--accent); }

/* ── Empty hint ── */
.eh-icon { font-size: 52px; opacity: .3; }
.eh-text { font-size: 12px; color: var(--text-ghost); }
.eh-sub  { font-size: 11px; color: var(--text-ghost); opacity: .6; }
.eh-dbl  { font-size: 10px; color: var(--text-ghost); opacity: .4; }

/* ── Crop tool ── */
.crop-layer { position: absolute; inset: 0; background: rgba(0,0,0,.35); z-index: 5; pointer-events: all; cursor: crosshair; }
.crop-rect { position: absolute; border: 1.5px solid rgba(255,255,255,.9); box-shadow: 0 0 0 9999px rgba(0,0,0,.45); box-sizing: border-box; cursor: move; z-index: 6; }
.ch { position: absolute; width: 8px; height: 8px; background: white; border: 1px solid rgba(0,0,0,.25); border-radius: 1px; z-index: 7; }
.ch.tl { top: -5px; left: -5px; cursor: nw-resize; }
.ch.tr { top: -5px; right: -5px; cursor: ne-resize; }
.ch.bl { bottom: -5px; left: -5px; cursor: sw-resize; }
.ch.br { bottom: -5px; right: -5px; cursor: se-resize; }

.crop-btn { position: absolute; top: calc(100% + 10px); left: 50%; transform: translateX(-50%); width: 28px; height: 28px; padding: 5px; background: var(--surface); border: 1px solid var(--border); border-radius: 7px; cursor: pointer; color: var(--text-muted); box-shadow: 0 2px 8px var(--shadow); display: flex; align-items: center; justify-content: center; transition: background .12s, color .12s; z-index: 20; pointer-events: all; }
.crop-btn:hover { background: var(--surface-2); color: var(--text); }
.crop-btn.active { background: var(--accent); color: white; border-color: var(--accent); }
.crop-btn svg { width: 100%; height: 100%; }

.ratio-panel { position: absolute; top: calc(100% + 48px); left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: 5px; white-space: nowrap; z-index: 20; pointer-events: all; }
.ratio-chip { padding: 3px 8px; border: 1px solid var(--border-md); border-radius: 5px; background: var(--bg); color: var(--text-muted); font-size: 11px; cursor: pointer; transition: background .1s, color .1s; }
.ratio-chip:hover { background: var(--accent); color: white; border-color: var(--accent); }

.crop-confirm-bar { position: fixed; bottom: 24px; right: 24px; display: flex; gap: 6px; z-index: 32; }
.ccb-cancel  { padding: 6px 14px; border-radius: 7px; border: 1px solid var(--border-md); background: var(--surface); color: var(--text-muted); font-size: 12px; cursor: pointer; }
.ccb-cancel:hover { border-color: var(--text-sub); color: var(--text); }
.ccb-confirm { padding: 6px 16px; border-radius: 7px; border: none; background: var(--accent); color: white; font-size: 12px; font-weight: 600; cursor: pointer; }
.ccb-confirm:hover:not(:disabled) { background: var(--accent-dim); }
.ccb-confirm:disabled { opacity: .35; cursor: not-allowed; }
.crop-dim-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.65); z-index: 30; pointer-events: none; }

/* ── Canvas controls ── */
.canvas-controls { position: absolute; bottom: 14px; right: 14px; display: flex; align-items: center; gap: 4px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 4px 6px; box-shadow: 0 2px 10px var(--shadow); z-index: 10; }
.cc-btn { width: 24px; height: 24px; border: none; background: none; cursor: pointer; color: var(--text-muted); font-size: 13px; border-radius: 4px; display: flex; align-items: center; justify-content: center; transition: background .12s, color .12s; }
.cc-btn:hover { background: var(--border); color: var(--text); }
.cc-btn.fit-btn { font-size: 12px; margin-left: 2px; padding: 0 4px; width: auto; }
.zoom-label { font-size: 11px; color: var(--text-muted); min-width: 38px; text-align: center; }

/* ── Info bar ── */
.info-bar { height: 44px; flex-shrink: 0; background: var(--surface); border-top: 1px solid var(--border); display: flex; align-items: center; gap: 10px; padding: 0 20px; z-index: 3; }
.shot-icon-lg  { font-size: 18px; }
.shot-meta     { display: flex; flex-direction: column; gap: 1px; flex: 1; }
.shot-title-lg { font-size: 13px; font-weight: 600; color: var(--text-hi); }
.shot-mood-lg  { font-size: 10px; color: var(--text-muted); }
.version-count { font-size: 11px; color: var(--text-ghost); }

/* ── AI chat ── */
.ai-messages { flex: 1; overflow-y: auto; padding: 14px 14px 8px; display: flex; flex-direction: column; gap: 10px; min-height: 0; }
.ai-msg { display: flex; gap: 8px; align-items: flex-start; }
.ai-msg.user { flex-direction: row-reverse; }
.ai-avatar { width: 24px; height: 24px; border-radius: 6px; background: var(--avatar-bg); color: var(--avatar-text); font-size: 9px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ai-bubble { max-width: 84%; padding: 7px 10px; border-radius: 8px; font-size: 11px; line-height: 1.55; background: var(--surface-2); color: var(--text-muted); border: 1px solid var(--border); }
.ai-msg.user .ai-bubble { background: var(--bubble-user-bg); border-color: var(--bubble-user-bdr); color: var(--bubble-user-text); }
.typing { display: flex; gap: 4px; align-items: center; padding: 10px 12px; }
.typing span { width: 5px; height: 5px; border-radius: 50%; background: var(--text-sub); animation: dot 1.2s ease-in-out infinite; }
.typing span:nth-child(2) { animation-delay: .2s; }
.typing span:nth-child(3) { animation-delay: .4s; }
@keyframes dot { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-5px)} }

.selection-hint { margin: 0 14px 4px; padding: 5px 10px; background: color-mix(in srgb, var(--accent) 12%, transparent); border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent); border-radius: 6px; font-size: 11px; color: var(--accent); text-align: center; flex-shrink: 0; }

.ai-input-row { display: flex; gap: 6px; padding: 10px 14px 14px; border-top: 1px solid var(--border); flex-shrink: 0; }
.ai-input { flex: 1; background: var(--bg); border: 1px solid var(--border-md); border-radius: 8px; color: var(--text-hi); font-size: 12px; padding: 7px 10px; font-family: inherit; transition: border-color .15s; }
.ai-input:focus { outline: none; border-color: var(--accent-dim); }
.ai-input::placeholder { color: var(--text-ghost); }
.ai-input:disabled { opacity: .5; cursor: not-allowed; }
.ai-send { width: 32px; height: 32px; background: var(--accent-dim); border: none; border-radius: 8px; color: white; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background .15s; }
.ai-send:hover:not(:disabled) { background: var(--accent); }
.ai-send:disabled { background: var(--border-md); cursor: not-allowed; }

/* ── Spinner ── */
.spinner { width: 16px; height: 16px; border: 2px solid var(--border-md); border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Unsaved dialog ── */
.ud-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 200; display: flex; align-items: center; justify-content: center; }
.ud-modal { background: var(--surface); border: 1px solid var(--border-md); border-radius: 12px; padding: 24px 28px; min-width: 300px; display: flex; flex-direction: column; gap: 12px; }
.ud-title { font-size: 15px; font-weight: 600; color: var(--text-hi, var(--text)); }
.ud-body  { font-size: 13px; color: var(--text-sub); }
.ud-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
.ud-btn { padding: 7px 16px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; border: none; transition: background .15s; }
.ud-cancel  { background: none; color: var(--text-muted); border: 1px solid var(--border-md); }
.ud-cancel:hover { border-color: var(--text-sub); }
.ud-discard { background: var(--surface-2, var(--border)); color: var(--text); }
.ud-discard:hover { background: var(--border-md); }
.ud-save    { background: var(--accent); color: white; }
.ud-save:hover { background: var(--accent-dim, #2d8f5f); }

/* ── Generating overlay ── */
.gen-overlay {
  position: absolute; inset: 0; z-index: 50;
  background: rgba(0,0,0,.52);
  backdrop-filter: blur(3px);
  display: flex; align-items: center; justify-content: center;
  pointer-events: all;
}
.gen-overlay-card {
  display: flex; flex-direction: column; align-items: center; gap: 14px;
  background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 16px; padding: 32px 40px;
  box-shadow: 0 8px 32px rgba(0,0,0,.28);
}
.gen-spinner {
  width: 36px; height: 36px;
  border: 3px solid var(--border-md);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin .8s linear infinite;
}
.gen-label { font-size: 15px; font-weight: 600; color: var(--text); }
.gen-sub   { font-size: 12px; color: var(--text-lo, #999); }

/* fade-in / fade-out transition */
.gen-overlay-enter-active, .gen-overlay-leave-active { transition: opacity .25s ease; }
.gen-overlay-enter-from, .gen-overlay-leave-to { opacity: 0; }
</style>
