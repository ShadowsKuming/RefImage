<template>
  <Teleport to="body">
    <div class="ave-backdrop" @click.self="emit('close')">
      <div class="ave-panel">
        <div class="ave-head">
          <span class="ave-title">{{ t('projectCanvas.avatarEditorTitle') }}</span>
          <button class="ave-x" @click="emit('close')"><X /></button>
        </div>

        <!-- crop stage -->
        <div class="ave-stage" ref="stageEl">
          <template v-if="srcUrl">
            <img
              ref="imgEl" :src="srcUrl" class="ave-img" draggable="false"
              @load="onImgLoad"
            />
            <!-- frame (dims outside via huge box-shadow); drag to move -->
            <div
              class="ave-frame"
              :style="frameStyle"
              @pointerdown="onDown"
            ><span class="ave-frame-circle" /></div>
          </template>
          <div v-else class="ave-empty">
            <ImageIcon /><span>{{ t('projectCanvas.avatarNoImage') }}</span>
          </div>
        </div>

        <!-- size slider -->
        <div v-if="srcUrl" class="ave-size">
          <span class="ave-size-lbl">{{ t('projectCanvas.avatarSize') }}</span>
          <input type="range" min="20" max="100" v-model.number="sizePct" class="ave-range" @input="clampFrame" />
        </div>
        <p v-if="srcUrl" class="ave-hint">{{ t('projectCanvas.avatarDragHint') }}</p>

        <!-- actions -->
        <div class="ave-tools">
          <label class="ave-tool">
            <input type="file" accept="image/*" hidden @change="onUpload" />
            <Upload /><span>{{ t('projectCanvas.avatarUpload') }}</span>
          </label>
          <button v-if="srcUrl" class="ave-tool" :disabled="busy" @click="runAuto">
            <Sparkles :class="{ spin: autoLoading }" /><span>{{ t('projectCanvas.avatarAuto') }}</span>
          </button>
        </div>

        <div class="ave-actions">
          <button class="ave-cancel" @click="emit('close')">{{ t('projectCanvas.cancel') }}</button>
          <button class="ave-save" :disabled="!srcUrl || busy" @click="save">{{ t('projectCanvas.avatarSave') }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { X, Upload, Sparkles, Image as ImageIcon } from 'lucide-vue-next'
import { useApi } from '~/composables/useApi'
import { useLocale } from '~/composables/useLocale'

const props = defineProps<{
  projectId: string
  character: { id: string; avatar_src?: string | null; avatar_crop?: { x: number; y: number; size: number } | null }
}>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'saved', url: string): void }>()

const { t } = useLocale()
const api = useApi()
const { public: { apiBase: BASE } } = useRuntimeConfig()

const srcUrl = ref<string>(props.character.avatar_src ? BASE + props.character.avatar_src : '')
const stageEl = ref<HTMLElement | null>(null)
const imgEl = ref<HTMLImageElement | null>(null)
const busy = ref(false)
const autoLoading = ref(false)

// displayed image rect within the stage (px, relative to stage top-left)
const disp = reactive({ left: 0, top: 0, w: 0, h: 0 })
// crop frame position (px, relative to stage) + size as % of the image's short side
const frame = reactive({ x: 0, y: 0 })
const sizePct = ref(70)

const frameSizePx = computed(() => (sizePct.value / 100) * Math.min(disp.w, disp.h))
const frameStyle = computed(() => ({
  left: frame.x + 'px', top: frame.y + 'px',
  width: frameSizePx.value + 'px', height: frameSizePx.value + 'px',
}))

function measure() {
  const img = imgEl.value, stage = stageEl.value
  if (!img || !stage) return
  const ir = img.getBoundingClientRect(), sr = stage.getBoundingClientRect()
  disp.left = ir.left - sr.left; disp.top = ir.top - sr.top
  disp.w = ir.width; disp.h = ir.height
}

function applyRect(r: { x: number; y: number; size: number }) {
  sizePct.value = Math.round(Math.max(20, Math.min(100, r.size * 100)))
  frame.x = disp.left + r.x * disp.w
  frame.y = disp.top + r.y * disp.h
  clampFrame()
}

function onImgLoad() {
  measure()
  if (props.character.avatar_crop) applyRect(props.character.avatar_crop)
  else centerFrame()
}

function centerFrame() {
  sizePct.value = 70
  frame.x = disp.left + (disp.w - frameSizePx.value) / 2
  frame.y = disp.top + (disp.h - frameSizePx.value) / 2
}

function clampFrame() {
  const s = frameSizePx.value
  frame.x = Math.max(disp.left, Math.min(frame.x, disp.left + disp.w - s))
  frame.y = Math.max(disp.top, Math.min(frame.y, disp.top + disp.h - s))
}

// drag to move
let dragging = false, sx = 0, sy = 0, fx = 0, fy = 0
function onDown(e: PointerEvent) {
  dragging = true; sx = e.clientX; sy = e.clientY; fx = frame.x; fy = frame.y
  ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
}
function onMove(e: PointerEvent) {
  if (!dragging) return
  frame.x = fx + (e.clientX - sx); frame.y = fy + (e.clientY - sy)
  clampFrame()
}
function onUp() {
  dragging = false
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerup', onUp)
}

async function onUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  busy.value = true
  try {
    const { src_url } = await api.uploadAvatarSource(props.projectId, props.character.id, file)
    srcUrl.value = BASE + src_url + (src_url.includes('?') ? '' : '?t=' + Date.now())
    // frame will re-init on the new image's @load (no stored crop → centered)
    props.character.avatar_crop = null
  } catch (err) {
    console.error('avatar upload failed', err)
  } finally {
    busy.value = false
    input.value = ''
  }
}

async function runAuto() {
  autoLoading.value = true
  try {
    const r = await api.autoAvatarCrop(props.projectId, props.character.id)
    measure(); applyRect(r)
  } catch (err) {
    console.error('auto crop failed', err)
  } finally {
    autoLoading.value = false
  }
}

async function save() {
  measure()
  const size = frameSizePx.value / Math.min(disp.w, disp.h)
  const x = (frame.x - disp.left) / disp.w
  const y = (frame.y - disp.top) / disp.h
  busy.value = true
  try {
    const { avatar_url } = await api.cropAvatar(props.projectId, props.character.id, { x, y, size })
    emit('saved', avatar_url)
    emit('close')
  } catch (err) {
    console.error('crop failed', err)
  } finally {
    busy.value = false
  }
}

onMounted(() => { if (imgEl.value?.complete) onImgLoad() })
</script>

<style scoped>
.ave-backdrop {
  position: fixed; inset: 0; z-index: 10001;
  background: rgba(0,0,0,0.6); backdrop-filter: blur(3px);
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.ave-panel {
  width: min(420px, 92vw); background: var(--surface);
  border: 1px solid var(--border-md); border-radius: 16px;
  box-shadow: 0 16px 48px var(--shadow); padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
}
.ave-head { display: flex; align-items: center; justify-content: space-between; }
.ave-title { font-size: 14px; font-weight: 700; color: var(--text-hi); }
.ave-x {
  width: 28px; height: 28px; border: none; background: none; cursor: pointer;
  color: var(--text-quiet); border-radius: 7px; display: flex; align-items: center; justify-content: center;
}
.ave-x:hover { background: var(--surface-inset); color: var(--text-2); }
.ave-x :deep(svg) { width: 16px; height: 16px; }

.ave-stage {
  position: relative; width: 100%; height: 340px; overflow: hidden;
  border-radius: 12px; background: var(--surface-inset); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
}
.ave-img { max-width: 100%; max-height: 100%; object-fit: contain; user-select: none; display: block; }
.ave-frame {
  position: absolute; box-sizing: border-box; cursor: grab;
  border: 2px solid #fff; box-shadow: 0 0 0 9999px rgba(0,0,0,0.5);
}
.ave-frame:active { cursor: grabbing; }
.ave-frame-circle {
  position: absolute; inset: 0; border-radius: 50%;
  border: 1px dashed rgba(255,255,255,0.7); pointer-events: none;
}
.ave-empty {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  color: var(--text-quiet); font-size: 12px;
}
.ave-empty :deep(svg) { width: 28px; height: 28px; }

.ave-size { display: flex; align-items: center; gap: 10px; }
.ave-size-lbl { font-size: 11px; color: var(--text-quiet); white-space: nowrap; }
.ave-range { flex: 1; accent-color: var(--accent); cursor: pointer; }
.ave-hint { font-size: 10.5px; color: var(--text-quiet); text-align: center; margin: -4px 0 0; }

.ave-tools { display: flex; gap: 8px; }
.ave-tool {
  flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  padding: 9px; border-radius: 9px; cursor: pointer;
  font-size: 12px; font-weight: 600; color: var(--accent);
  background: none; border: 1px dashed var(--border-focus);
  transition: background 0.15s, border-color 0.15s;
}
.ave-tool:hover:not(:disabled) { background: var(--surface-inset); border-color: var(--accent-dim); }
.ave-tool:disabled { opacity: 0.6; cursor: default; }
.ave-tool :deep(svg) { width: 14px; height: 14px; }
.ave-tool :deep(svg.spin) { animation: ave-spin 0.8s linear infinite; }
@keyframes ave-spin { to { transform: rotate(360deg); } }

.ave-actions { display: flex; gap: 8px; justify-content: flex-end; }
.ave-cancel, .ave-save {
  padding: 8px 18px; border-radius: 8px; font-size: 12.5px; font-weight: 600; cursor: pointer;
}
.ave-cancel { background: none; border: 1px solid var(--border-md); color: var(--text-2); }
.ave-cancel:hover { border-color: var(--text-quiet); }
.ave-save { background: var(--accent); border: none; color: #fff; }
.ave-save:hover:not(:disabled) { background: var(--accent-hover); }
.ave-save:disabled { opacity: 0.5; cursor: default; }
</style>
