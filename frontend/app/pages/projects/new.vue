<template>
  <div class="new-project-page">

    <!-- Top bar -->
    <div class="top-bar">
      <button class="back-btn" @click="step === 1 ? navigateTo('/') : (step = 1)">← 返回</button>
      <span class="top-bar-title">新建项目</span>
      <div class="step-indicator">
        <div class="step-dot" :class="{ active: step >= 1, done: step > 1 }">
          <span>{{ step > 1 ? '✓' : '1' }}</span>
        </div>
        <div class="step-line" :class="{ active: step > 1 }" />
        <div class="step-dot" :class="{ active: step >= 2 }">
          <span>2</span>
        </div>
      </div>
    </div>

    <!-- ══ STEP 1 ══ -->
    <template v-if="step === 1">
      <div class="step1-body">

        <div class="step-header">
          <h2 class="step-title">上传角色参考图</h2>
          <p class="step-desc">上传这个角色的截图或同人图，AI 会提取外貌特征用于生成例图</p>
        </div>

        <!-- Two-column: left = image, right = figure (empty until analysis) -->
        <div class="step1-cols">

          <!-- Single hidden file input (shared) -->
          <input ref="fileInput" type="file" accept="image/*" multiple style="display:none" @change="onFileChange" />

          <!-- Left: image cards -->
          <div class="img-col">
            <!-- Empty state hint -->
            <div v-if="images.length === 0" class="empty-upload-hint">
              <div
                class="add-card big"
                :class="{ 'drag-over': dragging }"
                @dragover.prevent="dragging = true"
                @dragleave.prevent="dragging = false"
                @drop.prevent="onDrop($event)"
                @click="triggerFileInput()"
              >
                <span class="add-icon-big">↑</span>
                <span class="add-label-big">点击上传 或 拖拽图片到此</span>
                <span class="add-sub">支持 JPG、PNG、WEBP</span>
              </div>
            </div>

            <!-- Image stack (after upload) — book-pile style -->
            <div v-else class="img-stack">
              <div class="stack-scene" :class="{ spinning: loading || verifying }">
                <div
                  v-for="(img, i) in images"
                  :key="img.url"
                  class="stack-card"
                  :style="cardStyle(i)"
                >
                  <img :src="img.url" class="card-img" :alt="'参考图' + (i + 1)" />
                </div>
                <div v-if="visualSpec && !loading && !verifying" class="card-done" :style="cardStyle(images.length - 1)" />
                <div v-if="verifying" class="stack-scan stack-scan--verify" :style="cardStyle(images.length - 1)">
                  <div class="scan-inner"><div class="scan-line scan-line--verify" /></div>
                  <span class="scan-label scan-label--verify">检查中</span>
                </div>
                <div v-else-if="loading" class="stack-scan" :style="cardStyle(images.length - 1)">
                  <div class="scan-inner"><div class="scan-line" /></div>
                  <span class="scan-label">分析中</span>
                </div>
              </div>
              <!-- Add more overlay button (bottom of top card, only when not done/busy) -->
              <button
                v-if="!analysisComplete && !loading && !verifying"
                class="stack-add-btn"
                @click="triggerFileInput()"
              >+ 补充图片</button>
            </div>

            <!-- Scanning hint -->
            <p v-if="verifying" class="scanning-hint scanning-hint--verify">AI 正在验证角色一致性…</p>
            <p v-else-if="loading" class="scanning-hint">AI 正在分析角色外貌特征…</p>
          </div>

          <!-- Right: character figure — appears only after first analysis result -->
          <div v-if="Object.keys(extracted).length > 0" class="fig-col">
            <CharacterFigure :extracted="extracted" :gender="gender" :loading="loading" />
          </div>

        </div>

        <!-- AI summary + optional verify error -->
        <div v-if="agentMessage || verifyError" class="agent-bubble">
          <p v-if="verifyError" class="verify-error-inline"><span>⚠</span> {{ verifyError }}</p>
          <p v-if="agentMessage && !verifyError">{{ agentMessage }}</p>
        </div>

        <!-- Bottom center button -->
        <div class="step1-footer">
          <button
            class="finish-btn"
            :disabled="!analysisComplete"
            @click="step = 2"
          >
            下一步 →
          </button>
        </div>

      </div>
    </template>

    <!-- ══ STEP 2 ══ -->
    <template v-if="step === 2">
      <div class="step2-body">

        <div class="step-header">
          <h2 class="step-title">人物档案</h2>
          <p class="step-desc">与 Agent 对话确认角色，右侧档案可直接编辑</p>
        </div>

        <div class="step2-cols">

          <!-- Left: Chat -->
          <div class="chat-col">
            <div class="chat-messages" ref="chatContainer">
              <div
                v-for="(msg, i) in messages"
                :key="i"
                class="chat-msg"
                :class="msg.role"
              >
                <div v-if="msg.role === 'agent'" class="agent-avatar">AI</div>
                <div class="msg-bubble">{{ msg.text }}</div>
              </div>
              <div v-if="chatLoading" class="chat-msg agent">
                <div class="agent-avatar">AI</div>
                <div class="msg-bubble typing">
                  <span /><span /><span />
                </div>
              </div>
            </div>
            <div class="chat-input-row">
              <input
                ref="chatInputEl"
                v-model="chatInput"
                class="chat-input"
                placeholder="输入角色名和作品名…"
                :disabled="chatLoading"
                @keydown.enter.exact.prevent="sendMessage"
              />
              <button class="chat-send" :disabled="!chatInput.trim() || chatLoading" @click="sendMessage">发送</button>
            </div>
          </div>

          <!-- Right: Editable profile -->
          <div class="profile-col">
            <!-- Empty state -->
            <div v-if="!personality" class="profile-empty">
              <div class="empty-icon">📋</div>
              <p>在左侧告诉 Agent 你要找的角色</p>
              <p class="empty-sub">Agent 会自动填入档案，你也可以直接编辑</p>
            </div>

            <!-- Filled profile -->
            <transition name="slide-up">
              <ProfileViewer
                v-if="personality"
                v-model="personality"
                class="profile-filled"
              />
            </transition>
          </div>

        </div>

        <!-- Bottom center button -->
        <div class="step2-footer">
          <p v-if="projectStatus" class="project-status">{{ projectStatus }}</p>
          <button class="finish-btn" :disabled="!personality || projectCreating" @click="createProject">
            <span v-if="projectCreating" class="btn-spinner" />
            {{ projectCreating ? '规划中…' : '开始规划 →' }}
          </button>
        </div>

      </div>
    </template>

  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { useApi } from '~/composables/useApi'

definePageMeta({ ssr: false })

const api = useApi()

const step      = ref(1)
const images    = ref<{ file: File; url: string }[]>([])
const dragging  = ref(false)
const loading   = ref(false)
const verifying = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const visualSpec  = ref<any>(null)
const personality = ref<any>(null)

// Analysis session state
const sessionId        = ref<string | null>(null)
const agentMessage     = ref('')
const verifyError      = ref('')
const extracted        = ref<Record<string, string | null>>({})
const gender           = ref<'male' | 'female'>('female')
const missingFields    = ref<string[]>([])
const analysisComplete = ref(false)
const imageQueue       = ref<File[]>([])
const analyzing        = ref(false)


// Step 2 chat state
const messages      = ref<{ role: 'agent' | 'user'; text: string }[]>([])
const chatHistory   = ref<{ role: 'user' | 'assistant'; content: string }[]>([])
const chatInput     = ref('')
const chatLoading   = ref(false)
const chatInputEl   = ref<HTMLInputElement | null>(null)
const chatContainer = ref<HTMLElement | null>(null)

// project creation progress
const projectCreating = ref(false)
const projectStatus   = ref('')

watch(step, async (val) => {
  if (val === 2) {
    messages.value    = []
    chatHistory.value = []
    personality.value = null
    await nextTick()
    messages.value.push({ role: 'agent', text: '你想找哪位角色？告诉我角色名和所属作品名称。' })
    chatInputEl.value?.focus()
  }
})

async function sendMessage() {
  const text = chatInput.value.trim()
  if (!text || chatLoading.value) return
  chatInput.value = ''
  messages.value.push({ role: 'user', text })
  chatLoading.value = true
  await scrollBottom()

  try {
    const res = await api.chat(text, chatHistory.value, visualSpec.value?.zh ?? null, personality.value)
    chatHistory.value.push({ role: 'user', content: text })
    chatHistory.value.push({ role: 'assistant', content: res.reply })
    if (res.profile) personality.value = deepMerge(personality.value ?? {}, res.profile)
    messages.value.push({ role: 'agent', text: res.reply })
  } catch {
    messages.value.push({ role: 'agent', text: '网络错误，请重试。' })
  }

  chatLoading.value = false
  await scrollBottom()
}

function deepMerge(base: Record<string, any>, update: Record<string, any>): Record<string, any> {
  const result: Record<string, any> = { ...base }
  for (const key of Object.keys(update)) {
    const bv = base[key], uv = update[key]
    if (bv && uv && typeof bv === 'object' && !Array.isArray(bv) && typeof uv === 'object' && !Array.isArray(uv)) {
      result[key] = deepMerge(bv, uv)
    } else {
      result[key] = uv
    }
  }
  return result
}

async function scrollBottom() {
  await nextTick()
  if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
}


function triggerFileInput() { fileInput.value?.click() }

function cardStyle(i: number) {
  const depth = images.value.length - 1 - i  // 0 = top card
  const dx = Math.min(depth, 3) * 20
  const dy = Math.min(depth, 3) * 10
  return {
    left: `${dx}px`,
    top:  `${dy}px`,
    zIndex: i + 1,
    ...(depth > 0 ? { filter: `brightness(${Math.max(0.55, 1 - depth * 0.15)})` } : {}),
  }
}

function onFileChange(e: Event) {
  Array.from((e.target as HTMLInputElement).files ?? []).forEach(addImage)
  ;(e.target as HTMLInputElement).value = ''
}

function onDrop(e: DragEvent) {
  dragging.value = false
  Array.from(e.dataTransfer?.files ?? []).filter(f => f.type.startsWith('image/')).forEach(addImage)
}

async function addImage(file: File) {
  verifyError.value = ''

  // Show image immediately so user knows it was received
  const url = URL.createObjectURL(file)
  images.value.push({ file, url })

  // Verify first — only then queue for extraction
  if (sessionId.value && Object.values(extracted.value).some(v => v !== null)) {
    verifying.value = true
    try {
      const check = await api.verifyCharacter(file, sessionId.value)
      if (!check.same) {
        const idx = images.value.findIndex(img => img.url === url)
        if (idx !== -1) { URL.revokeObjectURL(url); images.value.splice(idx, 1) }
        verifyError.value = `图片中的角色与已上传的角色不一致，请使用同一角色的图片。（${check.reason}）`
        verifying.value = false
        return
      }
    } catch {
      // verify failed → allow anyway
    }
    verifying.value = false
  }

  if (!analysisComplete.value) {
    imageQueue.value.push(file)
    processQueue()
  }
}

function removeImage(i: number) {
  URL.revokeObjectURL(images.value[i].url)
  images.value.splice(i, 1)
  sessionId.value     = null
  agentMessage.value  = ''
  extracted.value     = {}
  missingFields.value = []
  analysisComplete.value = false
  visualSpec.value    = null
  imageQueue.value    = []
  if (images.value.length > 0) {
    images.value.forEach(img => imageQueue.value.push(img.file))
    processQueue()
  }
}

async function processQueue() {
  if (analyzing.value) return
  while (imageQueue.value.length > 0) {
    const file = imageQueue.value.shift()!
    analyzing.value = true
    loading.value   = true
    try {
      const result = await api.analyzeImage(file, sessionId.value)
      sessionId.value        = result.session_id
      agentMessage.value     = result.message
      extracted.value        = result.extracted
      // Override with hard visual signals to guard against LLM misidentification
      const lb = (result.extracted.lower_body ?? '').toLowerCase()
      gender.value = lb.includes('skirt') || lb.includes('dress')
        ? 'female'
        : result.gender
      missingFields.value    = result.missing_fields
      analysisComplete.value = result.done
      if (result.done) visualSpec.value = result.visual_spec
    } catch (e) {
      agentMessage.value = `分析出错：${(e as Error).message}`
    } finally {
      analyzing.value = false
    }
  }
  loading.value = false
}

async function createProject() {
  if (projectCreating.value || !personality.value) return
  projectCreating.value = true
  projectStatus.value   = '保存项目…'
  try {
    const p = personality.value
    const world     = { series: p.series, worldSetting: p.worldSetting }
    const character = { character: p.character, series: p.series, characterBackground: p.characterBackground }

    const proj = await api.createProject({
      images:     images.value,
      extracted:  extracted.value,
      visualSpec: visualSpec.value ?? { zh: '', en: '', ja: '' },
      world,
      character,
    })

    navigateTo(`/projects/${proj.project_id}`)
  } catch (e) {
    console.error(e)
    projectStatus.value   = `出错了：${(e as Error).message}`
    projectCreating.value = false
  }
}

onUnmounted(() => {})
</script>

<style scoped>
.new-project-page {
  height: 100vh;
  overflow: hidden;
  background: var(--bg);
  display: flex;
  flex-direction: column;
}

/* ── Top bar ── */
.top-bar {
  height: 48px; background: var(--surface);
  border-bottom: 1px solid var(--border-md);
  display: flex; align-items: center; padding: 0 20px; gap: 12px; flex-shrink: 0;
}
.back-btn { background: none; border: none; color: var(--text-muted); font-size: 13px; cursor: pointer; }
.back-btn:hover { color: var(--text); }
.top-bar-title { font-size: 13px; font-weight: 600; color: var(--text); flex: 1; }
.step-indicator { display: flex; align-items: center; }
.step-dot {
  width: 24px; height: 24px; border-radius: 50%;
  border: 1.5px solid var(--border-focus);
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600; color: var(--text-sub); transition: all 0.2s;
}
.step-dot.active { border-color: var(--accent); color: var(--accent); }
.step-dot.done   { background: var(--accent); border-color: var(--accent); color: white; }
.step-line { width: 24px; height: 1.5px; background: var(--border-focus); transition: background 0.2s; }
.step-line.active { background: var(--accent); }

/* ══ STEP 1 ══ */
.step1-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  max-width: 960px;
  width: 100%;
  margin: 0 auto;
  padding: 36px 32px 0;
  gap: 24px;
  overflow-y: auto;
  min-height: 0;
}

.step-header { flex-shrink: 0; }
.step-title  { font-size: 22px; font-weight: 700; color: var(--text); margin-bottom: 6px; }
.step-desc   { font-size: 13px; color: var(--text-dim); margin-bottom: 10px; }

/* Empty upload state */
.empty-upload-hint { flex: 1; display: flex; align-items: flex-start; }
.add-card.big {
  aspect-ratio: 3/4;
  width: 260px;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 8px;
  background: var(--surface); border: 2px dashed var(--border-md);
  border-radius: 12px; cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.add-card.big:hover,
.add-card.big.drag-over { border-color: var(--accent); background: var(--bg); }
.add-icon-big  { font-size: 32px; color: var(--border-focus); }
.add-label-big { font-size: 14px; color: var(--text-sub); font-weight: 500; }
.add-sub       { font-size: 11px; color: var(--text-ghost); }

/* Hints */
.scanning-hint { font-size: 11px; color: var(--accent); margin-top: 8px; text-align: center; animation: pulse 1.5s ease-in-out infinite; }
.wait-hint     { font-size: 11px; color: var(--text-sub); margin: 0; }
@keyframes pulse { 0%,100%{opacity:0.5} 50%{opacity:1} }

/* Two-column — always, right side is empty until analysis returns */
.step1-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 48px;
}

/* Left: image col */
.img-col { display: flex; flex-direction: column; gap: 12px; }

/* Book-pile image stack */
.img-stack {
  position: relative;
  padding-right: 62px;
  padding-bottom: 32px;
}

.stack-scene {
  position: relative;
  width: 260px;
  height: 347px;
  perspective: 700px;
}

.stack-scene.spinning {
  animation: flip-3d 1.8s linear infinite;
  transform-style: preserve-3d;
}

@keyframes flip-3d {
  from { transform: rotateY(0deg); }
  to   { transform: rotateY(360deg); }
}

.stack-card {
  position: absolute;
  width: 260px;
  height: 347px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border-md);
}

.card-img { width: 100%; height: 100%; object-fit: cover; display: block; }

.card-done {
  position: absolute;
  width: 260px; height: 347px;
  border-radius: 10px;
  background: rgba(76, 175, 130, 0.25);
  animation: fadein 0.3s ease;
  pointer-events: none;
}
@keyframes fadein { from { opacity: 0 } to { opacity: 1 } }

.stack-scan {
  position: absolute;
  width: 260px; height: 347px;
  border-radius: 10px;
  overflow: hidden;
  background: rgba(16, 16, 42, 0.75);
  display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 12px;
  pointer-events: none;
}
.scan-inner {
  position: absolute; inset: 0;
  overflow: hidden;
}
.scan-line {
  position: absolute; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  animation: scan 1.2s ease-in-out infinite;
}
@keyframes scan {
  0%   { top: -2%; opacity: 0; }
  10%  { opacity: 1; }
  90%  { opacity: 1; }
  100% { top: 102%; opacity: 0; }
}
.scan-label { font-size: 11px; color: var(--accent); letter-spacing: 1px; position: relative; }
.scan-line--verify { background: linear-gradient(90deg, transparent, var(--orange), transparent); }
.scan-label--verify { color: var(--orange); }
.scanning-hint--verify { color: var(--orange); }

/* Add more — overlaid at bottom of image stack */
.stack-add-btn {
  position: absolute;
  bottom: 20px;
  left: 0;
  width: 260px;
  padding: 8px 0;
  background: rgba(12, 12, 28, 0.72);
  backdrop-filter: blur(4px);
  border: none;
  border-top: 1px solid rgba(124, 106, 247, 0.25);
  border-radius: 0 0 10px 10px;
  color: var(--accent-dim);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
  z-index: 10;
}
.stack-add-btn:hover { background: rgba(124,106,247,0.2); color: var(--text-accent); }

/* Right: figure + message */
.fig-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.agent-bubble {
  background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 10px; padding: 12px 14px;
  display: flex; flex-direction: column; gap: 6px;
}
.agent-bubble p { font-size: 12px; color: var(--text-muted); line-height: 1.7; margin: 0; }
.verify-error-inline { color: var(--error) !important; }
.verify-error-inline span { margin-right: 4px; }

/* Bottom footer */
.step1-footer {
  display: flex;
  justify-content: center;
  padding: 32px 0 48px;
  flex-shrink: 0;
}
.finish-btn {
  padding: 13px 48px;
  background: var(--accent); border: none; border-radius: 8px;
  color: white; font-size: 15px; font-weight: 600;
  cursor: pointer; transition: background 0.2s, transform 0.1s;
}
.finish-btn:hover:not(:disabled) { background: var(--accent-hover); }
.finish-btn:active:not(:disabled) { transform: scale(0.98); }
.finish-btn:disabled { background: var(--border-md); color: var(--text-quiet); cursor: not-allowed; }

/* ══ STEP 2 ══ */
.page-body {
  max-width: 680px; margin: 0 auto;
  padding: 40px 24px 80px; width: 100%;
  display: flex; flex-direction: column; gap: 20px;
}

/* ══ STEP 2 ══ */
.step2-body {
  flex: 1; display: flex; flex-direction: column;
  max-width: 960px; width: 100%; margin: 0 auto;
  padding: 36px 32px 0; gap: 24px;
  min-height: 0; overflow: hidden;
}

.step2-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── Chat column ── */
.chat-col {
  display: flex; flex-direction: column;
  background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 12px; overflow: hidden;
}

.chat-messages {
  flex: 1; overflow-y: auto; padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
  min-height: 0;
  scrollbar-width: none;
}
.chat-messages::-webkit-scrollbar { display: none; }

.chat-msg {
  display: flex; gap: 8px; align-items: flex-start;
}
.chat-msg.user { flex-direction: row-reverse; }

.agent-avatar {
  width: 26px; height: 26px; border-radius: 50%;
  background: var(--surface-raised); border: 1px solid var(--border-focus);
  display: flex; align-items: center; justify-content: center;
  font-size: 9px; font-weight: 700; color: var(--accent); flex-shrink: 0;
}

.msg-bubble {
  max-width: 80%; padding: 10px 13px; border-radius: 10px;
  font-size: 13px; line-height: 1.6;
  background: var(--surface-2); color: var(--text-hi); border: 1px solid var(--border-md);
}
.chat-msg.user .msg-bubble {
  background: var(--bubble-user-bg); border-color: var(--bubble-user-bdr); color: var(--text);
}

/* Typing indicator */
.msg-bubble.typing {
  display: flex; align-items: center; gap: 4px; padding: 12px 14px;
}
.msg-bubble.typing span {
  width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
  animation: blink 1.2s ease-in-out infinite;
}
.msg-bubble.typing span:nth-child(2) { animation-delay: 0.2s; }
.msg-bubble.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink { 0%,80%,100% { opacity: 0.2; } 40% { opacity: 1; } }

.chat-input-row {
  display: flex; gap: 8px; padding: 12px;
  border-top: 1px solid var(--border);
}
.chat-input {
  flex: 1; background: var(--bg); border: 1px solid var(--border-md);
  border-radius: 8px; padding: 9px 12px;
  color: var(--text); font-size: 13px; outline: none; transition: border-color 0.2s;
}
.chat-input:focus { border-color: var(--accent); }
.chat-input::placeholder { color: var(--text-ghost); }
.chat-send {
  padding: 9px 16px; background: var(--accent); border: none;
  border-radius: 8px; color: white; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: background 0.2s; white-space: nowrap;
}
.chat-send:hover:not(:disabled) { background: var(--accent-hover); }
.chat-send:disabled { background: var(--border-md); color: var(--text-quiet); cursor: not-allowed; }

/* ── Profile column ── */
.profile-col {
  background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 12px; overflow-y: auto; padding: 20px;
}

.profile-empty {
  height: 100%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 10px; color: var(--text-quiet);
}
.empty-icon { font-size: 32px; }
.profile-empty p { font-size: 13px; color: var(--text-sub); text-align: center; margin: 0; }
.empty-sub { font-size: 11px !important; color: var(--border-focus) !important; }

.profile-filled { display: flex; flex-direction: column; gap: 18px; }

/* Editable identity */
.profile-identity { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.edit-name {
  background: none; border: none; border-bottom: 1px solid transparent;
  font-size: 22px; font-weight: 700; color: var(--text); outline: none;
  transition: border-color 0.2s; padding: 2px 0; flex: 1; min-width: 120px;
}
.edit-name:hover, .edit-name:focus { border-bottom-color: var(--border-focus); }
.edit-series {
  background: var(--surface-raised); border: 1px solid var(--border-focus); border-radius: 20px;
  padding: 3px 12px; font-size: 11px; color: var(--accent); font-weight: 600;
  outline: none; text-align: center; width: auto;
}

/* Editable fields */
.meta-row { display: flex; flex-wrap: wrap; gap: 6px; }
.edit-chip {
  padding: 3px 10px; background: var(--surface-2); border: 1px solid var(--border-md);
  border-radius: 4px; font-size: 11px; color: var(--text-muted); outline: none;
  transition: border-color 0.2s; min-width: 60px;
}
.edit-chip:hover, .edit-chip:focus { border-color: var(--accent); color: var(--text-hi); }
.edit-chip.accent { border-color: var(--border-focus); color: var(--text-neutral); }

.edit-trait {
  background: none; border: none; border-bottom: 1px solid var(--border);
  font-size: 13px; font-weight: 600; color: var(--accent); font-style: italic;
  outline: none; width: 100%; padding: 4px 0; transition: border-color 0.2s;
}
.edit-trait:hover, .edit-trait:focus { border-bottom-color: var(--accent); }

.edit-area {
  width: 100%; background: var(--bg); border: 1px solid transparent;
  border-radius: 6px; padding: 10px; color: var(--text-muted); font-size: 13px;
  line-height: 1.7; resize: vertical; outline: none; font-family: inherit;
  transition: border-color 0.2s;
}
.edit-area:hover, .edit-area:focus { border-color: var(--border-md); color: var(--text-hi); }

/* Step 2 footer */
.step2-footer {
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 16px 0 24px; flex-shrink: 0;
}
.project-status { font-size: 12px; color: var(--accent); margin: 0; }

/* ── Reference bar ── */
.ref-bar {
  display: flex; align-items: flex-start; gap: 14px;
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 12px; padding: 14px;
}
.ref-thumb { width: 52px; height: 70px; border-radius: 7px; overflow: hidden; flex-shrink: 0; background: var(--surface-2); }
.ref-img   { width: 100%; height: 100%; object-fit: cover; display: block; }
.ref-info  { flex: 1; display: flex; flex-direction: column; gap: 7px; min-width: 0; }
.ref-specs { display: flex; flex-wrap: wrap; gap: 5px; }
.ref-chip  {
  padding: 2px 8px; background: var(--surface-raised); border: 1px solid var(--border-focus); border-radius: 4px;
  font-size: 10px; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 180px;
}
.ref-features { display: flex; flex-wrap: wrap; gap: 4px; }
.feat-mini { font-size: 10px; color: var(--text-sub); background: var(--bg); padding: 2px 6px; border-radius: 3px; border: 1px solid var(--border); }
.reextract-btn { background: none; border: none; color: var(--text-quiet); font-size: 11px; cursor: pointer; flex-shrink: 0; white-space: nowrap; align-self: flex-start; }
.reextract-btn:hover { color: var(--accent); }

/* ── Name section ── */
.name-section { display: flex; flex-direction: column; gap: 10px; }
.name-label   { font-size: 11px; font-weight: 600; color: var(--text-sub); text-transform: uppercase; letter-spacing: 0.6px; }
.name-input {
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 8px;
  padding: 14px 16px; color: var(--text); font-size: 22px; font-weight: 600; outline: none; transition: border-color 0.2s;
}
.name-input:focus { border-color: var(--accent); }
.name-input::placeholder { color: var(--border-md); font-weight: 400; font-size: 18px; }
.series-input {
  background: var(--surface); border: 1px solid var(--surface-2); border-radius: 8px;
  padding: 9px 14px; color: var(--text-dim); font-size: 13px; outline: none; transition: border-color 0.2s;
}
.series-input:focus { border-color: var(--border-focus); color: var(--text-hi); }
.series-input::placeholder { color: var(--border-md); }

/* ── Primary button ── */
.primary-btn {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  width: 100%; padding: 12px; background: var(--accent); border: none; border-radius: 8px;
  color: white; font-size: 14px; font-weight: 600; cursor: pointer; transition: background 0.2s;
}
.primary-btn:hover:not(:disabled) { background: var(--accent-hover); }
.primary-btn:disabled { background: var(--border-md); color: var(--text-sub); cursor: not-allowed; }
.mt-20 { margin-top: 20px; }

.btn-spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: white;
  border-radius: 50%; animation: spin 0.7s linear infinite; flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Profile result ── */
.profile-result {
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 12px;
  padding: 24px; display: flex; flex-direction: column; gap: 20px;
}

.profile-identity { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.profile-name { font-size: 28px; font-weight: 700; color: var(--text); }
.profile-series-pill {
  padding: 3px 12px; background: var(--surface-raised); border: 1px solid var(--border-focus);
  border-radius: 20px; font-size: 11px; color: var(--accent); font-weight: 600;
}

.profile-section { display: flex; flex-direction: column; gap: 10px; }
.section-label {
  font-size: 10px; font-weight: 700; color: var(--text-sub);
  text-transform: uppercase; letter-spacing: 1px;
}
.section-divider { height: 1px; background: var(--border); }
.section-desc { font-size: 13px; color: var(--text-muted); line-height: 1.8; margin: 0; }

.world-meta, .char-meta { display: flex; flex-wrap: wrap; gap: 6px; }
.meta-chip {
  padding: 3px 10px; background: var(--surface-2); border: 1px solid var(--border-md);
  border-radius: 4px; font-size: 11px; color: var(--text-muted);
}
.meta-chip.accent { border-color: var(--border-focus); color: var(--text-neutral); }

.theme-tags { display: flex; flex-wrap: wrap; gap: 5px; }
.theme-tag {
  padding: 3px 9px; background: var(--bg); border: 1px solid var(--border);
  border-radius: 20px; font-size: 11px; color: var(--text-dim);
}

.core-trait {
  font-size: 13px; font-weight: 600; color: var(--accent);
  font-style: italic; padding: 2px 0;
}

.relations { display: flex; flex-wrap: wrap; gap: 5px; }
.relation-tag {
  padding: 3px 9px; background: var(--surface-raised); border: 1px solid var(--border-focus);
  border-radius: 4px; font-size: 11px; color: var(--text-muted);
}


.slide-up-enter-active { transition: all 0.35s ease; }
.slide-up-enter-from   { opacity: 0; transform: translateY(16px); }
</style>
