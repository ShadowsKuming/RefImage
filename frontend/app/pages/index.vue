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
          <span class="pr-arrow">→</span>
          <!-- Delete button top-right -->
          <button class="pr-delete-btn" title="删除项目" @click.stop="confirmDelete(p)">×</button>
        </div>
      </div>
    </div>

    <!-- Limit dialog -->
    <div v-if="showLimitDialog" class="dialog-backdrop" @click.self="showLimitDialog = false">
      <div class="dialog">
        <div class="dialog-icon">⚠️</div>
        <div class="dialog-title">已达项目上限</div>
        <div class="dialog-body">
          每位用户最多保存 {{ PROJECT_LIMIT }} 个项目。<br>
          请进入旧项目导出备份后再删除，腾出空间新建。
        </div>
        <div class="dialog-footer">
          <button class="dialog-btn primary" @click="showLimitDialog = false">知道了</button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation dialog -->
    <div v-if="deleteTarget" class="dialog-backdrop" @click.self="deleteTarget = null">
      <div class="dialog">
        <div class="dialog-title">删除「{{ deleteTarget.character }}」？</div>
        <div class="dialog-body">
          项目数据将被永久删除，无法恢复。<br>
          如需保留，请先进入项目页面导出备份。
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

const PROJECT_LIMIT = 5

const api = useApi()
const projects       = ref<any[]>([])
const importing      = ref(false)
const importError    = ref('')
const showLimitDialog = ref(false)
const deleteTarget   = ref<any | null>(null)
const deleting       = ref(false)
const { public: { apiBase: BASE_URL } } = useRuntimeConfig()

onMounted(async () => {
  try { projects.value = await api.listProjects() }
  catch (e) { console.error('Failed to load projects', e) }
})

function playDing() {
  try {
    const ctx = new AudioContext()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain); gain.connect(ctx.destination)
    osc.type = 'sine'; osc.frequency.value = 880
    gain.gain.setValueAtTime(0.35, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6)
    osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.6)
  } catch {}
}

function onNewProject() {
  if (projects.value.length >= PROJECT_LIMIT) {
    showLimitDialog.value = true
    playDing()
    return
  }
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
  } catch (err: any) {
    importError.value = err.message ?? '导入失败'
  }
  importing.value = false
  ;(e.target as HTMLInputElement).value = ''
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
    deleteTarget.value = null
  } catch (e: any) { console.error('delete failed', e) }
  deleting.value = false
}
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg);
}
.home-content {
  display: flex; flex-direction: column; align-items: center;
  gap: 16px; width: 100%; max-width: 400px; padding: 40px 24px;
}
.logo-mark  { font-size: 48px; color: var(--accent); line-height: 1; }
.home-title { font-size: 36px; font-weight: 700; color: var(--text-hi, var(--text)); letter-spacing: -0.5px; }
.home-subtitle { font-size: 14px; color: var(--text-quiet, var(--text-sub)); margin-bottom: 8px; }

.action-row { display: flex; gap: 10px; align-items: center; }
.new-project-btn {
  padding: 12px 28px; background: var(--accent); border: none;
  border-radius: 8px; color: white; font-size: 15px; font-weight: 600;
  cursor: pointer; transition: background .2s, transform .1s;
}
.new-project-btn:hover  { background: var(--accent-hover); }
.new-project-btn:active { transform: scale(.98); }

.import-btn {
  padding: 12px 20px; background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 8px; color: var(--text-muted); font-size: 14px; font-weight: 500;
  cursor: pointer; transition: border-color .15s, color .15s;
}
.import-btn:hover  { border-color: var(--accent); color: var(--accent); }
.import-btn.loading { opacity: .6; cursor: not-allowed; }

.import-error {
  font-size: 12px; color: var(--error); background: var(--surface);
  border: 1px solid var(--error); border-radius: 6px;
  padding: 8px 14px; width: 100%; text-align: center;
}

/* Projects list */
.projects-list { width: 100%; margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
.projects-label {
  font-size: 10px; font-weight: 600; color: var(--text-ghost);
  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;
  display: flex; align-items: center; justify-content: space-between;
}
.proj-count { font-size: 10px; color: var(--text-ghost); font-weight: 400; letter-spacing: 0; }

.project-row {
  position: relative;
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  background: var(--surface); border: 1px solid var(--border, var(--border-md));
  border-radius: 10px; cursor: pointer;
  transition: border-color .15s, background .15s;
}
.project-row:hover { border-color: var(--accent); background: var(--surface-2); }

.pr-thumb-wrap {
  width: 40px; height: 40px; flex-shrink: 0; border-radius: 8px; overflow: hidden;
  background: var(--surface-inset); display: flex; align-items: center; justify-content: center;
}
.pr-thumb       { width: 100%; height: 100%; object-fit: cover; display: block; }
.pr-thumb-empty { font-size: 16px; color: var(--accent); }
.pr-info  { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.pr-name  { font-size: 13px; font-weight: 600; color: var(--text-hi, var(--text)); }
.pr-meta  { font-size: 11px; color: var(--text-quiet); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pr-arrow { font-size: 14px; color: var(--text-ghost); flex-shrink: 0; }

/* × delete button — inside card, top-right with margin */
.pr-delete-btn {
  position: absolute; top: 8px; right: 10px;
  width: 18px; height: 18px; border-radius: 4px;
  background: transparent; border: 1px solid var(--border-md);
  color: var(--border-md); font-size: 12px; line-height: 1;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; opacity: 0;
  transition: opacity .15s, background .15s, border-color .15s, color .15s;
}
.project-row:hover .pr-delete-btn { opacity: 1; }
.pr-delete-btn:hover { background: #fee; border-color: #e55; color: #e55; }

/* Dialog */
.dialog-backdrop {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(0,0,0,.45);
  display: flex; align-items: center; justify-content: center;
}
.dialog {
  background: var(--surface); border: 1px solid var(--border-md);
  border-radius: 14px; padding: 28px 28px 22px; min-width: 300px; max-width: 360px;
  display: flex; flex-direction: column; gap: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,.22);
}
.dialog-icon  { font-size: 28px; text-align: center; }
.dialog-title { font-size: 15px; font-weight: 700; color: var(--text-hi, var(--text)); text-align: center; }
.dialog-body  { font-size: 13px; color: var(--text-muted); line-height: 1.65; text-align: center; }
.dialog-footer { display: flex; gap: 8px; justify-content: center; margin-top: 4px; }
.dialog-btn {
  padding: 8px 22px; border-radius: 8px; font-size: 13px;
  font-weight: 600; cursor: pointer; border: none;
  transition: background .15s, opacity .15s;
}
.dialog-btn:disabled { opacity: .55; cursor: not-allowed; }
.dialog-btn.primary { background: var(--accent); color: white; }
.dialog-btn.primary:hover { background: var(--accent-hover); }
.dialog-btn.cancel { background: var(--surface-2, var(--border)); color: var(--text); }
.dialog-btn.cancel:hover { background: var(--border-md); }
.dialog-btn.danger { background: #e55; color: white; }
.dialog-btn.danger:hover { background: #c33; }
</style>
