<template>
  <div class="project-page">

    <!-- Top bar -->
    <div class="top-bar">
      <div class="breadcrumb">
        <button class="back-btn" @click="navigateTo('/')">← 主页</button>
        <span class="bc-sep">/</span>
        <span class="bc-item">{{ project.work }}</span>
        <span class="bc-sep">·</span>
        <span class="bc-current">{{ project.character }}</span>
      </div>
      <div class="tb-actions">
        <button class="tb-btn" @click="resetLayout">重置布局</button>
        <button class="tb-btn" :disabled="exporting" @click="doExport">
          {{ exporting ? '导出中…' : '导出项目' }}
        </button>
      </div>
    </div>

    <!-- Docking canvas — mousemove here handles drag tracking -->
    <div class="canvas" @mousemove="onCanvasMouseMove">
      <DockLayout
        :node="layout"
        :dragging="dragging"
        :hoverInfo="hoverInfo"
        :titles="panelTitles"
        :collapsible="['summary', 'settings', 'ai']"
        :collapsed="collapsed"
        :collapse-dir="null"
        @panel-mousedown="startDrag"
        @move="handleMove"
        @toggle-collapse="toggleCollapse"
      >

        <!-- ① 拍摄计划 -->
        <template #shots>
          <div class="p-inner shots-panel">
            <!-- Panel toolbar -->
            <div class="shots-toolbar">
              <span class="shots-count">{{ shots.length }} 张</span>
              <div class="view-toggle">
                <button class="vt-btn" :class="{ active: viewMode === 'grid' }" title="网格" @click="viewMode = 'grid'">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="0" y="0" width="6" height="6" rx="1" fill="currentColor"/>
                    <rect x="8" y="0" width="6" height="6" rx="1" fill="currentColor"/>
                    <rect x="0" y="8" width="6" height="6" rx="1" fill="currentColor"/>
                    <rect x="8" y="8" width="6" height="6" rx="1" fill="currentColor"/>
                  </svg>
                </button>
                <button class="vt-btn" :class="{ active: viewMode === 'list' }" title="列表" @click="viewMode = 'list'">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="0" y="1" width="14" height="2.5" rx="1" fill="currentColor"/>
                    <rect x="0" y="5.75" width="14" height="2.5" rx="1" fill="currentColor"/>
                    <rect x="0" y="10.5" width="14" height="2.5" rx="1" fill="currentColor"/>
                  </svg>
                </button>
              </div>
            </div>

            <!-- Grid view -->
            <div v-if="viewMode === 'grid'" class="shots-grid">
              <div
                v-for="shot in shots"
                :key="shot.shot_id"
                class="shot-card"
                :class="{ 'shot-card-no-thumb': !shot.image_url, 'shot-card-refined': shot.status === 'refined' }"
                @click="navigateTo(`/projects/${projectId}/shots/${shot.shot_id}`)"
              >
                <div v-if="shot.image_url" class="sc-thumb-wrap">
                  <img :src="BASE_URL + shot.image_url" class="sc-thumb" :alt="shot.title" />
                  <div v-if="shot.status === 'refined'" class="sc-refined-overlay">✓ 已完善</div>
                </div>
                <div class="sc-mood">{{ shot.mood }}</div>
                <div class="sc-title">{{ shot.title }}</div>
                <div class="sc-desc" v-if="shot.description">{{ shot.description }}</div>
                <div class="sc-footer">
                  <span v-if="shot.status === 'error'" class="sc-error-dot" title="生成出错">!</span>
                  <span v-else class="sc-spacer" />
                  <button class="sc-del" @click.stop="removeShot(shot.shot_id)" title="删除">✕</button>
                </div>
              </div>
              <div class="shot-add" @click="shotModalOpen = true">
                <span class="add-icon">+</span>
                <span class="add-text">新增拍摄</span>
              </div>
            </div>

            <!-- List view -->
            <div v-else class="shots-list">
              <div
                v-for="shot in shots"
                :key="shot.shot_id"
                class="sl-row"
                :class="{ 'sl-refined': shot.status === 'refined' }"
                @click="navigateTo(`/projects/${projectId}/shots/${shot.shot_id}`)"
              >
                <div class="sl-thumb-wrap">
                  <img v-if="shot.image_url" :src="BASE_URL + shot.image_url" class="sl-thumb" :alt="shot.title" />
                  <div v-else class="sl-thumb-empty">—</div>
                </div>
                <div class="sl-info">
                  <span class="sl-title">{{ shot.title }}</span>
                  <span v-if="shot.mood" class="sl-mood">{{ shot.mood }}</span>
                </div>
                <div class="sl-right">
                  <span v-if="shot.status === 'refined'" class="sl-badge-refined">已完善</span>
                  <span v-else-if="shot.status === 'error'" class="sl-badge-error">错误</span>
                  <button class="sc-del" @click.stop="removeShot(shot.shot_id)" title="删除">✕</button>
                </div>
              </div>
              <button class="sl-add" @click="shotModalOpen = true">+ 新增拍摄</button>
            </div>
          </div>
        </template>

        <!-- ② 拍摄总结 -->
        <template #summary>
          <div class="p-inner">
            <div class="summary-row">
              <span class="sr-icon">📍</span>
              <div class="sr-body">
                <span class="sr-label">场地</span>
                <div class="tags">
                  <span v-for="l in summary.locations" :key="l" class="tag">{{ l }}</span>
                </div>
              </div>
            </div>
            <div class="summary-row">
              <span class="sr-icon">💡</span>
              <div class="sr-body">
                <span class="sr-label">设备</span>
                <div class="tags">
                  <span v-for="e in summary.equipment" :key="e" class="tag">{{ e }}</span>
                </div>
              </div>
            </div>
            <div class="summary-row">
              <span class="sr-icon">🕐</span>
              <div class="sr-body">
                <span class="sr-label">最佳时段</span>
                <span class="sr-text">{{ summary.bestTime }}</span>
              </div>
            </div>
            <div class="summary-row">
              <span class="sr-icon">👗</span>
              <div class="sr-body">
                <span class="sr-label">服装道具</span>
                <div class="tags">
                  <span v-for="p in summary.props" :key="p" class="tag">{{ p }}</span>
                </div>
              </div>
            </div>
            <div v-if="summary.styleNotes" class="summary-row">
              <span class="sr-icon">✏️</span>
              <div class="sr-body">
                <span class="sr-label">风格备注</span>
                <span class="sr-text">{{ summary.styleNotes }}</span>
              </div>
            </div>
          </div>
        </template>

        <!-- ③ 设定面板 -->
        <template #settings>
          <div class="p-inner">

            <!-- 作品设定 -->
            <div class="setting-block">
              <div class="s-section">作品设定</div>
              <div class="s-row"><span class="s-key">类型</span><span class="s-val">{{ worldSetting?.genre ?? '—' }}</span></div>
              <div class="s-row"><span class="s-key">时代</span><span class="s-val">{{ worldSetting?.era ?? '—' }}</span></div>
              <div class="s-row"><span class="s-key">时间地点</span><span class="s-val">{{ worldSetting?.timeline ?? '—' }}</span></div>
              <div class="s-row"><span class="s-key">视觉</span><span class="s-val">{{ worldSetting?.tone?.visual ?? '—' }}</span></div>
              <div class="s-row"><span class="s-key">叙事</span><span class="s-val">{{ worldSetting?.tone?.narrative ?? '—' }}</span></div>
              <div class="s-row"><span class="s-key">情感</span><span class="s-val">{{ worldSetting?.tone?.emotion ?? '—' }}</span></div>
              <div v-if="worldSetting?.synopsis" class="s-row s-row-top">
                <span class="s-key">梗概</span>
                <span class="s-val">{{ worldSetting.synopsis }}</span>
              </div>
              <div v-if="worldSetting?.themes?.length" class="s-row s-row-top">
                <span class="s-key">主题</span>
                <div class="tags"><span v-for="t in worldSetting.themes" :key="t" class="tag">{{ t }}</span></div>
              </div>
              <div v-if="worldSetting?.iconic_settings?.length" class="s-row s-row-top">
                <span class="s-key">场景</span>
                <div class="tags"><span v-for="s in worldSetting.iconic_settings" :key="s" class="tag">{{ s }}</span></div>
              </div>
            </div>

            <!-- 人物设定 -->
            <div class="setting-block">
              <div class="s-section">人物设定</div>
              <div class="s-row"><span class="s-key">角色</span><span class="s-val">{{ project.character }} · {{ project.work }}</span></div>
              <div class="s-row"><span class="s-key">定位</span><span class="s-val">{{ charBg?.role ?? '—' }}</span></div>
              <div class="s-row"><span class="s-key">年龄</span><span class="s-val">{{ charBg?.age ?? '—' }}</span></div>
              <div v-if="charBg?.backstory" class="s-row s-row-top">
                <span class="s-key">身世</span>
                <span class="s-val">{{ charBg.backstory }}</span>
              </div>
              <div class="s-row"><span class="s-key">外在</span><span class="s-val">{{ charBg?.personality?.surface ?? '—' }}</span></div>
              <div class="s-row"><span class="s-key">内心</span><span class="s-val">{{ charBg?.personality?.inner ?? '—' }}</span></div>
              <div class="s-row"><span class="s-key">渴望</span><span class="s-val">{{ charBg?.personality?.core_desire ?? '—' }}</span></div>
              <div v-if="charBg?.iconic_moments?.length" class="s-row s-row-top">
                <span class="s-key">瞬间</span>
                <div class="tags"><span v-for="m in charBg.iconic_moments" :key="m" class="tag">{{ m }}</span></div>
              </div>
            </div>

            <!-- 外貌特征 -->
            <div v-if="visualSpecFields.length" class="setting-block">
              <div class="s-section">外貌特征</div>
              <div v-for="f in visualSpecFields" :key="f.label" class="s-row s-row-top">
                <span class="s-key">{{ f.label }}</span>
                <span class="s-val">{{ f.value }}</span>
              </div>
            </div>

            <!-- 角色参考图 -->
            <div class="setting-block">
              <div class="s-section">角色参考图</div>
              <div class="refs-mini-grid">
                <img
                  v-for="(url, i) in allRefUrls" :key="i"
                  :src="url" class="ref-mini-img"
                  :class="{ 'ref-extra': i >= refUrls.length }"
                  :title="i >= refUrls.length ? '补充参考图' : '原始参考图'"
                  :alt="`参考 ${i + 1}`"
                  @click="openLightbox(i)"
                />
                <label class="ref-add-card">
                  <input type="file" accept="image/*" multiple hidden @change="onAddRefs" />
                  <span class="ref-add-plus">+</span>
                </label>
              </div>
            </div>

          </div>
        </template>

        <!-- ④ AI 规划助手 -->
        <template #ai>
          <div class="ai-wrap">
            <div class="ai-messages" ref="aiContainer">
              <div
                v-for="(msg, i) in aiMessages"
                :key="i"
                class="ai-msg"
                :class="msg.role"
              >
                <div v-if="msg.role === 'agent'" class="ai-avatar">AI</div>
                <div class="ai-bubble">{{ msg.text }}</div>
              </div>
              <div v-if="aiLoading" class="ai-msg agent">
                <div class="ai-avatar">AI</div>
                <div class="ai-bubble typing"><span /><span /><span /></div>
              </div>
            </div>
            <div class="ai-input-row">
              <input
                v-model="aiInput"
                class="ai-input"
                placeholder="问问 AI…"
                @keydown.enter.exact.prevent="sendAiMessage"
              />
              <button class="ai-send" @click="sendAiMessage">↑</button>
            </div>
          </div>
        </template>

      </DockLayout>
    </div>

    <!-- New shot modal -->
    <Teleport to="body">
      <div v-if="shotModalOpen" class="shot-modal-overlay" @click.self="shotModalOpen = false">
        <div class="shot-modal">
          <div class="sm-title">新增拍摄</div>
          <input v-model="newShotTitle" class="sm-input" placeholder="如「雨中漫步」" @keydown.enter="addShot" />
          <div class="sm-actions">
            <button class="sm-btn sm-cancel" @click="shotModalOpen = false">取消</button>
            <button class="sm-btn sm-ok" :disabled="!newShotTitle.trim() || shotAdding" @click="addShot">
              {{ shotAdding ? '…' : '添加' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Lightbox -->
    <Teleport to="body">
      <div v-if="lightboxIndex !== null" class="lightbox" @click.self="lightboxIndex = null">
        <button class="lb-close" @click="lightboxIndex = null">✕</button>
        <button v-if="lightboxIndex > 0" class="lb-arrow lb-prev" @click="lightboxIndex--">‹</button>
        <button v-if="lightboxIndex < allRefUrls.length - 1" class="lb-arrow lb-next" @click="lightboxIndex++">›</button>
        <div class="lb-img-wrap">
          <img :src="allRefUrls[lightboxIndex]" class="lb-img" :alt="`参考 ${lightboxIndex + 1}`" />
          <div class="lb-badge" :class="lightboxIndex >= refUrls.length ? 'lb-badge-extra' : 'lb-badge-orig'">
            {{ lightboxIndex >= refUrls.length ? '补充参考' : '原始参考' }}
          </div>
        </div>
        <div class="lb-counter">{{ lightboxIndex + 1 }} / {{ allRefUrls.length }}</div>
      </div>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import type { LayoutNode, PanelId, Edge } from '~/components/DockLayout.vue'
import { useApi } from '~/composables/useApi'

definePageMeta({ ssr: false })

const route = useRoute()
const api = useApi()

// ── Project data ──────────────────────────────────────────
const projectData = ref<any>(null)

const projectId = computed(() =>
  Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
)

const project = computed(() => ({
  work:      projectData.value?.series    ?? '—',
  character: projectData.value?.character ?? '—',
}))

const BASE_URL = 'http://localhost:8000'

const refUrls = computed<string[]>(() =>
  (projectData.value?.refs ?? []).map((r: string) => BASE_URL + r)
)
const extraRefUrls = computed<string[]>(() =>
  (projectData.value?.extra_refs ?? []).map((r: string) => BASE_URL + r)
)
const allRefUrls = computed<string[]>(() => [...refUrls.value, ...extraRefUrls.value])

// ── Lightbox ──────────────────────────────────────────────
const lightboxIndex = ref<number | null>(null)
function openLightbox(i: number) { lightboxIndex.value = i }

// Keyboard navigation
if (typeof window !== 'undefined') {
  window.addEventListener('keydown', (e) => {
    if (lightboxIndex.value === null) return
    if (e.key === 'Escape') lightboxIndex.value = null
    if (e.key === 'ArrowLeft' && lightboxIndex.value > 0) lightboxIndex.value--
    if (e.key === 'ArrowRight' && lightboxIndex.value < allRefUrls.value.length - 1) lightboxIndex.value++
  })
}

// ── Extra refs upload ─────────────────────────────────────
async function onAddRefs(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files?.length) return
  const uploads = Array.from(files).map(f => api.addExtraRef(projectId.value, f))
  const results = await Promise.all(uploads)
  if (!projectData.value) return
  const newUrls = results.map(r => BASE_URL + r.url)
  projectData.value.extra_refs = [...(projectData.value.extra_refs ?? []), ...results.map(r => r.url)]
  // Reset input so same file can be re-selected
  ;(e.target as HTMLInputElement).value = ''
}

const worldSetting = computed(() => projectData.value?.world?.worldSetting ?? null)
const charBg       = computed(() => projectData.value?.character_data?.characterBackground ?? null)

const visualSpecFields = computed(() => {
  const vs = projectData.value?.visual_spec
  if (!vs) return []
  // Multilang dict {zh,en,ja} or legacy plain-text — always show zh by default
  const spec: string = typeof vs === 'object' ? (vs.zh ?? '') : vs
  return spec.split('\n')
    .filter(Boolean)
    .map(line => {
      const idx = line.indexOf(': ')
      if (idx === -1) return null
      return { label: line.slice(0, idx), value: line.slice(idx + 2) }
    })
    .filter(Boolean) as { label: string; value: string }[]
})

const summary = computed(() => {
  const brief = projectData.value?.plan?.brief ?? {}
  return {
    locations:  brief.locations?.length  ? brief.locations  : ['待 AI 规划'],
    equipment:  brief.equipment?.length  ? brief.equipment  : ['待 AI 规划'],
    bestTime:   brief.best_time          ?? '待 AI 规划',
    props:      brief.props?.length      ? brief.props      : ['待 AI 规划'],
    styleNotes: brief.style_notes        ?? '',
  }
})

const exporting = ref(false)
async function doExport() {
  exporting.value = true
  try {
    await api.exportProject(projectId.value)
  } catch (e) {
    console.error('Export failed', e)
  }
  exporting.value = false
}

onMounted(async () => {
  try {
    projectData.value = await api.getProject(projectId.value)
    const savedHistory: { role: string; text: string }[] = projectData.value?.plan?.chat_history ?? []
    if (savedHistory.length > 0) {
      aiMessages.value = savedHistory
    }
  } catch (e) {
    console.error('Failed to load project', e)
  }
})

// ── Shots ─────────────────────────────────────────────────
const shots       = computed<any[]>(() => projectData.value?.shots ?? [])
const viewMode    = ref<'grid' | 'list'>('grid')
const shotModalOpen = ref(false)
const newShotTitle  = ref('')
const newShotMood   = ref('')
const shotAdding    = ref(false)

async function addShot() {
  if (!newShotTitle.value.trim() || shotAdding.value) return
  shotAdding.value = true
  try {
    const shot = await api.createShot(projectId.value, newShotTitle.value.trim(), '')
    if (projectData.value) {
      projectData.value.shots = [...(projectData.value.shots ?? []), shot]
    }
    newShotTitle.value = ''
    shotModalOpen.value = false
  } catch (e) {
    console.error('Failed to create shot', e)
  }
  shotAdding.value = false
}

async function removeShot(shotId: string) {
  try {
    await api.deleteShot(projectId.value, shotId)
    if (projectData.value) {
      projectData.value.shots = projectData.value.shots.filter((s: any) => s.shot_id !== shotId)
    }
  } catch (e) {
    console.error('Failed to delete shot', e)
  }
}


// ── AI assistant ──────────────────────────────────────────
const GREETING = '你好！可以帮你规划拍摄场景、整理设备需求或优化拍摄故事。随时问我。'
const aiContainer = ref<HTMLElement | null>(null)
const aiInput     = ref('')
const aiLoading   = ref(false)
const aiMessages  = ref<{ role: string; text: string }[]>([
  { role: 'agent', text: GREETING },
])

async function sendAiMessage() {
  const text = aiInput.value.trim()
  if (!text || aiLoading.value) return
  aiInput.value = ''
  // history = all messages before this new one
  const history = [...aiMessages.value]
  aiMessages.value.push({ role: 'user', text })
  aiLoading.value = true
  await nextTick()
  if (aiContainer.value) aiContainer.value.scrollTop = aiContainer.value.scrollHeight
  try {
    const { reply, brief } = await api.projectChat(projectId.value, text, history)
    aiMessages.value.push({ role: 'agent', text: reply })
    if (brief && projectData.value) {
      projectData.value.plan = { ...projectData.value.plan, brief }
    }
  } catch {
    aiMessages.value.push({ role: 'agent', text: '出了点问题，请稍后重试。' })
  }
  aiLoading.value = false
  await nextTick()
  if (aiContainer.value) aiContainer.value.scrollTop = aiContainer.value.scrollHeight
}

// ── Dock layout ───────────────────────────────────────────
const panelTitles: Record<string, string> = {
  shots:    '拍摄计划',
  summary:  '拍摄总结',
  settings: '设定',
  ai:       'AI 规划助手',
}

const defaultLayout = (): LayoutNode => ({
  type: 'split', dir: 'h', ratio: 22,
  a: { type: 'panel', id: 'settings' },
  b: {
    type: 'split', dir: 'h', ratio: 70,
    a: {
      type: 'split', dir: 'v', ratio: 60,
      a: { type: 'panel', id: 'shots' },
      b: { type: 'panel', id: 'ai' },
    },
    b: { type: 'panel', id: 'summary' },
  },
})

const layout    = ref<LayoutNode>(defaultLayout())
const dragging  = ref<PanelId | null>(null)
const hoverInfo = ref<{ panelId: PanelId; edge: Edge } | null>(null)
const collapsed = ref<PanelId[]>([])
let   ghostEl: HTMLElement | null = null

function resetLayout() { layout.value = defaultLayout(); collapsed.value = [] }

function toggleCollapse(id: PanelId) {
  const idx = collapsed.value.indexOf(id)
  if (idx === -1) collapsed.value.push(id)
  else collapsed.value.splice(idx, 1)
}

// ── Drag (mouse events) ───────────────────────────────────
function startDrag(panelId: PanelId) {
  dragging.value = panelId

  ghostEl = document.createElement('div')
  ghostEl.textContent = panelTitles[panelId]
  ghostEl.style.cssText = [
    'position:fixed', 'pointer-events:none', 'z-index:9999',
    'background:var(--avatar-bg)', 'border:1px solid var(--accent)', 'border-radius:6px',
    'padding:4px 14px', 'font-size:12px', 'color:var(--text-accent)',
    'opacity:0', 'transition:opacity 0.1s', 'white-space:nowrap',
    'left:-999px', 'top:-999px',
  ].join(';')
  document.body.appendChild(ghostEl)
  requestAnimationFrame(() => { if (ghostEl) ghostEl.style.opacity = '0.9' })

  window.addEventListener('mouseup', onMouseUp, { once: true })
}

function onCanvasMouseMove(e: MouseEvent) {
  if (!dragging.value) return

  if (ghostEl) {
    ghostEl.style.left = `${e.clientX + 14}px`
    ghostEl.style.top  = `${e.clientY - 12}px`
  }

  const els = document.elementsFromPoint(e.clientX, e.clientY) as HTMLElement[]
  const panelEl = els.find(el => el.dataset?.panelId && el.dataset.panelId !== dragging.value)

  if (!panelEl) { hoverInfo.value = null; return }

  const rect   = panelEl.getBoundingClientRect()
  const xRatio = (e.clientX - rect.left)  / rect.width
  const yRatio = (e.clientY - rect.top)   / rect.height
  const T      = 0.25

  let edge: Edge | null = null
  if      (xRatio < T)     edge = 'left'
  else if (xRatio > 1 - T) edge = 'right'
  else if (yRatio < T)     edge = 'top'
  else if (yRatio > 1 - T) edge = 'bottom'

  hoverInfo.value = edge ? { panelId: panelEl.dataset.panelId as PanelId, edge } : null
}

function onMouseUp() {
  if (hoverInfo.value && dragging.value) {
    handleMove({ target: hoverInfo.value.panelId, panel: dragging.value, edge: hoverInfo.value.edge })
  }
  if (ghostEl) { ghostEl.remove(); ghostEl = null }
  dragging.value  = null
  hoverInfo.value = null
}

// ── Layout tree operations ────────────────────────────────
function removePanel(node: LayoutNode, id: PanelId): LayoutNode | null {
  if (node.type === 'panel') return node.id === id ? null : node
  const a = removePanel(node.a, id)
  const b = removePanel(node.b, id)
  if (a === null) return b
  if (b === null) return a
  return { ...node, a, b }
}

function insertPanel(node: LayoutNode, targetId: PanelId, panel: LayoutNode, edge: Edge): LayoutNode {
  if (node.type === 'panel') {
    if (node.id !== targetId) return node
    const dir: 'h' | 'v' = edge === 'left' || edge === 'right' ? 'h' : 'v'
    const before = edge === 'left' || edge === 'top'
    return { type: 'split', dir, ratio: 50, a: before ? panel : node, b: before ? node : panel }
  }
  return { ...node, a: insertPanel(node.a, targetId, panel, edge), b: insertPanel(node.b, targetId, panel, edge) }
}

function handleMove({ target, panel, edge }: { target: PanelId; panel: PanelId; edge: Edge }) {
  if (target === panel) return
  const panelNode: LayoutNode = { type: 'panel', id: panel }
  const without = removePanel(layout.value, panel)
  if (!without) return
  layout.value = insertPanel(without, target, panelNode, edge)
  dragging.value = null
}
</script>

<style scoped>
.project-page {
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}
.breadcrumb { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.back-btn   { background: none; border: none; color: var(--text-sub); font-size: 12px; cursor: pointer; padding: 0; }
.back-btn:hover { color: var(--text); }
.bc-sep     { color: var(--border-md); }
.bc-item    { color: var(--text-dim); }
.bc-current { color: var(--text-accent); font-weight: 600; }
.tb-actions { display: flex; gap: 8px; }
.tb-btn {
  padding: 5px 14px; background: var(--border); border: 1px solid var(--border-strong);
  border-radius: 6px; color: var(--text-muted); font-size: 12px; cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.tb-btn:hover { background: var(--border-md); color: var(--text); }

/* ── Canvas ── */
.canvas { flex: 1; overflow: hidden; padding: 10px; box-sizing: border-box; }

/* ── Shared pane inner ── */
.p-inner {
  padding: 18px 20px;
  height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
}
.p-inner.shots-panel { padding: 14px 16px; }

/* ── 拍摄计划 ── */
.shots-panel { display: flex; flex-direction: column; gap: 12px; padding: 14px 16px; }
.shots-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}
.shots-count { font-size: 11px; color: var(--text-ghost); }
.view-toggle { display: flex; gap: 2px; }
.vt-btn {
  width: 28px; height: 28px; border: none; background: none;
  color: var(--text-ghost); cursor: pointer; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.12s, color 0.12s;
}
.vt-btn:hover { background: var(--surface-inset); color: var(--text-muted); }
.vt-btn.active { background: var(--surface-inset); color: var(--accent); }

.shots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
.shot-card {
  min-height: 130px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 12px;
  padding: 0; display: flex; flex-direction: column; gap: 0;
  cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s;
  overflow: hidden;
}
.shot-card:hover { border-color: var(--accent-dim); box-shadow: 0 2px 12px var(--shadow); }
.shot-card-refined { border-color: var(--badge-done-text); }
.shot-card-no-thumb { padding: 12px; }
.shot-card-no-thumb .sc-mood  { padding: 0; }
.shot-card-no-thumb .sc-title { padding: 0; }
.shot-card-no-thumb .sc-desc  { padding: 0; }
.shot-card-no-thumb .sc-footer { padding: 6px 0 0; }
.sc-thumb-wrap {
  width: 100%; overflow: hidden; flex-shrink: 0;
  background: var(--surface-inset); position: relative;
}
.sc-thumb {
  width: 100%; height: 120px; object-fit: cover; display: block;
}
.sc-mood  { font-size: 10px; color: var(--accent); padding: 10px 12px 0; }
.sc-title { font-size: 13px; font-weight: 600; color: var(--text-hi); line-height: 1.3; padding: 4px 12px 0; }
.sc-desc  { font-size: 11px; color: var(--text-dim); line-height: 1.4; margin-top: 2px; flex: 1; padding: 0 12px; }
.sc-footer {
  display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding: 6px 12px 10px;
}
.sc-spacer { flex: 1; }
.sc-error-dot {
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--error); color: white;
  font-size: 10px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.sc-refined-overlay {
  position: absolute; bottom: 0; left: 0; right: 0;
  background: rgba(0,0,0,0.45);
  color: white; font-size: 10px; font-weight: 600;
  text-align: center; padding: 4px 0;
  letter-spacing: 0.04em;
}
.sc-del {
  background: none; border: none; color: var(--text-ghost); font-size: 10px;
  cursor: pointer; padding: 2px 4px; border-radius: 3px; line-height: 1;
  transition: color 0.15s, background 0.15s;
}
.sc-del:hover { color: var(--error); background: var(--surface-inset); }

/* ── List view ── */
.shots-list { display: flex; flex-direction: column; gap: 6px; }
.sl-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: 10px;
  border: 1px solid var(--border); background: var(--surface);
  cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s;
}
.sl-row:hover { border-color: var(--accent-dim); box-shadow: 0 1px 8px var(--shadow); }
.sl-refined { border-color: var(--badge-done-text); }
.sl-thumb-wrap {
  width: 44px; height: 44px; flex-shrink: 0;
  border-radius: 6px; overflow: hidden; background: var(--surface-inset);
  display: flex; align-items: center; justify-content: center;
}
.sl-thumb { width: 100%; height: 100%; object-fit: cover; display: block; }
.sl-thumb-empty { font-size: 10px; color: var(--text-ghost); }
.sl-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.sl-title { font-size: 12px; font-weight: 600; color: var(--text-hi); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sl-mood  { font-size: 10px; color: var(--accent); }
.sl-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.sl-badge-refined {
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
  background: var(--badge-done-bg); color: var(--badge-done-text); font-weight: 600;
}
.sl-badge-error {
  font-size: 10px; padding: 2px 6px; border-radius: 4px;
  background: var(--surface-inset); color: var(--error);
}
.sl-add {
  margin-top: 4px; padding: 8px; width: 100%;
  border: 1.5px dashed var(--border); border-radius: 10px;
  background: none; color: var(--text-ghost); font-size: 12px;
  cursor: pointer; transition: border-color 0.15s, color 0.15s;
}
.sl-add:hover { border-color: var(--accent-dim); color: var(--accent); }

.shot-add {
  min-height: 130px; background: var(--surface-inset);
  border: 1.5px dashed var(--border); border-radius: 12px;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px;
  cursor: pointer; transition: border-color 0.2s;
}
.shot-add:hover { border-color: var(--accent-dim); }
.add-icon { font-size: 20px; color: var(--text-ghost); }
.add-text { font-size: 11px; color: var(--text-ghost); }

/* ── Shot modal ── */
.shot-modal-overlay {
  position: fixed; inset: 0; z-index: 10001;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center;
}
.shot-modal {
  background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 14px; padding: 24px 28px; width: 320px;
  display: flex; flex-direction: column; gap: 12px;
}
.sm-title { font-size: 14px; font-weight: 600; color: var(--text-hi); }
.sm-input {
  width: 100%; box-sizing: border-box;
  background: var(--surface-inset); border: 1px solid var(--border-md);
  border-radius: 8px; color: var(--text-hi); font-size: 12px;
  padding: 8px 10px; font-family: inherit;
  transition: border-color 0.15s;
}
.sm-input:focus { outline: none; border-color: var(--accent-dim); }
.sm-input::placeholder { color: var(--text-ghost); }
.sm-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }
.sm-btn {
  padding: 6px 16px; border-radius: 7px; font-size: 12px;
  cursor: pointer; border: 1px solid var(--border-md);
  transition: background 0.15s, color 0.15s;
}
.sm-cancel { background: var(--surface-inset); color: var(--text-muted); }
.sm-cancel:hover { background: var(--border); }
.sm-ok {
  background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600;
}
.sm-ok:hover:not(:disabled) { background: var(--accent-hover); }
.sm-ok:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Summary ── */
.summary-row { display: flex; gap: 10px; margin-bottom: 14px; }
.sr-icon     { font-size: 13px; flex-shrink: 0; margin-top: 1px; }
.sr-body     { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.sr-label    { font-size: 10px; color: var(--text-quiet); }
.sr-text     { font-size: 11px; color: var(--text-muted); line-height: 1.5; }
.tags        { display: flex; flex-wrap: wrap; gap: 4px; }
.tag {
  padding: 2px 7px; background: var(--surface-2); border: 1px solid var(--border-md);
  border-radius: 4px; font-size: 11px; color: var(--text-muted);
}

/* ── 设定面板 ── */
.setting-block  { margin-bottom: 22px; }
.s-section      { font-size: 10px; color: var(--text-quiet); margin-bottom: 8px; letter-spacing: 0.04em; }
.s-row         { display: flex; gap: 10px; margin-bottom: 5px; align-items: baseline; }
.s-row-top     { align-items: flex-start; }
.s-key         { font-size: 10px; color: var(--text-quiet); flex-shrink: 0; width: 44px; padding-top: 1px; }
.s-val         { font-size: 12px; color: var(--text-muted); line-height: 1.5; }

.ref-add-card {
  width: 100%; aspect-ratio: 2/3;
  border: 1.5px dashed var(--border);
  border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: border-color 0.15s;
}
.ref-add-card:hover { border-color: var(--accent); }
.ref-add-card:hover .ref-add-plus { color: var(--accent); }
.ref-add-plus { font-size: 18px; color: var(--text-ghost); line-height: 1; }

.refs-mini-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: 6px;
}
.ref-mini-img {
  width: 100%; aspect-ratio: 2/3; object-fit: cover;
  border-radius: 6px; border: 1px solid var(--border); display: block;
  cursor: pointer; transition: border-color 0.15s, opacity 0.15s;
}
.ref-mini-img:hover { border-color: var(--accent); opacity: 0.9; }
.ref-extra { border-style: dashed; opacity: 0.85; }

/* ── Lightbox ── */
.lightbox {
  position: fixed; inset: 0; z-index: 10000;
  background: rgba(0,0,0,0.88);
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.lb-img-wrap { position: relative; max-height: 82vh; }
.lb-img {
  max-width: 90vw; max-height: 82vh;
  object-fit: contain; border-radius: 8px;
  display: block;
}
.lb-close {
  position: absolute; top: 16px; right: 20px;
  background: none; border: none;
  color: rgba(255,255,255,0.7); font-size: 22px;
  cursor: pointer; line-height: 1; padding: 4px;
}
.lb-close:hover { color: #fff; }
.lb-arrow {
  position: absolute; top: 50%; transform: translateY(-50%);
  background: rgba(255,255,255,0.12); border: none;
  color: #fff; font-size: 28px; line-height: 1;
  padding: 8px 14px; border-radius: 6px; cursor: pointer;
  transition: background 0.15s;
}
.lb-arrow:hover { background: rgba(255,255,255,0.22); }
.lb-prev { left: 20px; }
.lb-next { right: 20px; }
.lb-counter {
  margin-top: 12px; font-size: 12px; color: rgba(255,255,255,0.45);
}
.lb-badge {
  position: absolute; bottom: 8px; left: 8px;
  font-size: 10px; padding: 2px 7px; border-radius: 4px;
}
.lb-badge-orig  { background: var(--accent); color: #fff; opacity: 0.85; }
.lb-badge-extra { background: var(--border-strong); color: var(--text-hi); opacity: 0.85; }

/* ── AI 助手 ── */
.ai-wrap {
  height: 100%; display: flex; flex-direction: column;
}
.ai-messages {
  flex: 1; overflow-y: auto; padding: 16px 18px 10px;
  display: flex; flex-direction: column; gap: 10px; min-height: 0;
}
.ai-msg        { display: flex; gap: 8px; align-items: flex-start; }
.ai-msg.user   { flex-direction: row-reverse; }
.ai-avatar {
  width: 24px; height: 24px; border-radius: 6px; background: var(--avatar-bg);
  color: var(--avatar-text); font-size: 9px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.ai-bubble {
  max-width: 82%; padding: 7px 10px; border-radius: 8px;
  font-size: 12px; line-height: 1.5; background: var(--surface);
  color: var(--text-muted); border: 1px solid var(--border);
}
.ai-msg.user .ai-bubble {
  background: var(--bubble-user-bg);
  border-color: var(--bubble-user-bdr);
  color: var(--bubble-user-text);
}
.typing { display: flex; gap: 4px; align-items: center; padding: 10px 12px; }
.typing span {
  width: 5px; height: 5px; border-radius: 50%; background: var(--text-sub);
  animation: dot 1.2s ease-in-out infinite;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-5px)} }

.ai-input-row {
  display: flex; gap: 6px; padding: 10px 18px 14px;
  border-top: 1px solid var(--border); flex-shrink: 0;
}
.ai-input {
  flex: 1; background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 8px; color: var(--text-hi); font-size: 12px;
  padding: 7px 10px; font-family: inherit;
  transition: border-color 0.15s;
}
.ai-input:focus        { outline: none; border-color: var(--accent-dim); }
.ai-input::placeholder { color: var(--text-ghost); }
.ai-send {
  width: 32px; height: 32px; background: var(--accent-dim); border: none;
  border-radius: 8px; color: white; font-size: 14px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.15s;
}
.ai-send:hover { background: var(--accent); }
</style>
