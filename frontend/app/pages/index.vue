<template>
  <div class="home-page">
    <div class="home-content">
      <div class="logo-mark">⬡</div>
      <h1 class="home-title">RefImage</h1>
      <p class="home-subtitle">动漫角色真实摄影参考系统</p>
      <div class="action-row">
        <button class="new-project-btn" @click="navigateTo('/projects/new')">+ 新建项目</button>
        <label class="import-btn" :class="{ loading: importing }">
          <input type="file" accept=".refimg" hidden @change="onImport" />
          {{ importing ? '导入中…' : '导入项目' }}
        </label>
      </div>
      <div v-if="importError" class="import-error">{{ importError }}</div>

      <!-- Existing projects -->
      <div v-if="projects.length > 0" class="projects-list">
        <div class="projects-label">已有项目</div>
        <div
          v-for="p in projects"
          :key="p.project_id"
          class="project-row"
          @click="navigateTo(`/projects/${p.project_id}`)"
        >
          <div class="pr-thumb-wrap">
            <img v-if="p.ref_thumb" :src="BASE_URL + p.ref_thumb" class="pr-thumb" :alt="p.character" />
            <span v-else class="pr-thumb-empty">⬡</span>
          </div>
          <div class="pr-info">
            <span class="pr-name">{{ p.character }}</span>
            <span class="pr-meta">{{ p.series }}{{ p.shot_count ? ' · ' + p.shot_count + ' 个拍摄' : '' }}</span>
          </div>
          <span class="pr-arrow">→</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '~/composables/useApi'

definePageMeta({ ssr: false })

const api = useApi()
const projects  = ref<any[]>([])
const importing = ref(false)
const importError = ref('')
const { public: { apiBase: BASE_URL } } = useRuntimeConfig()

onMounted(async () => {
  try {
    projects.value = await api.listProjects()
  } catch (e) {
    console.error('Failed to load projects', e)
  }
})

async function onImport(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  importing.value  = true
  importError.value = ''
  try {
    const result = await api.importProject(file)
    projects.value = await api.listProjects()
    navigateTo(`/projects/${result.project_id}`)
  } catch (err: any) {
    importError.value = err.message ?? '导入失败'
  }
  importing.value = false
  ;(e.target as HTMLInputElement).value = ''
}
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg, var(--bg));
}

.home-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  width: 100%;
  max-width: 400px;
  padding: 40px 24px;
}

.logo-mark {
  font-size: 48px;
  color: var(--accent);
  line-height: 1;
}

.home-title {
  font-size: 36px;
  font-weight: 700;
  color: var(--text-hi, var(--text));
  letter-spacing: -0.5px;
}

.home-subtitle {
  font-size: 14px;
  color: var(--text-quiet, var(--text-sub));
  margin-bottom: 8px;
}

.action-row {
  display: flex; gap: 10px; align-items: center;
}
.new-project-btn {
  padding: 12px 28px;
  background: var(--accent);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, transform 0.1s;
}
.new-project-btn:hover  { background: var(--accent-hover); }
.new-project-btn:active { transform: scale(0.98); }
.import-btn {
  padding: 12px 20px;
  background: var(--surface);
  border: 1px solid var(--border-md);
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s;
}
.import-btn:hover  { border-color: var(--accent); color: var(--accent); }
.import-btn.loading { opacity: 0.6; cursor: not-allowed; }
.import-error {
  font-size: 12px; color: var(--error);
  background: var(--surface); border: 1px solid var(--error);
  border-radius: 6px; padding: 8px 14px; width: 100%; text-align: center;
}

/* Projects list */
.projects-list {
  width: 100%;
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.projects-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-ghost, var(--text-ghost));
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 4px;
}
.project-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--surface, var(--surface));
  border: 1px solid var(--border, var(--border-md));
  border-radius: 10px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.project-row:hover { border-color: var(--accent); background: var(--surface-2, var(--surface-2)); }
.pr-thumb-wrap {
  width: 40px; height: 40px; flex-shrink: 0;
  border-radius: 8px; overflow: hidden;
  background: var(--surface-inset);
  display: flex; align-items: center; justify-content: center;
}
.pr-thumb       { width: 100%; height: 100%; object-fit: cover; display: block; }
.pr-thumb-empty { font-size: 16px; color: var(--accent); }
.pr-info  { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.pr-name  { font-size: 13px; font-weight: 600; color: var(--text-hi, var(--text)); }
.pr-meta  { font-size: 11px; color: var(--text-quiet, var(--text-sub)); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pr-arrow { font-size: 14px; color: var(--text-ghost, var(--text-ghost)); flex-shrink: 0; }
</style>
