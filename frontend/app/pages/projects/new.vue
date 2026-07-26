<template>
  <div class="new-project-page">

    <!-- Top bar -->
    <div class="top-bar">
      <button class="back-btn" @click="navigateTo('/')">
        <span class="back-chevron">‹</span>{{ t('common.back') }}
      </button>
      <span class="top-bar-title">{{ t('newProject.pageTitle') }}</span>
    </div>

    <!-- Upload + extract + confirm-with-AI. Profile review/edit now happens in
         the workspace 设定 panel, so there's no separate review step. -->
    <div class="step1-body">

        <div class="step-header">
          <h2 class="step-title">{{ t('newProject.step1Title') }}</h2>
          <p class="step-desc">{{ t('newProject.step1Desc') }}</p>
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
                <span class="add-label-big">{{ t('newProject.uploadCtaLine1') }}<br>{{ t('newProject.uploadCtaLine2') }}</span>
                <span class="add-sub">{{ t('newProject.uploadFormats') }}</span>
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
                  <img :src="img.url" class="card-img" :alt="t('newProject.refImageAlt') + (i + 1)" />
                  <button
                    v-if="!loading && !verifying"
                    class="stack-del-btn"
                    :title="t('newProject.deleteImageTitle')"
                    @click.stop="removeImage(i)"
                  >×</button>
                </div>
                <div v-if="visualSpec && !loading && !verifying" class="card-done" :style="cardStyle(images.length - 1)" />
                <div v-if="verifying" class="stack-scan stack-scan--verify" :style="cardStyle(images.length - 1)">
                  <div class="scan-inner"><div class="scan-line scan-line--verify" /></div>
                  <span class="scan-label scan-label--verify">{{ t('newProject.verifyingScan') }}</span>
                </div>
                <div v-else-if="loading" class="stack-scan" :style="cardStyle(images.length - 1)">
                  <div class="scan-inner"><div class="scan-line" /></div>
                  <span class="scan-label">{{ t('newProject.analyzingScan') }}</span>
                </div>
              </div>
              <!-- Add more overlay button (bottom of top card, only when not done/busy) -->
              <button
                v-if="!analysisComplete && !loading && !verifying"
                class="stack-add-btn"
                @click="triggerFileInput()"
              >{{ addMoreLabel }}</button>
            </div>

            <!-- Verification / analysis errors — urgent, standalone -->
            <p v-if="verifyError" class="verify-error-inline"><span>⚠</span> {{ verifyError }}</p>
            <p v-if="agentMessage && !verifyError" class="verify-error-inline"><span>⚠</span> {{ agentMessage }}</p>

            <!-- Upload tips — anchored to the bottom-right of this column, stays
                 visible even after the figure result appears on the right -->
            <div class="upload-tips">
              <p class="upload-tips-title">{{ t('newProject.tipsTitle') }}</p>
              <ul>
                <li>{{ t('newProject.tip1') }}</li>
                <li>{{ t('newProject.tip2') }}</li>
                <li>{{ t('newProject.tip3') }}</li>
              </ul>
            </div>
          </div>

          <!-- Right: character figure — appears only after first analysis result -->
          <div v-if="Object.keys(extracted).length > 0" class="fig-col">
            <CharacterFigure :extracted="extracted" :extracted-i18n="extractedI18n" :gender="gender" :loading="loading" />
          </div>

        </div>

      </div>

      <!-- Floating assistant — always present, same as the theme/locale widgets.
           Just a speech bubble by default, no chat-box chrome — the only real
           input this flow ever needs is confirming (or correcting) the AI's
           character guess, so that's the only moment a small input appears.
           Placeholder circular avatar for now; swap for the illustrated mascot
           once that asset exists. -->
      <div class="assistant-widget" :style="assistantDrag.style">
        <div v-if="widgetExpanded" class="assistant-log-panel">
          <div class="assistant-log" ref="chatContainer">
            <div
              v-for="(msg, i) in messages"
              :key="i"
              class="chat-msg"
              :class="msg.role"
            >
              <div v-if="msg.role === 'agent'" class="agent-avatar-sm">AI</div>
              <div class="msg-bubble">
                {{ msg.text }}
                <button
                  v-if="msg.retryText"
                  class="retry-btn"
                  :disabled="chatLoading"
                  @click="msg.isKickoffRetry ? kickoffChat() : sendMessage(msg.retryText)"
                >{{ t('newProject.retry') }}</button>
              </div>
            </div>
            <div v-if="chatLoading" class="chat-msg agent">
              <div class="agent-avatar-sm">AI</div>
              <div class="msg-bubble busy">
                {{ chatStatusText }}<span class="inline-dots"><span /><span /><span /></span>
              </div>
            </div>
          </div>
        </div>

        <template v-else>
          <div v-if="verifying" class="assistant-bubble busy">
            {{ t('newProject.verifyingHint') }}<span class="inline-dots"><span /><span /><span /></span>
          </div>
          <div v-else-if="loading" class="assistant-bubble busy">
            {{ t('newProject.analyzingHint') }}<span class="inline-dots"><span /><span /><span /></span>
          </div>
          <div v-else-if="!analysisComplete && Object.keys(extracted).length > 0" class="assistant-bubble">
            <p class="feedback-title">{{ t('newProject.profileIncomplete') }}</p>
            <p v-if="doneLabelsText" class="feedback-line">{{ t('newProject.gathered', { list: doneLabelsText }) }}</p>
            <p class="feedback-line feedback-missing">{{ t('newProject.missing', { list: missingLabelsText }) }}</p>
            <p class="feedback-line feedback-suggestion">{{ suggestionText }}</p>
          </div>
          <div v-else-if="!analysisComplete" class="assistant-bubble">{{ t('newProject.assistantIdle') }}</div>
          <div v-else-if="chatLoading" class="assistant-bubble busy">
            {{ chatStatusText }}<span class="inline-dots"><span /><span /><span /></span>
          </div>
          <div v-else-if="latestAgentMessage" class="assistant-bubble">
            {{ latestAgentMessage.text }}
            <button
              v-if="latestAgentMessage.retryText"
              class="retry-btn"
              :disabled="chatLoading"
              @click="latestAgentMessage.isKickoffRetry ? kickoffChat() : sendMessage(latestAgentMessage.retryText)"
            >{{ t('newProject.retry') }}</button>
          </div>
        </template>

        <!-- Quick-reply row — only while the agent is waiting on the one
             thing this flow ever needs from the user: confirm or correct
             the character guess. Disappears once the profile is built. -->
        <div v-if="needsUserReply" class="assistant-quick-row">
          <button
            v-if="awaitingConfirm"
            class="quick-confirm-btn"
            :disabled="chatLoading"
            @click="sendMessage(t('newProject.confirmYes'))"
          >{{ t('newProject.confirmYes') }}</button>
          <div class="quick-input-wrap">
            <input
              ref="chatInputEl"
              v-model="chatInput"
              class="quick-input"
              :placeholder="t('newProject.quickInputPlaceholder')"
              :disabled="chatLoading"
              @keydown.enter.exact="onChatInputEnter"
            />
            <button class="quick-send" :disabled="!chatInput.trim() || chatLoading" @click="sendMessage()">›</button>
          </div>
        </div>

        <!-- Profile's built — go straight into the workspace (review/edit lives
             there now). Sits right under the message that announced it. -->
        <div v-if="showNextStepCta" class="assistant-quick-row">
          <button class="quick-confirm-btn" :disabled="projectCreating" @click="createProject">
            <span v-if="projectCreating" class="btn-spinner" />
            {{ projectCreating ? t('newProject.planning') : t('newProject.startPlanning') }}
          </button>
        </div>
        <p v-if="projectStatus" class="assistant-quick-row project-status">{{ projectStatus }}</p>

        <button
          class="assistant-avatar"
          @pointerdown="assistantDrag.onPointerDown"
          @click="assistantDrag.consumeClick() || (widgetExpanded = !widgetExpanded)"
        >
          <span>AI</span>
        </button>
      </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { useApi } from '~/composables/useApi'

definePageMeta({ ssr: false })

const api = useApi()
const { t } = useLocale()
const { fieldLabel } = useFieldLabels()

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
const extractedI18n    = ref<{ zh: Record<string, string | null>; en: Record<string, string | null>; ja: Record<string, string | null> } | null>(null)
const gender           = ref<'male' | 'female'>('female')
const missingFields    = ref<string[]>([])
const analysisComplete = ref(false)
const imageQueue       = ref<File[]>([])
const analyzing        = ref(false)
// Bumped whenever the reference image is removed/replaced. A processQueue()
// loop captures the generation at start; if it changes mid-flight, the in-flight
// analyze response is stale and must be discarded rather than written back.
// (Currently the template hides add/remove controls while loading, so this can't
// be triggered via the UI — it's a guard so a future "queue more images while
// analyzing" change can't silently reintroduce a stale-write race.)
const analysisGeneration = ref(0)

const FULL_BODY_FIELDS = ['shoes', 'proportions']

const doneLabelsText = computed(() =>
  Object.entries(extracted.value)
    .filter(([, v]) => v != null)
    .map(([f]) => fieldLabel(f))
    .join(t('common.listSeparator'))
)
const missingLabelsText = computed(() => missingFields.value.map(f => fieldLabel(f)).join(t('common.listSeparator')))
const needsFullBodyPhoto = computed(() => missingFields.value.some(f => FULL_BODY_FIELDS.includes(f)))
const suggestionText = computed(() => {
  if (!missingFields.value.length) return ''
  return needsFullBodyPhoto.value
    ? t('newProject.suggestFullBody')
    : t('newProject.suggestGeneric', { list: missingLabelsText.value })
})
const addMoreLabel = computed(() => needsFullBodyPhoto.value ? t('newProject.addMoreFullBody') : t('newProject.addMoreGeneric'))


// Floating assistant (Step 1) chat state
const messages      = ref<{ role: 'agent' | 'user'; text: string; retryText?: string; isKickoffRetry?: boolean }[]>([])
const chatHistory   = ref<{ role: 'user' | 'assistant'; content: string }[]>([])
const chatInput     = ref('')
const chatLoading   = ref(false)
const chatInputEl   = ref<HTMLInputElement | null>(null)
const chatContainer = ref<HTMLElement | null>(null)
const widgetExpanded = ref(false)
const assistantDrag = useDraggableCorner('newproject-ai-pos')   // drag the avatar to reposition
// Whether the agent's latest reply is a plain yes/no identity-confirm
// question (single vision candidate) — only then does a quick "yes" chip
// make sense; open-ended asks (candidates, "tell me the name") get only
// the free-text input. Driven by the backend (agents/character_chat.py),
// not guessed from the reply text.
const awaitingConfirm = ref(false)
// Bubble only ever shows the agent's side of the conversation — the user's
// own sent text lives in the expanded log, not the collapsed bubble.
const latestAgentMessage = computed(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].role === 'agent') return messages.value[i]
  }
  return null
})
// The only user input this flow ever needs is confirming/correcting the
// character guess — show the quick-reply row while that's still open, hide
// it once the agent has actually built the profile. A failed request shows
// only its own retry button instead (no point offering a confirm/edit row
// for a message that never actually asked anything).
const needsUserReply = computed(() => {
  const last = messages.value[messages.value.length - 1]
  return analysisComplete.value && !chatLoading.value && !personality.value &&
    !!last && last.role === 'agent' && !last.retryText
})
// What the agent's busy with right now — the very first request is always
// the vision identification (no reply yet); anything after that is the
// research-and-build pass following confirmation, which genuinely runs
// several web searches and can take a while.
const chatStatusText = computed(() =>
  messages.value.length === 0 ? t('newProject.identifyingHint') : t('newProject.buildingHint')
)
// Once the profile is actually built, the "next step" CTA sits right under
// the message that announced it instead of a separate page-wide footer.
const showNextStepCta = computed(() => analysisComplete.value && !!personality.value && !chatLoading.value)

// project creation progress
const projectCreating = ref(false)
const projectStatus   = ref('')

// Appearance extraction and character-identification chat both live on Step 1
// now — as soon as appearance extraction completes, silently kick off the
// identification chat in the floating assistant widget.
watch(analysisComplete, async (done) => {
  if (!done) return
  messages.value       = []
  chatHistory.value    = []
  personality.value    = null
  awaitingConfirm.value = false
  await nextTick()
  await kickoffChat()
})

// Map a failed request to user-facing copy: a network/timeout failure reads as
// "try again", a real backend/AI failure (4xx/5xx) reads as "contact us" — so
// the user isn't told to check their own connection when the service is down.
function errorMessage(e: unknown): string {
  return (e as { kind?: string } | null)?.kind === 'server'
    ? t('newProject.chatServerError')
    : t('newProject.chatNetworkError')
}

// Silently trigger the agent's turn-1 vision identification (see
// agents/character_chat.py) so the assistant opens with a guess-and-confirm
// message instead of a blind "which character?" prompt. The kickoff line
// itself is never shown — only the agent's reply is.
const KICKOFF_MESSAGE = '（用户刚上传了角色参考图，请开始建档流程。）'

// The turn that actually finishes the profile gets a fixed, friendly line
// instead of whatever the LLM happened to phrase — the model's own "all
// done!" replies read stiff/inconsistent turn to turn, and this is the one
// moment worth keeping predictable.
function profileReadyText(profile: any): string {
  return t('newProject.profileReadyMessage', { name: profile?.character || '' })
}

async function kickoffChat() {
  // A retry replaces the previous failed attempt rather than stacking on top of it.
  if (messages.value[messages.value.length - 1]?.isKickoffRetry) messages.value.pop()
  chatLoading.value = true
  try {
    const res = await withRetry(() => api.chat(KICKOFF_MESSAGE, chatHistory.value, visualSpec.value?.zh ?? null, personality.value, sessionId.value))
    chatHistory.value.push({ role: 'user', content: KICKOFF_MESSAGE })
    chatHistory.value.push({ role: 'assistant', content: res.reply })
    if (res.profile) {
      personality.value = deepMerge(personality.value ?? {}, res.profile)
      awaitingConfirm.value = false
      messages.value.push({ role: 'agent', text: profileReadyText(res.profile) })
    } else {
      awaitingConfirm.value = res.awaiting_confirm
      messages.value.push({ role: 'agent', text: res.reply || t('newProject.chatWelcome') })
    }
  } catch (e) {
    awaitingConfirm.value = false
    messages.value.push({ role: 'agent', text: errorMessage(e), retryText: KICKOFF_MESSAGE, isKickoffRetry: true })
  } finally {
    // Guaranteed to run even if something above throws unexpectedly —
    // the input/send button must never stay stuck disabled.
    chatLoading.value = false
  }
  await scrollBottom()
}

function onChatInputEnter(e: KeyboardEvent) {
  // Ignore Enter presses used to confirm an IME composition (e.g. pinyin/
  // Japanese input candidate selection) — only send on a "real" Enter.
  if (e.isComposing) return
  e.preventDefault()
  sendMessage()
}

async function sendMessage(retryText?: string) {
  const text = retryText ?? chatInput.value.trim()
  if (!text || chatLoading.value) return
  if (retryText === undefined) chatInput.value = ''
  messages.value.push({ role: 'user', text })
  chatLoading.value = true
  await scrollBottom()

  try {
    const res = await withRetry(() => api.chat(text, chatHistory.value, visualSpec.value?.zh ?? null, personality.value, sessionId.value))
    chatHistory.value.push({ role: 'user', content: text })
    chatHistory.value.push({ role: 'assistant', content: res.reply })
    if (res.profile) {
      personality.value = deepMerge(personality.value ?? {}, res.profile)
      awaitingConfirm.value = false
      messages.value.push({ role: 'agent', text: profileReadyText(res.profile) })
    } else {
      awaitingConfirm.value = res.awaiting_confirm
      messages.value.push({ role: 'agent', text: res.reply })
    }
  } catch (e) {
    awaitingConfirm.value = false
    messages.value.push({ role: 'agent', text: errorMessage(e), retryText: text })
  } finally {
    // Guaranteed to run even if something above throws unexpectedly —
    // the input/send button must never stay stuck disabled.
    chatLoading.value = false
  }
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
        verifyError.value = t('newProject.verifyMismatch', { reason: check.reason })
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
  analysisGeneration.value++   // supersede any in-flight analysis for the old image
  sessionId.value     = null
  agentMessage.value  = ''
  extracted.value     = {}
  extractedI18n.value = null
  missingFields.value = []
  analysisComplete.value = false
  visualSpec.value    = null
  imageQueue.value    = []
  // Removing the reference image invalidates any identification/profile
  // chat already in progress for the old session.
  messages.value      = []
  chatHistory.value   = []
  personality.value   = null
  awaitingConfirm.value = false
  widgetExpanded.value = false
  if (images.value.length > 0) {
    images.value.forEach(img => imageQueue.value.push(img.file))
    processQueue()
  }
}

async function processQueue() {
  if (analyzing.value) return
  analyzing.value = true
  loading.value   = true
  const gen = analysisGeneration.value
  try {
    while (imageQueue.value.length > 0 && gen === analysisGeneration.value) {
      const file = imageQueue.value.shift()!
      try {
        const result = await api.analyzeImage(file, sessionId.value)
        // Image removed/replaced while this was in flight → stale session; drop
        // it rather than clobbering the reset state or kicking off a stale chat.
        if (gen !== analysisGeneration.value) break
        agentMessage.value     = ''
        sessionId.value        = result.session_id
        extracted.value        = result.extracted
        extractedI18n.value    = result.extracted_i18n
        // Override with hard visual signals to guard against LLM misidentification
        const lb = (result.extracted.lower_body ?? '').toLowerCase()
        gender.value = lb.includes('skirt') || lb.includes('dress')
          ? 'female'
          : result.gender
        missingFields.value    = result.missing_fields
        analysisComplete.value = result.done
        if (result.done) visualSpec.value = result.visual_spec
      } catch (e) {
        if (gen !== analysisGeneration.value) break
        // Don't leak raw backend text — show the same friendly network/server
        // split the chat uses.
        agentMessage.value = errorMessage(e)
      }
    }
  } finally {
    analyzing.value = false
    loading.value   = false
  }
  // A supersede queued fresh work but our re-entrancy guard blocked its
  // processQueue() call while we were still running — run it now.
  if (gen !== analysisGeneration.value && imageQueue.value.length > 0) processQueue()
}

async function createProject() {
  if (projectCreating.value || !personality.value) return
  projectCreating.value = true
  projectStatus.value   = t('newProject.savingProject')
  try {
    const p = personality.value
    const world     = { series: p.series, worldSetting: p.worldSetting }
    const character = { character: p.character, series: p.series, characterBackground: p.characterBackground }

    const proj = await api.createProject({
      images:        images.value,
      extractedI18n: extractedI18n.value ?? { zh: extracted.value, en: extracted.value, ja: extracted.value },
      visualSpec:    visualSpec.value ?? { zh: '', en: '', ja: '' },
      world,
      character,
    })

    navigateTo(`/projects/${proj.project_id}`)
  } catch (e) {
    console.error(e)
    // Same network/server split as the chat flow — don't leak raw backend text.
    projectStatus.value   = errorMessage(e)
    projectCreating.value = false
  }
}

onUnmounted(() => {
  // Release blob URLs created by createObjectURL so they don't leak when the
  // page unmounts — covers both the create-success navigation and the back button.
  images.value.forEach(img => URL.revokeObjectURL(img.url))
})
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
.back-btn {
  display: flex; align-items: center; gap: 1px;
  background: none; border: none; padding: 4px 6px 4px 2px; border-radius: 6px;
  color: var(--accent); font-size: 15px; font-weight: 500; cursor: pointer;
  transition: opacity 0.15s;
}
.back-btn:hover { opacity: 0.65; }
.back-chevron { font-size: 21px; line-height: 1; margin-top: -1px; }
.top-bar-title { font-size: 13px; font-weight: 600; color: var(--text); flex: 1; }

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
  scrollbar-width: none;
}
.step1-body::-webkit-scrollbar { display: none; }

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
.add-label-big { font-size: 14px; color: var(--text-sub); font-weight: 500; text-align: center; line-height: 1.5; }
.add-sub       { font-size: 11px; color: var(--text-ghost); }


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

/* × delete button — inside card, top-right, always visible, no border */
.stack-del-btn {
  position: absolute; top: 8px; right: 10px;
  background: transparent; border: none;
  color: var(--text-ghost); font-size: 14px; line-height: 1;
  padding: 0; cursor: pointer;
  transition: color .15s;
}
.stack-del-btn:hover { color: #e55; }

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
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
  z-index: 10;
}
.stack-add-btn:hover { background: rgba(124,106,247,0.2); color: var(--accent); }

/* Right: figure + message */
.fig-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.verify-error-inline {
  font-size: 12px; line-height: 1.6; margin: 0;
  color: var(--error) !important;
}
.verify-error-inline span { margin-right: 4px; }

/* Assistant feedback bubble — dynamic status + concrete next-step suggestion */
.feedback-title { font-size: 13px; font-weight: 700; color: var(--text); margin: 0 0 2px; }
.feedback-line { font-size: 12px; color: var(--text-muted); line-height: 1.6; margin: 0; }
.feedback-missing { color: var(--text-dim); }
.feedback-suggestion { color: var(--accent); font-weight: 500; }

.upload-tips {
  padding: 4px 2px 0;
}
.upload-tips-title { font-size: 12px; font-weight: 600; color: var(--text-dim); margin: 0 0 8px; }
.upload-tips ul { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; }
.upload-tips li { font-size: 12px; color: var(--text-muted); line-height: 1.6; }

/* ══ Floating assistant widget ══ */
.assistant-widget {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 60;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}
.assistant-avatar {
  width: 48px; height: 48px; border-radius: 50%; flex-shrink: 0;
  background: var(--accent); border: none; color: white;
  font-size: 12px; font-weight: 700; cursor: grab; touch-action: none;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 6px 20px var(--shadow);
  transition: transform 0.15s;
}
.assistant-avatar:hover { transform: scale(1.06); }
.assistant-avatar:active { cursor: grabbing; }

/* Bare speech bubble — the default, no chat-box chrome around it */
.assistant-bubble {
  width: 260px; max-width: calc(100vw - 56px);
  background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 14px; padding: 10px 14px;
  box-shadow: 0 8px 24px var(--shadow);
  font-size: 12.5px; line-height: 1.6; color: var(--text-hi);
}
@keyframes blink { 0%,80%,100% { opacity: 0.2; } 40% { opacity: 1; } }

/* Inline animated dots appended after any "something's happening" bubble's
   status text — every busy state (extracting, identifying, researching)
   reads as the same visual language. */
.inline-dots { display: inline-flex; gap: 4px; margin-left: 4px; }
.inline-dots span {
  width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
  animation: blink 1.2s ease-in-out infinite;
}
.inline-dots span:nth-child(2) { animation-delay: 0.2s; }
.inline-dots span:nth-child(3) { animation-delay: 0.4s; }

/* Quick-reply row — appears only when the agent needs a confirm/correct */
.assistant-quick-row { display: flex; gap: 6px; align-items: center; }
.quick-confirm-btn {
  padding: 7px 12px; background: var(--accent); border: none;
  border-radius: 20px; color: white; font-size: 12px; font-weight: 600;
  cursor: pointer; white-space: nowrap; transition: background 0.2s;
}
.quick-confirm-btn:hover:not(:disabled) { background: var(--accent-hover); }
.quick-confirm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.quick-input-wrap {
  flex: 1; min-width: 0; display: flex; align-items: center; gap: 2px;
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 20px;
  padding: 3px 4px 3px 12px;
}
.quick-input {
  flex: 1; min-width: 0; background: none; border: none; outline: none;
  color: var(--text); font-size: 12px;
}
.quick-input::placeholder { color: var(--text-quiet); }
.quick-send {
  flex-shrink: 0; background: none; border: none;
  color: var(--accent); font-size: 19px; font-weight: 700; line-height: 1;
  padding: 0 8px; cursor: pointer; transition: transform 0.15s, color 0.2s;
}
.quick-send:hover:not(:disabled) { transform: translateX(2px); }
.quick-send:disabled { color: var(--text-quiet); cursor: not-allowed; }

/* Expanded history — a real panel, but only while explicitly open */
.assistant-log-panel {
  width: 300px; max-width: calc(100vw - 56px);
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 14px;
  box-shadow: 0 12px 32px var(--shadow);
  padding: 10px;
}
.assistant-log {
  max-height: 280px; overflow-y: auto;
  display: flex; flex-direction: column; gap: 10px;
  padding: 2px; scrollbar-width: none;
}
.assistant-log::-webkit-scrollbar { display: none; }

.chat-msg { display: flex; gap: 8px; align-items: flex-start; }
.chat-msg.user { flex-direction: row-reverse; }

.agent-avatar-sm {
  width: 22px; height: 22px; border-radius: 50%;
  background: var(--surface-raised); border: 1px solid var(--border-focus);
  display: flex; align-items: center; justify-content: center;
  font-size: 8px; font-weight: 700; color: var(--accent); flex-shrink: 0;
}

.msg-bubble {
  max-width: 82%; padding: 8px 11px; border-radius: 10px;
  font-size: 12.5px; line-height: 1.6;
  background: var(--surface-2); color: var(--text-hi); border: 1px solid var(--border-md);
}
.chat-msg.user .msg-bubble {
  background: var(--bubble-user-bg); border-color: var(--bubble-user-bdr); color: var(--text);
}

.retry-btn {
  display: block; margin-top: 6px;
  background: none; border: 1px solid var(--border-focus); border-radius: 6px;
  padding: 3px 10px; font-size: 11px; font-weight: 600; color: var(--accent);
  cursor: pointer; transition: background 0.15s;
}
.retry-btn:hover:not(:disabled) { background: var(--surface-raised); }
.retry-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.project-status { font-size: 12px; color: var(--accent); margin: 0; }

.btn-spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: white;
  border-radius: 50%; animation: spin 0.7s linear infinite; flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
