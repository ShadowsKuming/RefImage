<template>
  <div class="hb">
    <!-- Toolbar (screen only) -->
    <div class="hb-bar">
      <button class="hb-back" @click="goBack"><span class="hb-chev">‹</span>{{ t('handbook.back') }}</button>
      <div class="hb-titlewrap">
        <span class="hb-title">{{ t('handbook.title') }}</span>
        <span v-if="pages.length" class="hb-count">{{ t('handbook.pageCount', { n: pages.length }) }}</span>
      </div>
      <button class="hb-print" :disabled="!pages.length" @click="printNow"><Printer :size="16" /> {{ t('handbook.print') }}</button>
    </div>

    <div v-if="loading" class="hb-state">{{ t('handbook.loading') }}</div>
    <div v-else-if="!pages.length" class="hb-state">{{ t('handbook.empty') }}</div>

    <div v-else class="hb-pages">
      <div v-for="p in pages" :key="p.shot_id" class="hb-page">
        <ShotSheet :plan="p.plan" :image-url="imgUrl(p.image_url)" :index="p.index" :title="p.title" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Printer } from 'lucide-vue-next'

definePageMeta({ ssr: false })

const route = useRoute()
const api = useApi()
const { t } = useLocale()
const { public: { apiBase: BASE_URL } } = useRuntimeConfig()

const projectId = route.params.id as string
const pages = ref<any[]>([])
const loading = ref(true)

const imgUrl = (u: string) => (u ? BASE_URL + u : '')
function goBack() { navigateTo(`/projects/${projectId}`) }
function printNow() { window.print() }

onMounted(async () => {
  try {
    const data = await api.getHandbook(projectId)
    pages.value = data?.pages ?? []
  } catch (e) { console.error('handbook', e) }
  loading.value = false
})
</script>

<style scoped>
.hb { min-height: 100vh; background: var(--surface-2, #ece7ee); }
.hb-bar {
  position: sticky; top: 0; z-index: 10; display: flex; align-items: center; gap: 14px;
  padding: 12px 20px; background: var(--surface); border-bottom: 1px solid var(--border);
}
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

@page { size: A4 landscape; margin: 0; }
@media print {
  .hb { background: #fff; }
  .hb-bar { display: none; }
  .hb-pages { gap: 0; padding: 0; }
  .hb-page { width: 297mm; box-shadow: none; border-radius: 0; }
}
</style>
