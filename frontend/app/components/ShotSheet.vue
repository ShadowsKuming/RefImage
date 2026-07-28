<template>
  <div class="sheet">
    <!-- Header -->
    <div class="sh-head">
      <div class="sh-title"><span class="sh-no">S{{ String(index).padStart(2, '0') }}</span><span class="sh-sep">|</span>{{ headTitle }}</div>
      <span class="sh-prio">{{ prioLabel }}</span>
    </div>

    <!-- Middle: image (left) + intent & pose (right) -->
    <div class="sh-mid">
      <div class="sh-imgwrap">
        <img v-if="imageUrl" :src="imageUrl" class="sh-img" draggable="false" />
        <div v-else class="sh-img ph">{{ t('shotEditor.sheetNoImage') }}</div>
      </div>
      <div class="sh-side">
        <div class="sh-block">
          <div class="sh-h">{{ t('shotEditor.sheetIntent') }}</div>
          <p class="sh-p">{{ intent }}</p>
        </div>
        <div class="sh-block">
          <div class="sh-h">{{ t('shotEditor.sheetPoseExpr') }}</div>
          <ul class="sh-ul">
            <li v-for="(p, i) in poseLines" :key="i">{{ p }}</li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Bottom: full-width key/value grid -->
    <div class="sh-grid">
      <div v-for="(f, i) in fields" :key="i" class="sh-cell">
        <span class="sh-k">{{ f.k }}</span><span class="sh-v">{{ f.v }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  plan: any
  imageUrl?: string
  index: number
  title?: string
}>()

const { t } = useLocale()
const pv = (v: string): string => (v ? t('shotEditor.pv.' + v) : v)

const PRIO: Record<string, string> = { high: '必拍', mid: '想拍', low: '可选' }
const ov = computed(() => props.plan?.overview || {})
const lg = computed(() => props.plan?.logistics || {})
const te = computed(() => props.plan?.technique || {})
const pm = computed(() => te.value.params || {})

const prioLabel = computed(() => pv(PRIO[ov.value.priority] || '想拍'))
const scene = computed(() => (lg.value.scene || {}).location || (lg.value.scene || {}).place || '')
const headTitle = computed(() => props.title || scene.value || t('shotEditor.sheetCard'))
const intent = computed(() => ov.value.goal || ov.value.synopsis || '—')

const poseLines = computed(() => {
  const out = [...(te.value.pose_tips || [])]
  if (pm.value.gaze) out.push(`${t('shotEditor.gazeLabel')}：${pv(pm.value.gaze)}`)
  if (te.value.expression) out.push(`${t('shotEditor.exprLabel')}：${te.value.expression}`)
  return out.length ? out : ['—']
})

const props_all = computed(() => {
  const chr = lg.value.props?.character || []
  const aux = (lg.value.props?.aux || []).map((a: any) => a.item || a)
  return [...chr, ...aux].filter(Boolean).join('、') || '—'
})

const fields = computed(() => [
  { k: t('shotEditor.scene'),        v: scene.value || '—' },
  { k: t('shotEditor.lblAngle'),     v: pv(pm.value.angle) || '—' },
  { k: t('shotEditor.lblShot'),      v: pv(pm.value.shot) || '—' },
  { k: t('shotEditor.compLabel'),    v: te.value.composition || '—' },
  { k: t('shotEditor.sheetLight'),   v: te.value.lighting || '—' },
  { k: t('shotEditor.sheetProps'),   v: props_all.value },
  { k: t('shotEditor.time'),         v: (lg.value.timing || {}).best_time || '—' },
  { k: t('shotEditor.sheetBackup'),  v: (te.value.risks || []).join('；') || '—' },
])
</script>

<style scoped>
.sheet {
  aspect-ratio: 297 / 210;
  width: 100%;
  background: #fbf6fa;
  color: #3a3340;
  padding: 5.2% 5.5%;
  display: flex;
  flex-direction: column;
  gap: 3.2%;
  font-size: clamp(9px, 1.55vw, 15px);
  line-height: 1.5;
  box-sizing: border-box;
}
.sh-head { display: flex; align-items: center; justify-content: space-between; border-bottom: 1.5px solid #e6c6da; padding-bottom: 2%; }
.sh-title { font-weight: 800; font-size: 1.35em; color: #2f2836; display: flex; align-items: center; gap: .45em; }
.sh-no { color: #b23a67; }
.sh-sep { color: #d9b6cb; font-weight: 400; }
.sh-prio { flex-shrink: 0; background: #efd6e5; color: #a2295c; font-weight: 700; font-size: .82em; padding: .28em .9em; border-radius: 999px; }

.sh-mid { display: flex; gap: 4%; flex: 1; min-height: 0; }
.sh-imgwrap { flex: 0 0 54%; }
.sh-img { width: 100%; height: 100%; object-fit: cover; border-radius: 6px; display: block; }
.sh-img.ph { display: grid; place-items: center; background: #efe4ec; color: #a892b3; }
.sh-side { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5%; }
.sh-h { color: #b23a67; font-weight: 800; font-size: 1.02em; margin-bottom: .3em; }
.sh-p { margin: 0; color: #4a4350; }
.sh-ul { margin: 0; padding-left: 1.1em; color: #4a4350; }
.sh-ul li { margin-bottom: .22em; }

.sh-grid { display: grid; grid-template-columns: 1fr 1fr; column-gap: 6%; row-gap: 2.4%; border-top: 1.5px solid #e6c6da; padding-top: 2.4%; }
.sh-cell { display: flex; gap: .7em; align-items: baseline; }
.sh-k { flex: 0 0 4.6em; color: #b23a67; font-weight: 700; }
.sh-v { flex: 1; min-width: 0; color: #4a4350; }

@media print {
  .sheet { aspect-ratio: auto; width: 297mm; height: 210mm; font-size: 12px; page-break-after: always; }
}
</style>
