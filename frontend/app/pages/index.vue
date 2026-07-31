<template>
  <div class="home-v2">
    <!-- ── Top bar ── -->
    <header class="hv-top">
      <div class="hv-brand">
        <span class="hv-logo"><Hexagon :size="22" /></span>
        <span class="hv-name">RefImage</span>
        <span class="hv-divider" />
        <span class="hv-sub">{{ t('home.subtitle') }}</span>
      </div>
      <div class="hv-actions">
        <div class="hv-switch" ref="themeSwitchEl">
          <button class="hv-top-btn" @click="themeOpen = !themeOpen; localeOpen = false"><Palette :size="16" />{{ currentThemeLabel }}</button>
          <transition name="hv-pop">
            <div v-if="themeOpen" class="hv-pop-panel">
              <button
                v-for="th in THEMES" :key="th.id" class="hv-pop-item"
                :class="{ on: theme === th.id }" @click="applyTheme(th.id); themeOpen = false"
              >
                <span class="hv-pop-dot" :style="{ background: th.accent }" />{{ th.label }}
              </button>
            </div>
          </transition>
        </div>
        <div class="hv-switch" ref="localeSwitchEl">
          <button class="hv-top-btn" @click="localeOpen = !localeOpen; themeOpen = false"><Languages :size="16" />{{ currentLocaleLabel }}</button>
          <transition name="hv-pop">
            <div v-if="localeOpen" class="hv-pop-panel">
              <button
                v-for="l in LOCALE_META" :key="l.id" class="hv-pop-item"
                :class="{ on: locale === l.id }" @click="applyLocale(l.id); localeOpen = false"
              >{{ l.label }}</button>
            </div>
          </transition>
        </div>
        <button class="hv-icon-btn" @click="comingSoon(t('home.notifications'))"><Bell :size="18" /></button>
        <div class="hv-user">
          <span class="hv-user-av"><Camera :size="15" /></span>
          <span class="hv-user-name">{{ userId || '…' }}</span>
        </div>
      </div>
    </header>

    <main class="hv-page">
      <!-- ── Hero ── -->
      <section class="hv-hero">
        <div class="hv-hero-text">
          <h1 class="hv-hero-title">{{ t('home.heroTitle') }}</h1>
          <p class="hv-hero-desc">{{ t('home.heroDescLine1') }}<br>{{ t('home.heroDescLine2') }}</p>
          <div class="hv-hero-cta">
            <button class="hv-btn primary" @click="onNewProject"><Plus :size="18" />{{ t('home.heroNewProject') }}</button>
            <label class="hv-btn ghost" :class="{ disabled: importing }">
              <input type="file" accept=".refimg" hidden @change="onImport" />
              <Upload :size="17" />{{ importing ? t('home.importing') : t('home.heroImportProject') }}
            </label>
            <button class="hv-btn ghost" @click="comingSoon(t('home.heroTemplates'))"><LayoutGrid :size="17" />{{ t('home.heroTemplates') }}</button>
          </div>
          <div v-if="importError" class="hv-import-err">{{ importError }}</div>
        </div>
        <div class="hv-hero-art">
          <span class="hv-spark s1"><Sparkles :size="20" /></span>
          <span class="hv-spark s2"><Sparkles :size="14" /></span>
          <span class="hv-spark s3"><Star :size="16" /></span>
          <img src="/mascot/normal.png" alt="RefImage" class="hv-mascot" />
        </div>
      </section>

      <!-- ── Body: projects + rail ── -->
      <section class="hv-body">
        <!-- main -->
        <div class="hv-main">
          <div class="hv-sec-head">
            <div class="hv-sec-left">
              <User :size="18" class="hv-sec-ico" />
              <span class="hv-sec-title">{{ t('home.myProjects') }}</span>
              <span class="hv-sec-count">{{ t('home.savedProjects') }} {{ projects.length }} / {{ PROJECT_LIMIT }}</span>
            </div>
            <div class="hv-view-toggle">
              <button :class="{ on: projView === 'grid' }" @click="projView = 'grid'"><LayoutGrid :size="15" /></button>
              <button :class="{ on: projView === 'list' }" @click="projView = 'list'"><List :size="15" /></button>
            </div>
          </div>

          <div v-if="projects.length" class="hv-proj" :class="projView">
            <div v-for="p in projects" :key="p.project_id" class="hv-card" @click="navigateTo(`/projects/${p.project_id}`)">
              <div class="hv-card-thumb">
                <img v-if="p.ref_thumb" :src="BASE_URL + p.ref_thumb" :alt="p.character" />
                <Hexagon v-else :size="24" class="hv-thumb-empty" />
              </div>
              <div class="hv-card-body">
                <div class="hv-card-name">{{ p.character }}</div>
                <div class="hv-card-series">{{ p.series || '—' }}</div>
                <div class="hv-card-meta"><Camera :size="13" />{{ p.shot_count }} {{ t('home.shotCountSuffix') }}</div>
              </div>
              <ArrowRight :size="16" class="hv-card-arrow" />
              <button class="hv-card-del" :title="t('home.deleteProjectTitle')" @click.stop="confirmDelete(p)"><X :size="14" /></button>
            </div>
          </div>
          <div v-else class="hv-empty">
            <Hexagon :size="34" />
            <p>{{ t('home.emptyProjects') }}</p>
          </div>
        </div>

        <!-- right rail -->
        <aside class="hv-rail">
          <div v-if="lastProject" class="hv-rail-card hv-continue">
            <div class="hv-rail-title"><Star :size="15" />{{ t('home.continueLast') }}</div>
            <div class="hv-cont-row" @click="navigateTo(`/projects/${lastProject.project_id}`)">
              <div class="hv-cont-thumb">
                <img v-if="lastProject.ref_thumb" :src="BASE_URL + lastProject.ref_thumb" :alt="lastProject.character" />
                <Hexagon v-else :size="20" class="hv-thumb-empty" />
              </div>
              <div class="hv-cont-info">
                <div class="hv-cont-name">{{ lastProject.character }}</div>
                <div class="hv-cont-series">{{ lastProject.series || '—' }}</div>
              </div>
            </div>
            <button class="hv-btn primary sm block" @click="navigateTo(`/projects/${lastProject.project_id}`)">{{ t('home.continueEdit') }}</button>
          </div>

          <div class="hv-rail-card hv-soon">
            <div class="hv-rail-title"><Clock :size="15" />{{ t('home.recentActivity') }}</div>
            <div class="hv-soon-body"><span class="hv-soon-badge">{{ t('home.comingSoonBadge') }}</span>{{ t('home.comingSoonActivity') }}</div>
          </div>

          <div class="hv-rail-card hv-soon">
            <div class="hv-rail-title"><LayoutGrid :size="15" />{{ t('home.recommendedTemplates') }}</div>
            <div class="hv-soon-body"><span class="hv-soon-badge">{{ t('home.comingSoonBadge') }}</span>{{ t('home.comingSoonTemplates') }}</div>
          </div>
        </aside>
      </section>

      <!-- ── Feature strip ── -->
      <section class="hv-features">
        <div class="hv-feat"><FolderKanban :size="20" /><div><b>{{ t('home.featOrganizeTitle') }}</b><span>{{ t('home.featOrganizeDesc') }}</span></div></div>
        <div class="hv-feat"><CalendarClock :size="20" /><div><b>{{ t('home.featPlanTitle') }}</b><span>{{ t('home.featPlanDesc') }}</span></div></div>
        <div class="hv-feat"><Users :size="20" /><div><b>{{ t('home.featTeamTitle') }}</b><span>{{ t('home.featTeamDesc') }}</span></div></div>
        <div class="hv-feat"><Cloud :size="20" /><div><b>{{ t('home.featCloudTitle') }}</b><span>{{ t('home.featCloudDesc') }}</span></div></div>
      </section>
    </main>

    <!-- toast -->
    <transition name="hv-toast">
      <div v-if="toast" class="hv-toast">{{ toast }}</div>
    </transition>

    <!-- Limit dialog -->
    <div v-if="showLimitDialog" class="dialog-backdrop" @click.self="showLimitDialog = false">
      <div class="dialog">
        <div class="dialog-icon">⚠️</div>
        <div class="dialog-title">{{ t('home.limitDialogTitle') }}</div>
        <div class="dialog-body">{{ t('home.limitDialogBody1', { limit: PROJECT_LIMIT }) }}<br>{{ t('home.limitDialogBody2') }}</div>
        <div class="dialog-footer"><button class="dialog-btn primary" @click="showLimitDialog = false">{{ t('home.limitDialogOk') }}</button></div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div v-if="deleteTarget" class="dialog-backdrop" @click.self="deleteTarget = null">
      <div class="dialog">
        <div class="dialog-title">{{ t('home.deleteDialogTitle', { name: deleteTarget.character }) }}</div>
        <div class="dialog-body">{{ t('home.deleteDialogBody1') }}<br>{{ t('home.deleteDialogBody2') }}</div>
        <div class="dialog-footer">
          <button class="dialog-btn cancel" @click="deleteTarget = null">{{ t('home.deleteCancel') }}</button>
          <button class="dialog-btn danger" :disabled="deleting" @click="doDelete">{{ deleting ? t('home.deleting') : t('home.deleteConfirm') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useApi } from '~/composables/useApi'
import {
  Hexagon, Bell, Camera, Plus, Upload, LayoutGrid, List, Palette, Languages,
  Sparkles, Star, User, ArrowRight, X, Clock, FolderKanban, CalendarClock, Users, Cloud,
} from 'lucide-vue-next'

definePageMeta({ ssr: false })

const PROJECT_LIMIT = 5

const api = useApi()
const { t, locale, LOCALE_META, apply: applyLocale } = useLocale()
const { theme, THEMES, apply: applyTheme } = useTheme()
const projects        = ref<any[]>([])
const projView        = ref<'grid' | 'list'>('grid')
const importing       = ref(false)
const importError     = ref('')
const showLimitDialog = ref(false)
const deleteTarget    = ref<any | null>(null)
const deleting        = ref(false)
const toast           = ref('')
const userId          = ref('')
const { public: { apiBase: BASE_URL } } = useRuntimeConfig()

// most-recently created project = "continue where you left off"
const lastProject = computed(() => projects.value[0] ?? null)

const currentThemeLabel  = computed(() => THEMES.find(x => x.id === theme.value)?.label ?? '主题')
const currentLocaleLabel = computed(() => LOCALE_META.find(x => x.id === locale.value)?.label ?? '语言')

// ── theme/language popovers (topbar) ──────────────────────
const themeOpen      = ref(false)
const localeOpen     = ref(false)
const themeSwitchEl  = ref<HTMLElement | null>(null)
const localeSwitchEl = ref<HTMLElement | null>(null)
function onDocClick(e: MouseEvent) {
  if (themeSwitchEl.value && !themeSwitchEl.value.contains(e.target as Node)) themeOpen.value = false
  if (localeSwitchEl.value && !localeSwitchEl.value.contains(e.target as Node)) localeOpen.value = false
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

onMounted(async () => {
  try { projects.value = await api.listProjects() }
  catch (e) { console.error('Failed to load projects', e) }
  try { userId.value = (await api.getMe()).user_id }
  catch (e) { console.error('Failed to load user', e) }
})

let toastTimer: any = null
function comingSoon(name: string) {
  toast.value = t('home.comingSoonToast', { name })
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 1800)
}

function playDing() {
  try {
    const ctx = new AudioContext()
    const osc = ctx.createOscillator(); const gain = ctx.createGain()
    osc.connect(gain); gain.connect(ctx.destination)
    osc.type = 'sine'; osc.frequency.value = 880
    gain.gain.setValueAtTime(0.35, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6)
    osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.6)
  } catch {}
}

function onNewProject() {
  if (projects.value.length >= PROJECT_LIMIT) { showLimitDialog.value = true; playDing(); return }
  navigateTo('/projects/new')
}

async function onImport(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  importing.value = true; importError.value = ''
  try {
    const result = await api.importProject(file)
    projects.value = await api.listProjects()
    navigateTo(`/projects/${result.project_id}`)
  } catch (err: any) { importError.value = err.message ?? t('home.importFailed') }
  importing.value = false
  ;(e.target as HTMLInputElement).value = ''
}

function confirmDelete(p: any) { deleteTarget.value = p }

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await api.deleteProject(deleteTarget.value.project_id)
    projects.value = projects.value.filter(p => p.project_id !== deleteTarget.value!.project_id)
    deleteTarget.value = null
  } catch (e: any) { console.error('delete failed', e) }
  deleting.value = false
}
</script>

<style scoped>
/* ── uses the app's global theme tokens (app.vue [data-theme="..."]) so this
   page recolors with every theme, not a private palette ── */
.home-v2 {
  min-height: 100vh;
  background: var(--bg);
  color: var(--text-hi, var(--text));
  font-family: inherit;
}

/* top bar */
.hv-top {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 28px; background: var(--surface);
  border-bottom: 1px solid var(--border-md); position: sticky; top: 0; z-index: 20;
}
.hv-brand { display: flex; align-items: center; gap: 10px; }
.hv-logo { color: var(--accent); display: flex; }
.hv-name { font-size: 18px; font-weight: 800; color: var(--text-hi, var(--text)); letter-spacing: -.2px; }
.hv-divider { width: 1px; height: 16px; background: var(--border-md); margin: 0 2px; }
.hv-sub { font-size: 12.5px; color: var(--text-muted); }
.hv-actions { display: flex; align-items: center; gap: 8px; }
.hv-top-btn {
  display: inline-flex; align-items: center; gap: 5px; padding: 7px 12px;
  border: 1px solid var(--border-md); background: transparent; border-radius: 9px;
  color: var(--text-muted); font-size: 13px; font-family: inherit; cursor: pointer; transition: .15s;
}
.hv-top-btn:hover { border-color: var(--accent); color: var(--accent); }
.hv-switch { position: relative; }
.hv-pop-panel {
  position: absolute; top: calc(100% + 8px); right: 0; z-index: 50;
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 12px;
  padding: 6px; min-width: 128px; display: flex; flex-direction: column; gap: 2px;
  box-shadow: 0 10px 30px rgba(0,0,0,.14);
}
.hv-pop-item {
  display: flex; align-items: center; gap: 8px; padding: 7px 10px; border-radius: 8px;
  border: none; background: transparent; color: var(--text-muted); font-size: 12.5px;
  font-family: inherit; text-align: left; cursor: pointer; transition: .12s; white-space: nowrap;
}
.hv-pop-item:hover { background: var(--accent-soft, var(--surface-raised)); color: var(--text-hi, var(--text)); }
.hv-pop-item.on { background: var(--accent-soft, var(--surface-raised)); color: var(--accent); font-weight: 600; }
.hv-pop-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.hv-pop-enter-active, .hv-pop-leave-active { transition: opacity .14s, transform .14s; }
.hv-pop-enter-from, .hv-pop-leave-to { opacity: 0; transform: translateY(6px) scale(.97); }
.hv-icon-btn {
  width: 34px; height: 34px; display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid var(--border-md); background: transparent; border-radius: 9px;
  color: var(--text-muted); cursor: pointer; transition: .15s;
}
.hv-icon-btn:hover { border-color: var(--accent); color: var(--accent); }
.hv-user { display: flex; align-items: center; gap: 7px; padding: 5px 12px 5px 6px;
  border: 1px solid var(--border-md); border-radius: 999px; }
.hv-user-av { width: 26px; height: 26px; border-radius: 50%; background: var(--accent-soft, var(--surface-raised));
  color: var(--accent); display: flex; align-items: center; justify-content: center; }
.hv-user-name { font-size: 13px; font-weight: 600; color: var(--text-hi, var(--text)); }

/* page */
.hv-page { max-width: 1180px; margin: 0 auto; padding: 26px 28px 48px; }

/* hero */
.hv-hero {
  position: relative; display: flex; align-items: stretch; justify-content: space-between;
  gap: 20px; overflow: hidden;
  background: linear-gradient(120deg, var(--surface-raised), var(--surface-2));
  border: 1px solid var(--border-md); border-radius: 22px; padding: 40px 44px; min-height: 240px;
}
.hv-hero-text { max-width: 560px; z-index: 2; align-self: center; }
.hv-hero-title { font-size: 34px; font-weight: 800; color: var(--text-hi, var(--text)); letter-spacing: -.5px; margin: 0 0 14px; }
.hv-hero-desc { font-size: 14.5px; line-height: 1.75; color: var(--text-muted); margin: 0 0 24px; }
.hv-hero-cta { display: flex; gap: 12px; flex-wrap: wrap; }
.hv-import-err { margin-top: 12px; font-size: 12px; color: #c0392b; }

.hv-btn {
  display: inline-flex; align-items: center; gap: 7px; padding: 12px 22px;
  border-radius: 11px; font-size: 14.5px; font-weight: 600; font-family: inherit;
  cursor: pointer; border: 1px solid transparent; transition: .15s; white-space: nowrap;
}
.hv-btn.primary { background: var(--accent); color: #fff; box-shadow: 0 6px 16px -6px var(--accent); }
.hv-btn.primary:hover { background: var(--accent-hover); }
.hv-btn.ghost { background: var(--surface); border-color: var(--border-md); color: var(--text-hi, var(--text)); }
.hv-btn.ghost:hover { border-color: var(--accent); color: var(--accent); }
.hv-btn.disabled { opacity: .55; pointer-events: none; }
.hv-btn.sm { padding: 9px 16px; font-size: 13px; }
.hv-btn.block { width: 100%; justify-content: center; }

.hv-hero-art { position: relative; flex-shrink: 0; width: 300px; display: flex; align-items: flex-end; justify-content: center; }
.hv-mascot { height: 260px; width: auto; object-fit: contain; filter: drop-shadow(0 10px 22px rgba(0,0,0,.14)); }
.hv-spark { position: absolute; color: var(--accent); opacity: .7; }
.hv-spark.s1 { top: 18px; left: 20px; }
.hv-spark.s2 { top: 90px; left: 0; color: #d8b24a; }
.hv-spark.s3 { top: 40px; right: 10px; color: #d8b24a; }

/* body */
.hv-body { display: grid; grid-template-columns: 1fr 320px; gap: 22px; margin-top: 28px; }
@media (max-width: 940px) { .hv-body { grid-template-columns: 1fr; } }

.hv-sec-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.hv-sec-left { display: flex; align-items: center; gap: 9px; }
.hv-sec-ico { color: var(--accent); }
.hv-sec-title { font-size: 17px; font-weight: 700; color: var(--text-hi, var(--text)); }
.hv-sec-count { font-size: 12px; color: var(--text-quiet); }
.hv-view-toggle { display: flex; gap: 2px; background: var(--surface); border: 1px solid var(--border-md); border-radius: 9px; padding: 2px; }
.hv-view-toggle button { width: 30px; height: 26px; display: flex; align-items: center; justify-content: center;
  border: none; background: transparent; border-radius: 7px; color: var(--text-quiet); cursor: pointer; transition: .12s; }
.hv-view-toggle button.on { background: var(--accent-soft, var(--surface-raised)); color: var(--accent); }

.hv-proj.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }
.hv-proj.list { display: flex; flex-direction: column; gap: 10px; }

.hv-card {
  position: relative; display: flex; gap: 12px; align-items: center;
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 14px;
  padding: 14px; cursor: pointer; transition: .15s;
}
.hv-card:hover { border-color: var(--accent); box-shadow: 0 8px 22px -12px var(--accent); transform: translateY(-1px); }
.hv-proj.grid .hv-card { flex-direction: column; align-items: stretch; text-align: left; }
.hv-card-thumb {
  border-radius: 11px; overflow: hidden; background: var(--accent-soft, var(--surface-raised));
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.hv-proj.grid .hv-card-thumb { width: 100%; aspect-ratio: 4/3; }
.hv-proj.list .hv-card-thumb { width: 54px; height: 54px; }
.hv-card-thumb img { width: 100%; height: 100%; object-fit: cover; }
.hv-thumb-empty { color: var(--accent); }
.hv-card-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.hv-card-name { font-size: 14px; font-weight: 700; color: var(--text-hi, var(--text)); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hv-card-series { font-size: 12px; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hv-card-meta { display: inline-flex; align-items: center; gap: 5px; font-size: 11.5px; color: var(--text-quiet); margin-top: 2px; }
.hv-card-arrow { color: var(--text-quiet); flex-shrink: 0; }
.hv-proj.grid .hv-card-arrow { position: absolute; right: 14px; bottom: 14px; }
.hv-card-del {
  position: absolute; top: 8px; right: 8px; width: 22px; height: 22px;
  display: flex; align-items: center; justify-content: center;
  background: var(--surface); border: 1px solid var(--border-md); border-radius: 7px;
  color: var(--text-quiet); cursor: pointer; opacity: 0; transition: .12s;
}
.hv-card:hover .hv-card-del { opacity: 1; }
.hv-card-del:hover { color: #e55; border-color: #e55; }

.hv-empty { text-align: center; color: var(--text-quiet); padding: 50px 20px;
  background: var(--surface); border: 1px dashed var(--border-md); border-radius: 16px; }
.hv-empty p { font-size: 13px; margin-top: 12px; }

/* rail */
.hv-rail { display: flex; flex-direction: column; gap: 14px; }
.hv-rail-card { background: var(--surface); border: 1px solid var(--border-md); border-radius: 16px; padding: 16px; }
.hv-rail-title { display: flex; align-items: center; gap: 7px; font-size: 13.5px; font-weight: 700; color: var(--text-hi, var(--text)); margin-bottom: 12px; }
.hv-rail-title svg { color: var(--accent); }
.hv-cont-row { display: flex; gap: 10px; align-items: center; cursor: pointer; margin-bottom: 12px; }
.hv-cont-thumb { width: 46px; height: 46px; border-radius: 10px; overflow: hidden; background: var(--accent-soft, var(--surface-raised));
  display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.hv-cont-thumb img { width: 100%; height: 100%; object-fit: cover; }
.hv-cont-name { font-size: 13.5px; font-weight: 700; color: var(--text-hi, var(--text)); }
.hv-cont-series { font-size: 11.5px; color: var(--text-muted); }
.hv-soon-body { font-size: 12.5px; color: var(--text-quiet); line-height: 1.7; }
.hv-soon-badge { display: inline-block; font-size: 10px; font-weight: 700; color: var(--accent);
  background: var(--accent-soft, var(--surface-raised)); border-radius: 5px; padding: 1px 7px; margin-right: 7px; vertical-align: 1px; }

/* features */
.hv-features { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: 28px; }
@media (max-width: 760px) { .hv-features { grid-template-columns: repeat(2, 1fr); } }
.hv-feat { display: flex; gap: 12px; align-items: flex-start; background: var(--surface);
  border: 1px solid var(--border-md); border-radius: 14px; padding: 16px; }
.hv-feat > svg { color: var(--accent); flex-shrink: 0; margin-top: 2px; }
.hv-feat b { display: block; font-size: 13.5px; color: var(--text-hi, var(--text)); margin-bottom: 3px; }
.hv-feat span { display: block; font-size: 11.5px; color: var(--text-muted); line-height: 1.55; }

/* toast */
.hv-toast { position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%);
  background: rgba(28,26,24,.94); color: #fff; font-size: 13px; padding: 10px 20px; border-radius: 10px; z-index: 300;
  box-shadow: 0 8px 24px rgba(0,0,0,.25); }
.hv-toast-enter-active, .hv-toast-leave-active { transition: opacity .2s, transform .2s; }
.hv-toast-enter-from, .hv-toast-leave-to { opacity: 0; transform: translate(-50%, 8px); }

/* dialogs (shared) */
.dialog-backdrop { position: fixed; inset: 0; z-index: 200; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; }
.dialog { background: var(--surface); border: 1px solid var(--border-md); border-radius: 14px; padding: 28px 28px 22px; min-width: 300px; max-width: 360px; display: flex; flex-direction: column; gap: 12px; box-shadow: 0 8px 32px rgba(0,0,0,.22); }
.dialog-icon { font-size: 28px; text-align: center; }
.dialog-title { font-size: 15px; font-weight: 700; color: var(--text-hi, var(--text)); text-align: center; }
.dialog-body { font-size: 13px; color: var(--text-muted); line-height: 1.65; text-align: center; }
.dialog-footer { display: flex; gap: 8px; justify-content: center; margin-top: 4px; }
.dialog-btn { padding: 8px 22px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: .15s; font-family: inherit; }
.dialog-btn:disabled { opacity: .55; cursor: not-allowed; }
.dialog-btn.primary { background: var(--accent); color: #fff; }
.dialog-btn.primary:hover { background: var(--accent-hover); }
.dialog-btn.cancel { background: var(--accent-soft, var(--surface-raised)); color: var(--text-hi, var(--text)); }
.dialog-btn.danger { background: #e55; color: #fff; }
.dialog-btn.danger:hover { background: #c33; }
</style>
