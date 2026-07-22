<template>
  <div class="home-page">
    <div class="home-content">
      <div class="logo-mark">⬡</div>
      <h1 class="home-title">RefImage</h1>
      <p class="home-subtitle">动漫角色真实摄影参考系统</p>
      <div class="action-row">
        <button class="new-project-btn" @click="onNewProject">+ 新建项目</button>
        <label class="import-btn" :class="{ loading: importing }">
          <input type="file" accept=".refimg" hidden @change="onImport" />
          {{ importing ? '导入中…' : '导入项目' }}
        </label>
      </div>

      <!-- Limit warning -->
      <div v-if="limitWarning" class="limit-banner">
        <span>已达项目上限（{{ PROJECT_LIMIT }} 个）。请先导出并删除旧项目，再新建。</span>
        <button class="limit-dismiss" @click="limitWarning = false">×</button>
      </div>
      <div v-if="importError" class="import-error">{{ importError }}</div>

      <!-- Existing projects -->
      <div v-if="projects.length > 0" class="projects-list">
        <div class="projects-label">
          已有项目
          <span class="proj-count">{{ projects.length }} / {{ PROJECT_LIMIT }}</span>
        </div>
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
          <div class="pr-actions" @click.stop>
            <button
              class="pr-export-btn"
              title="导出备份"
              @click.stop="onExport(p.project_id)"
            >↓</button>
            <button
              class="pr-delete-btn"
              title="删除项目"
              @click.stop="confirmDelete(p)"
            >🗑</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirmation dialog -->
    <div v-if="deleteTarget" class="dialog-backdrop" @click.self="deleteTarget = null">
      <div class="dialog">
        <div class="dialog-title">删除项目「{{ deleteTarget.character }}」？</div>
        <div class="dialog-body">
          此操作不可恢复，项目数据将被永久删除。<br>
          建议先<button class="inline-link" @click="onExport(deleteTarget!.project_id)">导出备份</button>再删除。
        </div>
        <div class="dialog-footer">
          <button class="dialog-btn cancel" @click="deleteTarget = null">取消</button>
          <button class="dialog-btn danger" :disabled="deleting" @click="doDelete">
            {{ deleting ? '删除中…' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '~/composables/useApi'

definePageMeta({ ssr: false })

const PROJECT_LIMIT = 5   // mirror of backend config default

const api = useApi()
const projects    = ref<any[]>([])
const importing   = ref(false)
const importError = ref('')
const limitWarning = ref(false)
const deleteTarget = ref<any | null>(null)
const deleting     = ref(false)
const { public: { apiBase: BASE_URL } } = useRuntimeConfig()

onMounted(async () => {
  try {
    projects.value = await api.listProjects()
  } catch (e) {
    console.error('Failed to load projects', e)
  }
})

function onNewProject() {
  if (projects.value.length >= PROJECT_LIMIT) {
    limitWarning.value = true
    return
  }
  navigateTo('/projects/new')
}

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

async function onExport(projectId: string) {
  try {
    await api.exportProject(projectId)
  } catch (e) {
    console.error('export failed', e)
  }
}

function confirmDelete(p: any) {
  deleteTarget.value = p
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await api.deleteProject(deleteTarget.value.project_id)
    projects.value = projects.value.filter(p => p.project_id !== deleteTarget.value!.project_id)
    if (projects.value.length < PROJECT_LIMIT) limitWarning.value = false
    deleteTarget.value = null
  } catch (e: any) {
    console.error('delete failed', e)
  }
  deleting.value = false
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

/* Limit warning */
.limit-banner {
  width: 100%; padding: 10px 14px;
  background: #fff8e1; border: 1px solid #f0c040;
  border-radius: 8px; font-size: 12px; color: #7a5f00;
  display: flex; align-items: flex-start; gap: 8px;
}
.limit-dismiss {
  margin-left: auto; background: none; border: none;
  cursor: pointer; color: #7a5f00; font-size: 14px; line-height: 1; flex-shrink: 0;
}

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
  display: flex; align-items: center; justify-content: space-between;
}
.proj-count { font-size: 10px; color: var(--text-ghost); font-weight: 400; letter-spacing: 0; }

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

.pr-actions { display: flex; gap: 4px; flex-shrink: 0; }
.pr-export-btn, .pr-delete-btn {
  width: 28px; height: 28px; border-radius: 6px; border: 1px solid var(--border-md);
  background: var(--surface); cursor: pointer; display: flex; align-items: center;
  justify-content: center; font-size: 13px; color: var(--text-muted);
  transition: border-color .15s, color .15s, background .15s;
  opacity: 0;
}
.project-row:hover .pr-export-btn,
.project-row:hover .pr-delete-btn { opacity: 1; }
.pr-export-btn:hover { border-color: var(--accent); color: var(--accent); }
.pr-delete-btn:hover { border-color: #e55; color: #e55; background: #fff0f0; }

/* Delete dialog */
.dialog-backdrop {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(0,0,0,.45);
  display: flex; align-items: center; justify-content: center;
}
.dialog {
  background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 14px; padding: 28px; min-width: 300px; max-width: 380px;
  display: flex; flex-direction: column; gap: 14px;
  box-shadow: 0 8px 32px rgba(0,0,0,.22);
}
.dialog-title { font-size: 15px; font-weight: 700; color: var(--text-hi, var(--text)); }
.dialog-body  { font-size: 13px; color: var(--text-muted); line-height: 1.6; }
.inline-link {
  background: none; border: none; color: var(--accent);
  cursor: pointer; padding: 0; font-size: 13px; text-decoration: underline;
}
.dialog-footer { display: flex; gap: 8px; justify-content: flex-end; }
.dialog-btn {
  padding: 8px 18px; border-radius: 8px; font-size: 13px;
  font-weight: 600; cursor: pointer; border: none;
  transition: background .15s, opacity .15s;
}
.dialog-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.dialog-btn.cancel { background: var(--surface-2, var(--border)); color: var(--text); }
.dialog-btn.cancel:hover { background: var(--border-md); }
.dialog-btn.danger { background: #e55; color: white; }
.dialog-btn.danger:hover { background: #c33; }
</style>
