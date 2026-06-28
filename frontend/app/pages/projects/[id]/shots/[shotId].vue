<template>
  <div class="shot-page">

    <!-- Top bar -->
    <div class="top-bar">
      <div class="breadcrumb">
        <button class="back-btn" @click="goBack">← 返回</button>
        <span class="bc-sep">/</span>
        <span class="bc-item">{{ characterName }}</span>
        <span class="bc-sep">/</span>
        <span class="bc-current">{{ shot.title }}{{ hasUnsavedChanges ? ' *' : '' }}</span>
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
        <div
          class="canvas-wrap"
          ref="canvasWrapRef"
          :class="{ panning: dragMode === 'pan', 'img-cursor': dragMode === 'img', 'crop-active': editMode === 'crop' }"
          :style="gridStyle"
          @mousedown.self="startPan"
          @wheel.prevent="onWheel"
        >
          <div class="canvas-scene" :style="{ transform: sceneTransform }">

            <!-- Image object -->
            <div
              v-if="img"
              class="img-obj"
              :style="{ left: img.x + 'px', top: img.y + 'px', width: img.w + 'px', height: img.h + 'px' }"
              :class="{ selected: imgSelected, 'in-crop': editMode === 'crop' }"
              @mousedown.stop="startImgDrag"
              @click.stop="imgSelected = true"
            >
              <div class="img-clip">
                <img :src="currentDisplayUrl" class="gen-img" draggable="false" />

                <!-- Inline crop layer -->
                <template v-if="editMode === 'crop'">
                  <div class="crop-layer" />
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

              <!-- Hotspot dots (hidden in crop mode) -->
              <svg v-if="editMode !== 'crop'" class="hs-svg" :width="img.w" :height="img.h">
                <g
                  v-for="hs in hotspots"
                  :key="hs.id"
                  :transform="`translate(${hs.x / 100 * img.w}, ${hs.y / 100 * img.h})`"
                  class="hs-dot"
                  :class="{ active: activeId === hs.id }"
                  @click.stop="clickHotspot(hs)"
                >
                  <circle class="hs-ring" :fill="hs.color" />
                  <circle r="6" :fill="hs.color" />
                  <circle r="2.5" fill="white" />
                  <text y="20" text-anchor="middle" :fill="hs.color" class="hs-label">{{ hs.label }}</text>
                </g>
              </svg>

              <!-- Resize handles (normal mode only) -->
              <template v-if="imgSelected && editMode !== 'crop'">
                <div class="rh tl" @mousedown.stop="startResize('tl', $event)" />
                <div class="rh tr" @mousedown.stop="startResize('tr', $event)" />
                <div class="rh bl" @mousedown.stop="startResize('bl', $event)" />
                <div class="rh br" @mousedown.stop="startResize('br', $event)" />
              </template>

              <!-- Crop icon button + ratio panel (bottom center, normal mode) -->
              <template v-if="imgSelected && editMode !== 'crop'">
                <!-- Crop icon button -->
                <button class="crop-btn" @click.stop="toggleRatioPanel" :class="{ active: showRatioPanel }">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                    <path d="M6 2v14a2 2 0 0 0 2 2h14"/>
                    <path d="M18 22V8a2 2 0 0 0-2-2H2"/>
                  </svg>
                </button>
                <!-- Ratio picker panel (below crop button) -->
                <div v-if="showRatioPanel" class="ratio-panel" @click.stop @mousedown.stop>
                  <button
                    v-for="r in RATIOS"
                    :key="r.label"
                    class="ratio-chip"
                    @click.stop="selectRatio(r.value)"
                  >{{ r.label }}</button>
                </div>
              </template>
            </div>

            <!-- Empty hint -->
            <div v-else class="empty-hint" @mousedown.stop>
              <span class="eh-icon">{{ shot.icon }}</span>
              <span class="eh-text">在左侧输入描述，点击「生成」</span>
            </div>

          </div>

          <div class="canvas-controls">
            <button class="cc-btn" @click="zoomOut">−</button>
            <span class="zoom-label">{{ Math.round(canvasZoom * 100) }}%</span>
            <button class="cc-btn" @click="zoomIn">+</button>
            <button class="cc-btn fit-btn" @click="fitToView">⊞</button>
          </div>

          <!-- Crop confirm bar (bottom-right, only in crop mode) -->
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
        </div>
      </div>

      <!-- Resizer: canvas | right -->
      <div class="resizer" @mousedown.prevent="startResize2('right', $event)" />

      <!-- ── Right: Guide detail panel ── -->
      <div class="detail-col" :style="{ width: rightWidth + 'px' }">
        <div class="col-header">拍摄指南</div>

        <!-- Hotspot tabs -->
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

        <!-- Guide content -->
        <div class="detail-body">
          <div v-if="!img" class="detail-empty">
            <span>先生成例图<br>再查看拍摄指南</span>
          </div>
          <div v-else-if="!activeId" class="detail-empty">
            <span>点击图上或上方的<br>标注点查看指南</span>
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

  <!-- Dim overlay when in crop mode (covers everything except canvas-col) -->
  <Teleport to="body">
    <div v-if="editMode === 'crop'" class="crop-dim-overlay" />
  </Teleport>

  <!-- Unsaved changes dialog -->
  <Teleport to="body">
    <div v-if="unsavedDialog" class="ud-backdrop">
      <div class="ud-modal">
        <div class="ud-title">有未保存的修改</div>
        <div class="ud-body">图片已编辑但尚未保存，是否保存？</div>
        <div class="ud-actions">
          <button class="ud-btn ud-cancel"   @click="unsavedDialog = null">取消</button>
          <button class="ud-btn ud-discard"  @click="unsavedDialog.onDiscard()">不保存</button>
          <button class="ud-btn ud-save"     @click="unsavedDialog.onSave()">保存</button>
        </div>
      </div>
    </div>
  </Teleport>

</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, onBeforeRouteLeave } from 'vue-router'
import { useApi } from '~/composables/useApi'

definePageMeta({ ssr: false })

const route = useRoute()
const api = useApi()

const BASE_URL = 'http://localhost:8000'

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

const characterName = computed(() =>
  projectData.value?.character ?? projectData.value?.character_data?.character ?? ''
)

// ── Hotspots ──────────────────────────────────────────────
const hotspots = [
  { id: 'expression', label: '表情', guideType: 'expression' as const, x: 50, y: 26, color: '#f472b6' },
  { id: 'pose',       label: '动作', guideType: 'action'     as const, x: 40, y: 57, color: '#34d399' },
  { id: 'camera',     label: '构图', guideType: 'camera'     as const, x: 14, y: 34, color: '#fbbf24' },
  { id: 'background', label: '背景', guideType: 'background' as const, x: 84, y: 45, color: '#60a5fa' },
]
type Hotspot = typeof hotspots[number]

// ── Panel resize ─────────────────────────────────────────
const leftWidth  = ref(280)
const rightWidth = ref(280)
const MIN_W = 180
const MAX_W = 520

type ResizeSide = 'left' | 'right'
let resizeSide: ResizeSide | null = null
let resizeStartX = 0
let resizeStartW = 0

function startResize2(side: ResizeSide, e: MouseEvent) {
  resizeSide   = side
  resizeStartX = e.clientX
  resizeStartW = side === 'left' ? leftWidth.value : rightWidth.value
  document.body.style.cursor    = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onResizeMove(e: MouseEvent) {
  if (!resizeSide) return
  const dx = e.clientX - resizeStartX
  if (resizeSide === 'left') {
    leftWidth.value  = Math.min(MAX_W, Math.max(MIN_W, resizeStartW + dx))
  } else {
    rightWidth.value = Math.min(MAX_W, Math.max(MIN_W, resizeStartW - dx))
  }
}

function stopResize2() {
  if (!resizeSide) return
  resizeSide = null
  document.body.style.cursor    = ''
  document.body.style.userSelect = ''
}

// ── Canvas state ──────────────────────────────────────────
const canvasWrapRef = ref<HTMLElement | null>(null)
const canvasPan     = ref({ x: 0, y: 0 })
const canvasZoom    = ref(1)

const sceneTransform = computed(() =>
  `translate(${canvasPan.value.x}px, ${canvasPan.value.y}px) scale(${canvasZoom.value})`
)

// Grid background shifts with pan to give infinite-canvas feel
const gridStyle = computed(() => ({
  backgroundPosition: `${canvasPan.value.x % 32}px ${canvasPan.value.y % 32}px`,
}))

// ── Image object ──────────────────────────────────────────
const generatedImage = ref<string | null>(null)
const imgSelected    = ref(false)
const img = ref<{ x: number; y: number; w: number; h: number } | null>(null)

// ── Image editor state ─────────────────────────────────────
type HistoryEntry = { url: string; imgState: { x: number; y: number; w: number; h: number } }
const editHistory  = ref<HistoryEntry[]>([])
const historyIndex = ref(-1)

const currentDisplayUrl = computed((): string =>
  historyIndex.value >= 0 ? editHistory.value[historyIndex.value].url : (generatedImage.value ?? '')
)
const canUndo           = computed(() => historyIndex.value > 0)
const canRedo           = computed(() => historyIndex.value < editHistory.value.length - 1)
const hasUnsavedChanges = computed(() => historyIndex.value > 0)

function pushHistory(dataUrl: string, imgState: { x: number; y: number; w: number; h: number }) {
  editHistory.value = editHistory.value.slice(0, historyIndex.value + 1)
  editHistory.value.push({ url: dataUrl, imgState: { ...imgState } })
  historyIndex.value++
}

async function initEditHistory(imageUrl: string) {
  const snapImg = img.value ? { ...img.value } : { x: 0, y: 0, w: 512, h: 512 }
  try {
    const blob    = await fetch(imageUrl, { cache: 'reload' }).then(r => r.blob())
    const dataUrl = await new Promise<string>(res => {
      const reader = new FileReader()
      reader.onload = e => res(e.target!.result as string)
      reader.readAsDataURL(blob)
    })
    editHistory.value  = [{ url: dataUrl, imgState: snapImg }]
    historyIndex.value = 0
  } catch (e) {
    console.error('initEditHistory failed', e)
    editHistory.value  = [{ url: imageUrl, imgState: snapImg }]
    historyIndex.value = 0
  }
}

function applyHistoryEntry(idx: number) {
  const entry = editHistory.value[idx]
  if (!entry) return
  historyIndex.value = idx
  img.value = { ...entry.imgState }
}
function undo() { if (canUndo.value) applyHistoryEntry(historyIndex.value - 1) }
function redo() { if (canRedo.value) applyHistoryEntry(historyIndex.value + 1) }

// ── Crop tool (inline, on-canvas) ─────────────────────────
const RATIOS = [
  { label: '16:9', value: 16 / 9 },
  { label: '3:2',  value: 3  / 2 },
  { label: '4:3',  value: 4  / 3 },
  { label: '1:1',  value: 1      },
  { label: '3:4',  value: 3  / 4 },
  { label: '2:3',  value: 2  / 3 },
  { label: '9:16', value: 9  / 16 },
]

const editMode       = ref<null | 'crop'>(null)
const showRatioPanel = ref(false)
const cropRatio      = ref(1)
const inlineCrop     = ref<{ x: number; y: number; w: number; h: number } | null>(null)
const inlineCropValid = computed(() =>
  inlineCrop.value !== null && inlineCrop.value.w >= 4 && inlineCrop.value.h >= 4
)

function toggleRatioPanel() {
  showRatioPanel.value = !showRatioPanel.value
}

function initCropFromRatio(ratio: number) {
  if (!img.value) return
  const { w: iw, h: ih } = img.value
  let cw = iw, ch = cw / ratio
  if (ch > ih) { ch = ih; cw = ch * ratio }
  inlineCrop.value = { x: (iw - cw) / 2, y: (ih - ch) / 2, w: cw, h: ch }
}

function selectRatio(ratio: number) {
  cropRatio.value      = ratio
  showRatioPanel.value = false
  editMode.value       = 'crop'
  initCropFromRatio(ratio)
}

// Convert screen coord → coordinate inside img-clip (same units as img.w/h)
// clamp=true only when drawing a new selection from scratch
function eventToImgCoords(e: MouseEvent, clamp = false) {
  if (!img.value) return { x: 0, y: 0 }
  const x = (e.clientX - canvasPan.value.x) / canvasZoom.value - img.value.x
  const y = (e.clientY - canvasPan.value.y) / canvasZoom.value - img.value.y
  if (!clamp) return { x, y }
  return {
    x: Math.max(0, Math.min(x, img.value.w)),
    y: Math.max(0, Math.min(y, img.value.h)),
  }
}

function clampCrop(c: { x: number; y: number; w: number; h: number }) {
  if (!img.value) return c
  const x = Math.max(0, Math.min(c.x, img.value.w - c.w))
  const y = Math.max(0, Math.min(c.y, img.value.h - c.h))
  const w = Math.max(8, Math.min(c.w, img.value.w - x))
  const h = Math.max(8, Math.min(c.h, img.value.h - y))
  return { x, y, w, h }
}

function cancelCrop() {
  editMode.value       = null
  inlineCrop.value     = null
  showRatioPanel.value = false
}

// Drag on the background (outside crop rect) → draw a new selection
function onCropLayerDown(e: MouseEvent) {
  const start = eventToImgCoords(e, true)
  inlineCrop.value = { x: start.x, y: start.y, w: 0, h: 0 }

  const onMove = (me: MouseEvent) => {
    const curr = eventToImgCoords(me, true)
    inlineCrop.value = clampCrop({
      x: Math.min(curr.x, start.x),
      y: Math.min(curr.y, start.y),
      w: Math.abs(curr.x - start.x),
      h: Math.abs(curr.y - start.y),
    })
  }
  const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

// Drag on the crop rect body → move the selection
function onCropRectDown(e: MouseEvent) {
  const start = eventToImgCoords(e)
  const snap  = { ...inlineCrop.value! }

  const onMove = (me: MouseEvent) => {
    const curr = eventToImgCoords(me)
    inlineCrop.value = clampCrop({ ...snap, x: snap.x + (curr.x - start.x), y: snap.y + (curr.y - start.y) })
  }
  const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

// Drag a corner handle → resize with locked ratio
function startCropHandle(handle: string, e: MouseEvent) {
  const start = eventToImgCoords(e)
  const snap  = { ...inlineCrop.value! }
  const ratio = cropRatio.value
  const MIN   = 20
  const iw    = img.value!.w
  const ih    = img.value!.h

  const onMove = (me: MouseEvent) => {
    const curr = eventToImgCoords(me)
    const dx = curr.x - start.x
    const dy = curr.y - start.y

    // Compute raw new width from drag (dx drives width, dy contributes via ratio)
    const rawDelta = handle === 'br' || handle === 'tr' ? dx : -dx
    let newW = Math.max(MIN, snap.w + rawDelta)
    let newH = newW / ratio

    // Clamp to available space, preserving ratio
    // Right-anchored handles: right edge = snap.x + newW ≤ iw
    if (handle === 'br' || handle === 'tr') {
      if (snap.x + newW > iw) { newW = iw - snap.x; newH = newW / ratio }
    } else {
      // Left-anchored handles: left edge = snap.x + snap.w - newW ≥ 0
      if (newW > snap.x + snap.w) { newW = snap.x + snap.w; newH = newW / ratio }
    }
    // Bottom-anchored handles: bottom edge = snap.y + newH ≤ ih
    if (handle === 'br' || handle === 'bl') {
      if (snap.y + newH > ih) { newH = ih - snap.y; newW = newH * ratio }
    } else {
      // Top-anchored handles: top edge = snap.y + snap.h - newH ≥ 0
      if (newH > snap.y + snap.h) { newH = snap.y + snap.h; newW = newH * ratio }
    }

    newW = Math.max(MIN, newW)
    newH = newW / ratio

    let nx = snap.x, ny = snap.y
    if (handle === 'tl') { nx = snap.x + snap.w - newW; ny = snap.y + snap.h - newH }
    if (handle === 'tr') { ny = snap.y + snap.h - newH }
    if (handle === 'bl') { nx = snap.x + snap.w - newW }

    inlineCrop.value = { x: nx, y: ny, w: newW, h: newH }
  }
  const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const el = new window.Image()
    el.crossOrigin = 'anonymous'
    el.onload  = () => resolve(el)
    el.onerror = reject
    el.src = src
  })
}

async function applyCrop() {
  const crop = inlineCrop.value
  if (!crop || crop.w < 4 || crop.h < 4 || !img.value) return

  const url = currentDisplayUrl.value
  let objectUrl: string | null = null
  let srcImg: HTMLImageElement
  if (url.startsWith('data:')) {
    srcImg = await loadImage(url)
  } else {
    const blob = await fetch(url, { cache: 'reload' }).then(r => r.blob())
    objectUrl  = URL.createObjectURL(blob)
    srcImg     = await loadImage(objectUrl)
  }
  try {
    const scaleX  = srcImg.naturalWidth  / img.value.w
    const scaleY  = srcImg.naturalHeight / img.value.h

    const canvas  = document.createElement('canvas')
    canvas.width  = Math.round(crop.w * scaleX)
    canvas.height = Math.round(crop.h * scaleY)
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(
      srcImg,
      Math.round(crop.x * scaleX), Math.round(crop.y * scaleY),
      canvas.width, canvas.height,
      0, 0, canvas.width, canvas.height,
    )

    const dataUrl = canvas.toDataURL('image/png')

    const ratio  = canvas.width / canvas.height
    const MAX    = 512
    const newW   = ratio >= 1 ? MAX : Math.round(MAX * ratio)
    const newH   = ratio >= 1 ? Math.round(MAX / ratio) : MAX
    const cx     = img.value.x + img.value.w / 2
    const cy     = img.value.y + img.value.h / 2
    img.value    = { x: cx - newW / 2, y: cy - newH / 2, w: newW, h: newH }
    pushHistory(dataUrl, img.value)

    editMode.value   = null
    inlineCrop.value = null
  } catch (e) {
    console.error('applyCrop failed:', e)
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl)
  }
}

// ── Save edited image to backend ───────────────────────────
const saving = ref(false)

async function saveImage() {
  const dataUrl = currentDisplayUrl.value
  if (!dataUrl || !hasUnsavedChanges.value) return
  saving.value = true
  try {
    const blob = await fetch(dataUrl).then(r => r.blob())
    await api.saveImage(projectId.value, shotId.value, blob)
    editHistory.value  = [{ url: dataUrl, imgState: { ...img.value! } }]
    historyIndex.value = 0
  } catch (e) {
    console.error('Save image failed', e)
  }
  saving.value = false
}

// ── Unsaved-changes guard ──────────────────────────────────
const unsavedDialog = ref<{ onSave: () => void; onDiscard: () => void } | null>(null)

function guardAction(action: () => void) {
  if (!hasUnsavedChanges.value) { action(); return }
  unsavedDialog.value = {
    onSave:    async () => { await saveImage(); unsavedDialog.value = null; action() },
    onDiscard: ()      => { unsavedDialog.value = null; action() },
  }
}

function goBack() {
  guardAction(() => navigateTo(`/projects/${route.params.id}`))
}

function onBeforeUnload(e: BeforeUnloadEvent) {
  if (hasUnsavedChanges.value) { e.preventDefault(); e.returnValue = '' }
}

function onKeyDown(e: KeyboardEvent) {
  if (!(e.metaKey || e.ctrlKey)) return
  if (e.key === 's') { e.preventDefault(); saveImage() }
  if (e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo() }
  if (e.key === 'z' &&  e.shiftKey) { e.preventDefault(); redo() }
  if (e.key === 'y')                 { e.preventDefault(); redo() }
}

onBeforeRouteLeave(() => {
  if (hasUnsavedChanges.value && !unsavedDialog.value) return false
})

const activeId     = ref<string | null>(null)
const guideLoading = ref(false)
const guide        = ref<any>(null)
const sketchUrl    = ref<string | null>(null)

const activeHs = computed(() => hotspots.find(h => h.id === activeId.value) ?? null)

async function clickHotspot(hs: Hotspot) {
  if (activeId.value === hs.id) { closePopup(); return }
  activeId.value     = hs.id
  guide.value        = null
  sketchUrl.value    = null
  guideLoading.value = true
  try {
    let result = await api.getGuide(projectId.value, shotId.value, hs.guideType)
    if (!result) {
      result = await api.generateGuide(projectId.value, shotId.value, hs.guideType)
    }
    guide.value     = result?.guide ?? null
    sketchUrl.value = result?.sketch_url ? BASE_URL + result.sketch_url : null
  } catch (e) {
    console.error('Guide error', e)
  }
  guideLoading.value = false
}

function closePopup() {
  activeId.value  = null
  guide.value     = null
  sketchUrl.value = null
}

// ── Drag / pan / resize ───────────────────────────────────
type DragMode = null | 'pan' | 'img' | 'resize-tl' | 'resize-tr' | 'resize-bl' | 'resize-br'
const dragMode  = ref<DragMode>(null)
const dragStart = ref({ mx: 0, my: 0, panX: 0, panY: 0, imgX: 0, imgY: 0, imgW: 0, imgH: 0 })

function startPan(e: MouseEvent) {
  if (e.button !== 0) return
  imgSelected.value = false
  if (editMode.value !== null) { editMode.value = null; inlineCrop.value = null }
  showRatioPanel.value = false
  closePopup()
  dragMode.value = 'pan'
  dragStart.value = { ...dragStart.value, mx: e.clientX, my: e.clientY, panX: canvasPan.value.x, panY: canvasPan.value.y }
}

function startImgDrag(e: MouseEvent) {
  if (e.button !== 0 || editMode.value !== null) return
  imgSelected.value = true
  if (!img.value) return
  dragMode.value = 'img'
  dragStart.value = { ...dragStart.value, mx: e.clientX, my: e.clientY, imgX: img.value.x, imgY: img.value.y }
}

function startResize(handle: 'tl' | 'tr' | 'bl' | 'br', e: MouseEvent) {
  if (!img.value) return
  dragMode.value = `resize-${handle}` as DragMode
  dragStart.value = { mx: e.clientX, my: e.clientY, imgX: img.value.x, imgY: img.value.y, imgW: img.value.w, imgH: img.value.h, panX: 0, panY: 0 }
}

function onWindowMouseMove(e: MouseEvent) {
  const mode = dragMode.value
  if (!mode) return
  const dx = e.clientX - dragStart.value.mx
  const dy = e.clientY - dragStart.value.my

  if (mode === 'pan') {
    canvasPan.value = { x: dragStart.value.panX + dx, y: dragStart.value.panY + dy }
  } else if (mode === 'img' && img.value) {
    img.value = { ...img.value, x: dragStart.value.imgX + dx / canvasZoom.value, y: dragStart.value.imgY + dy / canvasZoom.value }
  } else if (mode.startsWith('resize') && img.value) {
    const handle  = mode.replace('resize-', '') as 'tl' | 'tr' | 'bl' | 'br'
    const { imgX, imgY, imgW, imgH } = dragStart.value
    const dxS    = dx / canvasZoom.value
    const aspect = imgW / imgH   // lock aspect ratio
    const MIN_W  = 80

    let newW = imgW, newX = imgX, newY = imgY
    if (handle === 'br') newW = Math.max(MIN_W, imgW + dxS)
    if (handle === 'tl') newW = Math.max(MIN_W, imgW - dxS)
    if (handle === 'tr') newW = Math.max(MIN_W, imgW + dxS)
    if (handle === 'bl') newW = Math.max(MIN_W, imgW - dxS)
    const newH = newW / aspect

    if (handle === 'tl') { newX = imgX + (imgW - newW); newY = imgY + (imgH - newH) }
    if (handle === 'tr') { newY = imgY + (imgH - newH) }
    if (handle === 'bl') { newX = imgX + (imgW - newW) }

    img.value = { x: newX, y: newY, w: newW, h: newH }
  }
}

function onWindowMouseUp() { dragMode.value = null }

onMounted(async () => {
  window.addEventListener('mousemove',    onWindowMouseMove)
  window.addEventListener('mousemove',    onResizeMove)
  window.addEventListener('mouseup',      onWindowMouseUp)
  window.addEventListener('mouseup',      stopResize2)
  window.addEventListener('keydown',      onKeyDown)
  window.addEventListener('beforeunload', onBeforeUnload)
  nextTick(() => {
    const wrap = canvasWrapRef.value
    if (!wrap) return
    canvasPan.value = {
      x: (wrap.clientWidth  - 380) / 2,
      y: (wrap.clientHeight - 500) / 2,
    }
  })
  try {
    projectData.value = await api.getProject(projectId.value)
    shotData.value = await api.getShot(projectId.value, shotId.value)
    aiMessages.value = shotData.value?.chat_history ?? []
    // Resume polling if generation was in-progress when page was loaded/refreshed
    if (shotData.value?.status === 'generating') {
      generating.value = true
      pollUntilDone()
    }
    // If shot already has a generated image, load it
    if ((shotData.value?.status === 'done' || shotData.value?.status === 'refined') && shotData.value?.image_url) {
      generatedImage.value = BASE_URL + shotData.value.image_url + '?t=' + Date.now()
      await placeImage(generatedImage.value)
      await initEditHistory(generatedImage.value)
    }
  } catch (e) {
    console.error('Failed to load shot', e)
  }
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

// ── Zoom ──────────────────────────────────────────────────
function onWheel(e: WheelEvent) {
  const wrap = canvasWrapRef.value
  if (!wrap) return
  const rect   = wrap.getBoundingClientRect()
  const mx     = e.clientX - rect.left
  const my     = e.clientY - rect.top
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
  const newZ   = Math.max(0.08, Math.min(6, canvasZoom.value * factor))
  const ratio  = newZ / canvasZoom.value
  canvasPan.value   = { x: mx - (mx - canvasPan.value.x) * ratio, y: my - (my - canvasPan.value.y) * ratio }
  canvasZoom.value  = newZ
}

function zoomIn()  { applyZoomCentered(1.25) }
function zoomOut() { applyZoomCentered(1 / 1.25) }

function applyZoomCentered(factor: number) {
  const wrap = canvasWrapRef.value
  if (!wrap) return
  const mx = wrap.clientWidth  / 2
  const my = wrap.clientHeight / 2
  const newZ = Math.max(0.08, Math.min(6, canvasZoom.value * factor))
  const ratio = newZ / canvasZoom.value
  canvasPan.value  = { x: mx - (mx - canvasPan.value.x) * ratio, y: my - (my - canvasPan.value.y) * ratio }
  canvasZoom.value = newZ
}

function fitToView() {
  const wrap = canvasWrapRef.value
  if (!wrap) return
  if (!img.value) {
    // Reset to origin
    canvasPan.value  = { x: 0, y: 0 }
    canvasZoom.value = 1
    return
  }
  const pad  = 48
  const wW   = wrap.clientWidth  - pad * 2
  const wH   = wrap.clientHeight - pad * 2
  const newZ = Math.min(wW / img.value.w, wH / img.value.h, 2)
  const cx   = img.value.x + img.value.w / 2
  const cy   = img.value.y + img.value.h / 2
  canvasZoom.value = newZ
  canvasPan.value  = { x: wrap.clientWidth  / 2 - cx * newZ, y: wrap.clientHeight / 2 - cy * newZ }
}

// ── Image placement helpers ───────────────────────────────
function placeImage(url: string, centered = true) {
  return new Promise<void>(resolve => {
    const el = new window.Image()
    el.onload = () => {
      const MAX = 512
      const ratio = el.naturalWidth / el.naturalHeight
      const iW = ratio >= 1 ? MAX : Math.round(MAX * ratio)
      const iH = ratio >= 1 ? Math.round(MAX / ratio) : MAX
      const wrap = canvasWrapRef.value
      const cx = wrap && centered
        ? (wrap.clientWidth  / 2 - canvasPan.value.x) / canvasZoom.value
        : iW / 2
      const cy = wrap && centered
        ? (wrap.clientHeight / 2 - canvasPan.value.y) / canvasZoom.value
        : iH / 2
      img.value = { x: cx - iW / 2, y: cy - iH / 2, w: iW, h: iH }
      resolve()
    }
    el.src = url
  })
}

// ── Generation polling ────────────────────────────────────
const generating = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null

function stopPolling() {
  if (pollTimer) { clearTimeout(pollTimer); pollTimer = null }
}

async function pollUntilDone() {
  stopPolling()
  try {
    const shot = await api.getShot(projectId.value, shotId.value)
    if (shot.status === 'done' && shot.image_url) {
      generatedImage.value = BASE_URL + shot.image_url + '?t=' + Date.now()
      await placeImage(generatedImage.value)
      await initEditHistory(generatedImage.value)
      imgSelected.value = true
      generating.value = false
      await refreshHistory()
    } else if (shot.status === 'error') {
      generating.value = false
      await refreshHistory()
    } else {
      pollTimer = setTimeout(pollUntilDone, 3000)
    }
  } catch {
    pollTimer = setTimeout(pollUntilDone, 5000)
  }
}

// ── AI chat ───────────────────────────────────────────────
const aiMsgContainer = ref<HTMLElement | null>(null)
const chatInput      = ref('')
const chatLoading    = ref(false)
const aiMessages     = ref<{ role: string; text: string }[]>([])

async function refreshHistory() {
  const shot = await api.getShot(projectId.value, shotId.value)
  aiMessages.value = shot.chat_history ?? []
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
    const { reply, generating: gen } = await api.shotChat(projectId.value, shotId.value, text)
    if (reply) aiMessages.value.push({ role: 'agent', text: reply })
    if (gen) {
      generating.value = true
      pollUntilDone()
    }
  } catch {
    aiMessages.value.push({ role: 'agent', text: '出了点问题，请稍后重试。' })
  }

  chatLoading.value = false
  await nextTick()
  if (aiMsgContainer.value) aiMsgContainer.value.scrollTop = aiMsgContainer.value.scrollHeight
}
</script>

<style scoped>
.shot-page {
  height: 100vh;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── Top bar ── */
.top-bar {
  height: 48px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; flex-shrink: 0;
}
.breadcrumb  { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.back-btn    { background: none; border: none; color: var(--text-sub); font-size: 12px; cursor: pointer; padding: 0; transition: color 0.15s; }
.back-btn:hover { color: var(--text); }
.bc-sep      { color: var(--border-md); }
.bc-item     { color: var(--text-dim); }
.bc-current  { color: var(--text-accent); font-weight: 600; }
.shot-mood-badge { padding: 2px 8px; background: var(--surface-2); border-radius: 10px; font-size: 10px; color: var(--text-muted); margin-left: 4px; }
.tb-actions  { display: flex; gap: 8px; }
.tb-btn      { padding: 5px 14px; background: var(--border); border: 1px solid var(--border-strong); border-radius: 6px; color: var(--text-muted); font-size: 12px; cursor: pointer; transition: background 0.15s, color 0.15s; }
.tb-btn:hover { background: var(--border-md); color: var(--text); }
.tb-btn.primary { background: var(--accent); border-color: var(--accent); color: white; }
.tb-btn.primary:hover    { background: var(--accent-dim); }
.tb-btn.primary:disabled { background: var(--border-md); border-color: var(--border-md); color: var(--text-quiet); cursor: not-allowed; }
.tb-generating   { font-size: 12px; color: var(--accent); animation: pulse 1.2s ease-in-out infinite; }
.tb-refined-badge { font-size: 11px; color: var(--badge-done-text); background: var(--badge-done-bg); padding: 3px 8px; border-radius: 5px; font-weight: 600; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.45} }

/* ── Main layout: dot canvas spans full width, panels float above ── */
.main-layout {
  flex: 1; display: flex; overflow: hidden;
  background-image: radial-gradient(circle, var(--border-md) 1px, transparent 1px);
  background-size: 32px 32px;
}

/* ── Left: AI panel (card floating on canvas) ── */
.ai-col {
  flex-shrink: 0;
  display: flex; flex-direction: column;
  background: var(--surface);
  overflow: hidden;
  min-width: 180px;
  border-right: 1px solid var(--border);
  box-shadow: 4px 0 20px var(--shadow);
  z-index: 2;
}

/* ── Center: Canvas (transparent — dots come from main-layout) ── */
.canvas-col { flex: 1; display: flex; flex-direction: column; min-width: 0; overflow: hidden; }

/* ── Right: Guide detail (card floating on canvas) ── */
.detail-col {
  flex-shrink: 0;
  display: flex; flex-direction: column;
  background: var(--surface);
  overflow: hidden;
  min-width: 180px;
  border-left: 1px solid var(--border);
  box-shadow: -4px 0 20px var(--shadow);
  z-index: 2;
}

/* ── Resizer handle (invisible hit area, cursor only) ── */
.resizer {
  width: 6px; flex-shrink: 0;
  background: transparent;
  cursor: col-resize;
  z-index: 3;
  position: relative;
}
.resizer::after {
  content: '';
  position: absolute;
  inset: 0 -2px;
}

/* Shared column header */
.col-header {
  height: 44px; display: flex; align-items: center; padding: 0 18px;
  font-size: 12px; font-weight: 600; color: var(--text-muted);
  border-bottom: 1px solid var(--border); flex-shrink: 0;
}

/* Hotspot tabs */
.hs-tabs {
  display: flex; border-bottom: 1px solid var(--border); flex-shrink: 0;
  overflow-x: auto;
}
.hs-tab {
  flex: 1; padding: 8px 4px; background: none; border: none;
  font-size: 11px; color: var(--text-muted); cursor: pointer;
  transition: color 0.15s; white-space: nowrap;
}
.hs-tab:hover { color: var(--text); }
.hs-tab.active { font-weight: 600; }

/* Guide detail body */
.detail-body {
  flex: 1; overflow-y: auto; padding: 16px;
  display: flex; flex-direction: column;
}
.detail-empty {
  flex: 1; display: flex; align-items: center; justify-content: center;
  text-align: center; font-size: 11px; color: var(--text-ghost); line-height: 1.7;
}
.detail-loading {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 10px; font-size: 11px; color: var(--text-muted);
}
.guide-panel { display: flex; flex-direction: column; gap: 10px; }
.gc-label    { font-size: 11px; font-weight: 700; letter-spacing: 0.04em; }

/* Infinite canvas viewport */
.canvas-wrap {
  flex: 1;
  position: relative;
  overflow: hidden;
  cursor: grab;
  background: transparent;
}
.canvas-wrap.panning   { cursor: grabbing; }
.canvas-wrap.img-cursor { cursor: move; }

/* Canvas scene: the single transformed div */
.canvas-scene {
  position: absolute;
  top: 0; left: 0;
  transform-origin: 0 0;
  will-change: transform;
}

/* Empty hint */
.empty-hint {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; width: 380px; height: 500px;
  border: 2px dashed var(--border-md);
  border-radius: 16px;
  background: var(--surface);
  user-select: none; pointer-events: none;
  box-shadow: 0 4px 24px var(--shadow);
}
.eh-icon { font-size: 52px; opacity: 0.3; }
.eh-text { font-size: 12px; color: var(--text-ghost); }

/* ── Image object ── */
.img-obj {
  position: absolute;
  cursor: move;
  overflow: visible;
}
.img-clip {
  position: absolute; inset: 0;
  overflow: hidden;
  border-radius: 8px;
  box-shadow: 0 4px 32px var(--shadow);
}
.gen-img { width: 100%; height: 100%; object-fit: fill; display: block; }

/* Selection outline (suppressed in crop mode) */
.img-obj.selected:not(.in-crop) .img-clip {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

/* SVG overlay for hotspots */
.hs-svg {
  position: absolute; inset: 0;
  overflow: visible;
  pointer-events: none;
  z-index: 2;
}

/* Hotspot dots */
.hs-dot {
  cursor: pointer;
  pointer-events: all;
}
.hs-ring {
  r: 16px;
  fill-opacity: 0;
  transition: fill-opacity 0.15s, r 0.15s;
}
.hs-dot:hover .hs-ring,
.hs-dot.active .hs-ring {
  r: 22px;
  fill-opacity: 0.18;
}
.hs-dot.active circle:nth-child(2) { r: 8px; }
.hs-label {
  font-size: 10px; font-weight: 600;
  pointer-events: none;
}


/* ── Resize corner handles ── */
.rh {
  position: absolute;
  width: 10px; height: 10px;
  background: white;
  border: 2px solid var(--accent);
  border-radius: 2px;
  z-index: 30;
}
.rh.tl { top: -5px;    left: -5px;   cursor: nw-resize; }
.rh.tr { top: -5px;    right: -5px;  cursor: ne-resize; }
.rh.bl { bottom: -5px; left: -5px;   cursor: sw-resize; }
.rh.br { bottom: -5px; right: -5px;  cursor: se-resize; }

/* ── Canvas controls ── */
.canvas-controls {
  position: absolute;
  bottom: 14px; right: 14px;
  display: flex; align-items: center; gap: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 4px 6px;
  box-shadow: 0 2px 10px var(--shadow);
  z-index: 10;
}
.cc-btn {
  width: 24px; height: 24px; border: none; background: none; cursor: pointer;
  color: var(--text-muted); font-size: 13px; border-radius: 4px; display: flex; align-items: center; justify-content: center;
  transition: background 0.12s, color 0.12s;
}
.cc-btn:hover { background: var(--border); color: var(--text); }
.cc-btn.fit-btn { font-size: 12px; margin-left: 2px; padding: 0 4px; width: auto; }
.zoom-label { font-size: 11px; color: var(--text-muted); min-width: 38px; text-align: center; }

/* ── Bottom info bar (full width) ── */
.info-bar {
  height: 44px; flex-shrink: 0;
  background: var(--surface);
  border-top: 1px solid var(--border);
  border-left: 1px solid var(--border);
  border-right: 1px solid var(--border);
  display: flex; align-items: center; gap: 10px; padding: 0 20px;
  z-index: 3;
}
.shot-icon-lg  { font-size: 18px; }
.shot-meta     { display: flex; flex-direction: column; gap: 1px; }
.shot-title-lg { font-size: 13px; font-weight: 600; color: var(--text-hi); }
.shot-mood-lg  { font-size: 10px; color: var(--text-muted); }

/* Chat */
.ai-messages {
  flex: 1; overflow-y: auto; padding: 14px 14px 8px;
  display: flex; flex-direction: column; gap: 10px; min-height: 0;
}
.ai-msg        { display: flex; gap: 8px; align-items: flex-start; }
.ai-msg.user   { flex-direction: row-reverse; }
.ai-avatar     { width: 24px; height: 24px; border-radius: 6px; background: var(--avatar-bg); color: var(--avatar-text); font-size: 9px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ai-bubble     { max-width: 84%; padding: 7px 10px; border-radius: 8px; font-size: 11px; line-height: 1.55; background: var(--surface-2); color: var(--text-muted); border: 1px solid var(--border); }
.ai-msg.user .ai-bubble { background: var(--bubble-user-bg); border-color: var(--bubble-user-bdr); color: var(--bubble-user-text); }
.typing { display: flex; gap: 4px; align-items: center; padding: 10px 12px; }
.typing span { width: 5px; height: 5px; border-radius: 50%; background: var(--text-sub); animation: dot 1.2s ease-in-out infinite; }
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-5px)} }

.ai-input-row {
  display: flex; gap: 6px; padding: 10px 14px 14px;
  border-top: 1px solid var(--border); flex-shrink: 0;
}
.ai-input {
  flex: 1; background: var(--bg); border: 1px solid var(--border-md);
  border-radius: 8px; color: var(--text-hi); font-size: 12px; padding: 7px 10px; font-family: inherit;
  transition: border-color 0.15s;
}
.ai-input:focus        { outline: none; border-color: var(--accent-dim); }
.ai-input::placeholder { color: var(--text-ghost); }
.ai-send { width: 32px; height: 32px; background: var(--accent-dim); border: none; border-radius: 8px; color: white; font-size: 14px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.15s; }
.ai-send:hover:not(:disabled) { background: var(--accent); }
.ai-send:disabled { background: var(--border-md); cursor: not-allowed; }
.ai-input:disabled { opacity: 0.5; cursor: not-allowed; }

/* Spinners */
.spinner    { width: 16px; height: 16px; border: 2px solid var(--border-md); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; }
.spinner-sm { display: inline-block; width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3); border-top-color: white; border-radius: 50%; animation: spin 0.7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Inline crop layer ── */
.crop-layer {
  position: absolute; inset: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 5;
  pointer-events: none;
}
.crop-rect {
  position: absolute;
  border: 1.5px solid rgba(255,255,255,0.9);
  box-sizing: border-box;
  cursor: move;
  z-index: 6;
  /* shade outside selection via inset box-shadow */
  box-shadow: 0 0 0 9999px rgba(0,0,0,0.45);
}
/* Crop handle dots */
.ch {
  position: absolute;
  width: 8px; height: 8px;
  background: white;
  border: 1px solid rgba(0,0,0,0.25);
  border-radius: 1px;
  z-index: 7;
}
.ch.tl { top: -5px;    left: -5px;   cursor: nw-resize; }
.ch.tr { top: -5px;    right: -5px;  cursor: ne-resize; }
.ch.bl { bottom: -5px; left: -5px;   cursor: sw-resize; }
.ch.br { bottom: -5px; right: -5px;  cursor: se-resize; }

/* ── Dim overlay (covers everything except canvas-col when in crop mode) ── */
.crop-dim-overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.65);
  z-index: 30;
  pointer-events: none;
}
/* Canvas wrap rises above dim overlay in crop mode */
.canvas-wrap.crop-active {
  z-index: 31;
}

/* ── Crop icon button (bottom center of image) ── */
.crop-btn {
  position: absolute;
  top: calc(100% + 10px); left: 50%; transform: translateX(-50%);
  width: 28px; height: 28px; padding: 5px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 7px;
  cursor: pointer;
  color: var(--text-muted);
  box-shadow: 0 2px 8px var(--shadow);
  display: flex; align-items: center; justify-content: center;
  transition: background 0.12s, color 0.12s, border-color 0.12s;
  z-index: 20;
  pointer-events: all;
}
.crop-btn:hover { background: var(--surface-2); color: var(--text); border-color: var(--border-md); }
.crop-btn.active { background: var(--accent); color: white; border-color: var(--accent); }
.crop-btn svg { width: 100%; height: 100%; }

/* ── Ratio picker panel (below crop button) ── */
.ratio-panel {
  position: absolute;
  top: calc(100% + 48px); left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 5px;
  white-space: nowrap;
  z-index: 20;
  pointer-events: all;
  user-select: none;
}
.ratio-chip {
  padding: 3px 8px; border: 1px solid var(--border-md);
  border-radius: 5px; background: var(--bg);
  color: var(--text-muted); font-size: 11px; font-weight: 500;
  cursor: pointer; transition: background 0.1s, color 0.1s, border-color 0.1s;
  white-space: nowrap;
}
.ratio-chip:hover { background: var(--accent); color: white; border-color: var(--accent); }

/* ── Crop confirm bar (fixed bottom-right, above dim overlay) ── */
.crop-confirm-bar {
  position: fixed;
  bottom: 24px; right: 24px;
  display: flex; gap: 6px;
  z-index: 32;
}
.ccb-cancel {
  padding: 6px 14px; border-radius: 7px;
  border: 1px solid var(--border-md);
  background: var(--surface); color: var(--text-muted);
  font-size: 12px; cursor: pointer;
  transition: border-color 0.12s, color 0.12s;
}
.ccb-cancel:hover { border-color: var(--text-muted); color: var(--text); }
.ccb-confirm {
  padding: 6px 16px; border-radius: 7px; border: none;
  background: var(--accent); color: white;
  font-size: 12px; font-weight: 600; cursor: pointer;
  transition: background 0.12s, opacity 0.12s;
}
.ccb-confirm:hover:not(:disabled) { background: var(--accent-dim); }
.ccb-confirm:disabled { opacity: 0.35; cursor: not-allowed; }

/* Unsaved-changes dialog */
.ud-backdrop {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.55);
  z-index: 200;
  display: flex; align-items: center; justify-content: center;
}
.ud-modal {
  background: var(--surface);
  border: 1px solid var(--border-md);
  border-radius: 12px;
  padding: 24px 28px;
  min-width: 300px;
  display: flex; flex-direction: column; gap: 12px;
}
.ud-title { font-size: 15px; font-weight: 600; color: var(--text-hi, var(--text)); }
.ud-body  { font-size: 13px; color: var(--text-sub); }
.ud-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
.ud-btn {
  padding: 7px 16px; border-radius: 6px;
  font-size: 13px; font-weight: 500; cursor: pointer; border: none;
  transition: background 0.15s;
}
.ud-cancel  { background: none; color: var(--text-muted); border: 1px solid var(--border-md); }
.ud-cancel:hover  { border-color: var(--text-sub); }
.ud-discard { background: var(--surface-2, var(--border)); color: var(--text); }
.ud-discard:hover { background: var(--border-md); }
.ud-save    { background: var(--accent); color: white; }
.ud-save:hover    { background: var(--accent-dim, #2d8f5f); }
</style>
