<template>
  <div class="hb">
    <!-- Toolbar (screen only) -->
    <div class="hb-bar">
      <button class="hb-back" @click="goBack"><span class="hb-chev">‹</span>{{ t('handbook.back') }}</button>
      <div class="hb-titlewrap">
        <span class="hb-title">{{ t('handbook.title') }}</span>
        <span v-if="pageTotal" class="hb-count">{{ t('handbook.pageCount', { n: pageTotal }) }}</span>
      </div>
      <button class="hb-print" :disabled="!pageTotal" @click="printNow"><Printer :size="16" /> {{ t('handbook.print') }}</button>
    </div>

    <div v-if="loading" class="hb-state">{{ t('handbook.loading') }}</div>
    <div v-else-if="!pageTotal" class="hb-state">{{ t('handbook.empty') }}</div>

    <div v-else class="hb-pages">
      <!-- 01 封面与概览 -->
      <div class="hb-page"><div class="doc cover">
        <div class="doc-eyebrow">01 · {{ t('handbook.secCover') }}</div>
        <div class="cover-body">
          <div class="cover-left">
            <img v-if="coverImg" :src="coverImg" class="cover-img" />
            <div v-else class="cover-img ph" />
          </div>
          <div class="cover-right">
            <div class="cover-title">{{ data.project.title || t('handbook.title') }}</div>
            <div v-if="data.project.series" class="cover-series">{{ data.project.series }}</div>
            <div v-if="data.project.theme" class="cover-sec"><div class="doc-h">{{ t('handbook.theme') }}</div><p class="doc-p">{{ data.project.theme }}</p></div>
            <div class="cover-stats">
              <div v-for="s in coverStats" :key="s.k" class="cstat"><span class="cstat-k">{{ s.k }}</span><span class="cstat-v">{{ s.v }}</span></div>
            </div>
            <div v-if="data.project.direction" class="cover-sec"><div class="doc-h">{{ t('handbook.direction') }}</div><p class="doc-p">{{ data.project.direction }}</p></div>
            <div v-if="data.summary.tags.length" class="cover-sec">
              <div class="doc-h">{{ t('handbook.keywords') }}</div>
              <div class="kw-row"><span v-for="tg in data.summary.tags" :key="tg" class="kw">{{ tg }}</span></div>
            </div>
          </div>
        </div>
      </div></div>

      <!-- 02 拍摄日程与准备清单 -->
      <div v-if="hasPrep || data.schedule.length" class="hb-page"><div class="doc">
        <div class="doc-eyebrow">02 · {{ t('handbook.secSchedulePrep') }}</div>
        <div v-if="data.schedule.length" class="sched-block">
          <div class="doc-h">{{ t('handbook.schedSuggested') }}</div>
          <div class="sc-table">
            <div class="sc-row sc-head">
              <span class="sc-c sc-time">{{ t('handbook.colTime') }}</span>
              <span class="sc-c sc-scene">{{ t('handbook.colScene') }}</span>
              <span class="sc-c sc-shots">{{ t('handbook.colShots') }}</span>
              <span class="sc-c sc-content">{{ t('handbook.colContent') }}</span>
              <span class="sc-c sc-dur">{{ t('handbook.colDuration') }}</span>
            </div>
            <div v-for="(r, i) in data.schedule" :key="i" class="sc-row">
              <span class="sc-c sc-time">{{ r.time || '—' }}</span>
              <span class="sc-c sc-scene">{{ r.scene || '—' }}</span>
              <span class="sc-c sc-shots">{{ r.shots || '—' }}</span>
              <span class="sc-c sc-content">{{ r.content || '—' }}</span>
              <span class="sc-c sc-dur">{{ r.duration || '—' }}</span>
            </div>
          </div>
        </div>
        <div class="prep-cols">
          <div v-for="col in prepCols" :key="col.k" class="prep-col">
            <div class="prep-h">{{ col.k }}</div>
            <div v-for="item in col.items" :key="item" class="prep-item"><span class="cbox" />{{ item }}</div>
            <div v-if="!col.items.length" class="prep-empty">—</div>
          </div>
        </div>
      </div></div>

      <!-- 03 视觉风格参考 -->
      <div v-if="data.mood_images.length || data.palette.length" class="hb-page"><div class="doc">
        <div class="doc-eyebrow">03 · {{ t('handbook.secVisual') }}</div>
        <div v-if="data.mood_images.length" class="vis-block">
          <div class="doc-h">{{ t('handbook.moodBoard') }}</div>
          <div class="mood-grid"><img v-for="(m, i) in data.mood_images" :key="i" :src="imgUrl(m)" class="mood-img" /></div>
        </div>
        <div v-if="data.palette.length" class="vis-block">
          <div class="doc-h">{{ t('handbook.palette') }}</div>
          <div class="pal-row"><span v-for="(c, i) in data.palette" :key="i" class="pal" :style="{ background: c }" /></div>
        </div>
      </div></div>

      <!-- 04+ 镜头详表 -->
      <div v-for="p in data.pages" :key="p.shot_id" class="hb-page">
        <ShotSheet :plan="p.plan" :image-url="imgUrl(p.image_url)" :index="p.index" :title="p.title" />
      </div>

      <!-- 备用方案与备注 -->
      <div v-if="data.backups.length" class="hb-page"><div class="doc">
        <div class="doc-eyebrow">{{ t('handbook.secBackup') }}</div>
        <div class="bk-table">
          <div class="bk-row bk-head"><span class="bk-c1">{{ t('handbook.problem') }}</span><span class="bk-c2">{{ t('handbook.solution') }}</span></div>
          <template v-for="b in data.backups" :key="b.label">
            <div v-if="b.backup" class="bk-row"><span class="bk-c1"><b>{{ b.label }}</b> {{ b.title }}</span><span class="bk-c2">{{ b.backup }}</span></div>
            <div v-for="(r, i) in b.risks" :key="b.label + i" class="bk-row"><span class="bk-c1"><b>{{ b.label }}</b> {{ t('handbook.risk') }}</span><span class="bk-c2">{{ r }}</span></div>
          </template>
        </div>
        <div class="doc-h onsite">{{ t('handbook.onsiteNotes') }}</div>
        <div class="onsite-lines"><span /><span /><span /></div>
      </div></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Printer } from 'lucide-vue-next'

definePageMeta({ ssr: false })

const route = useRoute()
const api = useApi()
const { t } = useLocale()
const { public: { apiBase: BASE_URL } } = useRuntimeConfig()

const projectId = route.params.id as string
const loading = ref(true)
const data = ref<any>({
  project: {}, summary: { tags: [] }, palette: [], mood_images: [], schedule: [],
  prep: { costumes: [], props: [], equipment: [], locations: [] }, backups: [], pages: [],
})

const imgUrl = (u: string) => (u ? BASE_URL + u : '')
const coverImg = computed(() => imgUrl(data.value.project.cover_url) || imgUrl(data.value.mood_images[0] || ''))
const pageTotal = computed(() => data.value.pages.length +
  1 /*cover*/ + ((hasPrep.value || data.value.schedule.length) ? 1 : 0) +
  ((data.value.mood_images.length || data.value.palette.length) ? 1 : 0) +
  (data.value.backups.length ? 1 : 0))

function fmtDuration(mins: number): string {
  if (!mins) return '—'
  if (mins < 60) return `${mins} ${t('projectCanvas.unitMinutes')}`
  const h = mins / 60
  return `${t('projectCanvas.approxPrefix')} ${Number.isInteger(h) ? h : h.toFixed(1)} ${t('projectCanvas.unitHours')}`
}
const coverStats = computed(() => {
  const s = data.value.summary, p = data.value.project
  return [
    { k: t('handbook.stCharacter'), v: p.character || '—' },
    { k: t('handbook.stDate'), v: p.shoot_date || '—' },
    { k: t('handbook.stDuration'), v: fmtDuration(s.duration_minutes) },
    { k: t('handbook.stShots'), v: String(s.shot_count) },
    { k: t('handbook.stScenes'), v: String(s.scene_count) },
    { k: t('handbook.stCostumes'), v: String(s.costume_count) },
  ]
})
const prepCols = computed(() => [
  { k: t('handbook.prepCostume'), items: data.value.prep.costumes },
  { k: t('handbook.prepProps'), items: data.value.prep.props },
  { k: t('handbook.prepEquip'), items: data.value.prep.equipment },
  { k: t('handbook.prepLoc'), items: data.value.prep.locations },
])
const hasPrep = computed(() => prepCols.value.some(c => c.items.length))

function goBack() { navigateTo(`/projects/${projectId}`) }
function printNow() { window.print() }

onMounted(async () => {
  try {
    const d = await api.getHandbook(projectId)
    if (d) data.value = { ...data.value, ...d }
  } catch (e) { console.error('handbook', e) }
  loading.value = false
})
</script>

<style scoped>
.hb { min-height: 100vh; background: var(--surface-2, #ece7ee); }
.hb-bar { position: sticky; top: 0; z-index: 10; display: flex; align-items: center; gap: 14px; padding: 12px 20px; background: var(--surface); border-bottom: 1px solid var(--border); }
.hb-back { display: inline-flex; align-items: center; gap: 3px; background: none; border: none; color: var(--text-muted); font-size: 13px; font-family: inherit; cursor: pointer; }
.hb-back:hover { color: var(--accent); }
.hb-chev { font-size: 18px; line-height: 1; }
.hb-titlewrap { display: flex; align-items: baseline; gap: 10px; margin: 0 auto 0 4px; }
.hb-title { font-size: 15px; font-weight: 700; color: var(--text-hi); }
.hb-count { font-size: 12px; color: var(--text-quiet); }
.hb-print { display: inline-flex; align-items: center; gap: 6px; background: var(--accent); color: #fff; border: none; border-radius: 8px; padding: 8px 15px; font-size: 13px; font-weight: 600; font-family: inherit; cursor: pointer; transition: opacity .12s; }
.hb-print:hover:not(:disabled) { opacity: .9; }
.hb-print:disabled { opacity: .5; cursor: not-allowed; }
.hb-state { padding: 60px 20px; text-align: center; color: var(--text-muted); font-size: 14px; }

.hb-pages { display: flex; flex-direction: column; align-items: center; gap: 20px; padding: 24px 16px 48px; }
.hb-page { width: min(96vw, 1100px); box-shadow: 0 6px 28px rgba(0,0,0,.16); border-radius: 8px; overflow: hidden; }

/* paper page shared with ShotSheet look */
.doc {
  aspect-ratio: 297 / 210; width: 100%; box-sizing: border-box;
  background: #fbf6fa; color: #3a3340; padding: 4.5% 5%;
  display: flex; flex-direction: column; gap: 3%;
  font-size: clamp(9px, 1.5vw, 15px); line-height: 1.5;
}
.doc-eyebrow { color: #a2295c; font-weight: 800; font-size: 1.05em; letter-spacing: .02em; }
.doc-h { color: #b23a67; font-weight: 800; font-size: 1em; margin-bottom: .4em; }
.doc-p { margin: 0; color: #4a4350; }

/* cover */
.cover-body { display: flex; gap: 4%; flex: 1; min-height: 0; }
.cover-left { flex: 0 0 44%; }
.cover-img { width: 100%; height: 100%; object-fit: cover; border-radius: 6px; display: block; }
.cover-img.ph { background: #efe4ec; }
.cover-right { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2.6%; overflow: hidden; }
.cover-title { font-size: 1.8em; font-weight: 800; color: #2f2836; line-height: 1.2; }
.cover-series { font-size: 1em; color: #8a7d92; margin-top: -.3em; }
.cover-sec { margin-top: .3em; }
.cover-stats { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 3% 5%; margin: .4em 0; }
.cstat { display: flex; flex-direction: column; }
.cstat-k { font-size: .8em; color: #b23a67; font-weight: 700; }
.cstat-v { font-size: .95em; color: #4a4350; }
.kw-row { display: flex; flex-wrap: wrap; gap: .5em; }
.kw { background: #efd6e5; color: #a2295c; border-radius: 999px; padding: .2em .8em; font-size: .8em; font-weight: 600; }

/* schedule table */
.sched-block { margin-bottom: 1em; }
.sc-table { display: flex; flex-direction: column; border: 1px solid #e6c6da; border-radius: 6px; overflow: hidden; font-size: .9em; }
.sc-row { display: flex; border-top: 1px solid #efdce8; }
.sc-row:first-child { border-top: none; }
.sc-head { background: #f3e3ee; font-weight: 700; color: #a2295c; }
.sc-c { padding: .45em .7em; border-right: 1px solid #efdce8; }
.sc-c:last-child { border-right: none; }
.sc-time { flex: 0 0 18%; }
.sc-scene { flex: 0 0 20%; }
.sc-shots { flex: 0 0 16%; }
.sc-content { flex: 1; }
.sc-dur { flex: 0 0 16%; }

/* prep checklist */
.prep-cols { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4%; flex: 1; }
.prep-col { display: flex; flex-direction: column; gap: .55em; }
.prep-h { color: #b23a67; font-weight: 800; border-bottom: 1.5px solid #e6c6da; padding-bottom: .4em; }
.prep-item { display: flex; align-items: center; gap: .55em; font-size: .92em; color: #4a4350; }
.cbox { width: .9em; height: .9em; border: 1.4px solid #b78; border-radius: 3px; flex-shrink: 0; }
.prep-empty { color: #b8a; }

/* visual */
.vis-block { }
.mood-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2.5%; }
.mood-img { width: 100%; aspect-ratio: 4/3; object-fit: cover; border-radius: 5px; display: block; }
.pal-row { display: flex; gap: 1.5%; }
.pal { flex: 1; height: 3.2em; border-radius: 6px; }

/* backup */
.bk-table { display: flex; flex-direction: column; border: 1px solid #e6c6da; border-radius: 6px; overflow: hidden; }
.bk-row { display: flex; border-top: 1px solid #efdce8; }
.bk-row:first-child { border-top: none; }
.bk-head { background: #f3e3ee; font-weight: 700; color: #a2295c; }
.bk-c1 { flex: 0 0 38%; padding: .5em .8em; border-right: 1px solid #efdce8; }
.bk-c2 { flex: 1; padding: .5em .8em; color: #4a4350; }
.doc-h.onsite { margin-top: 1em; }
.onsite-lines { display: flex; flex-direction: column; gap: 1.4em; }
.onsite-lines span { border-bottom: 1px dashed #d9b6cb; }

@page { size: A4 landscape; margin: 0; }
@media print {
  .hb { background: #fff; }
  .hb-bar { display: none; }
  .hb-pages { gap: 0; padding: 0; }
  .hb-page { width: 297mm; box-shadow: none; border-radius: 0; }
  .doc { width: 297mm; height: 210mm; aspect-ratio: auto; font-size: 12px; page-break-after: always; }
}
</style>
