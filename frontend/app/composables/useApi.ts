// Typed error so callers can tell a dropped connection / timeout (retry-worthy,
// "check your network") apart from a real backend/AI failure (a 4xx/5xx —
// "the service is having trouble, contact us"). `retryable` is honored by
// withRetry(): only a fast network blip is auto-retried; a 90s timeout or a
// deterministic server error is not (the user still gets a manual retry button).
export class ApiError extends Error {
  kind: 'network' | 'timeout' | 'server'
  status?: number
  constructor(kind: 'network' | 'timeout' | 'server', message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind
    this.status = status
  }
  get retryable(): boolean { return this.kind === 'network' }
}

// Hard ceiling on any single request. The identification/build calls legitimately
// run tens of seconds (multiple web searches), so this is generous — it only
// exists to rescue a truly hung request that would otherwise freeze the UI's
// loading state forever.
const REQUEST_TIMEOUT_MS = 90_000

export const useApi = () => {
  const { public: { apiBase: BASE } } = useRuntimeConfig()
  const { token, clearToken } = useAuth()

  function _authHeader(): Record<string, string> {
    return token.value ? { Authorization: `Bearer ${token.value}` } : {}
  }

  async function _fetchAuth(input: string, init: RequestInit = {}): Promise<Response> {
    const headers = { ..._authHeader(), ...(init.headers as Record<string, string> ?? {}) }
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
    let r: Response
    try {
      r = await fetch(input, { ...init, headers, signal: controller.signal })
    } catch (e) {
      // AbortController fired → timeout; any other rejection → network-level failure.
      if (controller.signal.aborted) throw new ApiError('timeout', 'Request timed out')
      throw new ApiError('network', (e as Error).message)
    } finally {
      clearTimeout(timer)
    }
    if (r.status === 401) {
      // Token was rejected mid-session (expired/revoked). Clear it and send the
      // user to login with a flag so the page can explain why they're back here,
      // instead of a silent bounce that looks like the app lost their work.
      clearToken()
      await navigateTo('/login?expired=1')
      throw new ApiError('server', 'Unauthorized', 401)
    }
    return r
  }

  async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
    const r = await _fetchAuth(BASE + path, opts)
    if (!r.ok) {
      const msg = await r.text().catch(() => r.statusText)
      throw new ApiError('server', msg, r.status)
    }
    return r.json()
  }

  function createProject(params: {
    images: { file: File; url: string }[]
    extractedI18n: { zh: Record<string, string | null>; en: Record<string, string | null>; ja: Record<string, string | null> }
    visualSpec: { zh: string; en: string; ja: string }
    world: Record<string, any>
    character: Record<string, any>
  }) {
    const fd = new FormData()
    params.images.forEach(img => fd.append('images', img.file, img.file.name))
    fd.append('extracted_i18n', JSON.stringify(params.extractedI18n))
    fd.append('visual_spec',    JSON.stringify(params.visualSpec))  // multilang dict as JSON string
    fd.append('world',          JSON.stringify(params.world))
    fd.append('character',      JSON.stringify(params.character))
    return api<{ project_id: string; character: string; series: string; created_at: string }>(
      '/projects/create', { method: 'POST', body: fd },
    )
  }

  function deleteProject(projectId: string) {
    return api<{ ok: boolean }>(`/projects/${projectId}`, { method: 'DELETE' })
  }

  function uploadReference(projectId: string, file: File) {
    const fd = new FormData()
    fd.append('file', file)
    return api<{ ok: boolean }>(`/projects/${projectId}/reference`, { method: 'POST', body: fd })
  }

  function runExtract(projectId: string) {
    return api<{ ok: boolean; visual_spec: string }>(`/pipeline/${projectId}/extract`, { method: 'POST' })
  }

  function runProfile(projectId: string) {
    return api<{ ok: boolean; profile: string }>(`/pipeline/${projectId}/profile`, { method: 'POST' })
  }

  function runScenes(projectId: string) {
    return api<{ scenes: any[]; raw: string }>(`/pipeline/${projectId}/scenes`, { method: 'POST' })
  }

  function getProject(projectId: string) {
    return api<any>(`/projects/${projectId}`)
  }

  function savePlanData(projectId: string, data: Record<string, any>) {
    return api<{ ok: boolean }>(`/projects/${projectId}/plan`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data }),
    })
  }

  function saveWardrobe(projectId: string, data: Record<string, any>) {
    return api<{ ok: boolean }>(`/projects/${projectId}/wardrobe`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data }),
    })
  }

  function grabCover(projectId: string) {
    return api<{ url: string; source: string; title: string }>(
      `/projects/${projectId}/cover/grab`, { method: 'POST' },
    )
  }

  function uploadCover(projectId: string, file: File) {
    const fd = new FormData()
    fd.append('image', file, file.name)
    return api<{ url: string }>(`/projects/${projectId}/cover`, { method: 'POST', body: fd })
  }

  function uploadAvatarSource(projectId: string, cid: string, file: File) {
    const fd = new FormData()
    fd.append('image', file, file.name)
    return api<{ src_url: string }>(`/projects/${projectId}/characters/${cid}/avatar`, { method: 'POST', body: fd })
  }

  function cropAvatar(projectId: string, cid: string, rect: { x: number; y: number; size: number }) {
    return api<{ avatar_url: string }>(`/projects/${projectId}/characters/${cid}/avatar/crop`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rect),
    })
  }

  function autoAvatarCrop(projectId: string, cid: string) {
    return api<{ x: number; y: number; size: number }>(`/projects/${projectId}/characters/${cid}/avatar/auto`, { method: 'POST' })
  }

  function listProjects() {
    return api<any[]>('/home/')
  }

  async function exportProject(projectId: string): Promise<void> {
    const r = await _fetchAuth(`${BASE}/projects/${projectId}/export`)
    if (!r.ok) throw new Error(await r.text())
    const blob = await r.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${projectId}.refimg`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function importProject(file: File): Promise<{ project_id: string; character: string; series: string }> {
    const fd = new FormData()
    fd.append('file', file)
    return api<any>('/home/import', { method: 'POST', body: fd })
  }

  function projectChat(
    projectId: string,
    message: string,
    history: { role: string; text: string }[],
  ): Promise<{ reply: string; brief: Record<string, any> | null; plan: Record<string, any> | null }> {
    return api<{ reply: string; brief: Record<string, any> | null; plan: Record<string, any> | null }>(`/projects/${projectId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history, reply_lang: useLocale().locale.value }),
    })
  }

  async function addExtraRef(projectId: string, file: File): Promise<{ url: string }> {
    const fd = new FormData()
    fd.append('image', file)
    return api<{ url: string }>(`/projects/${projectId}/extra-refs`, { method: 'POST', body: fd })
  }

  function createShot(projectId: string, title: string, mood: string, desc = '') {
    return api<any>(`/projects/${projectId}/shots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, mood, scene_description: desc }),
    })
  }

  function deleteShot(projectId: string, shotId: string) {
    return api<{ ok: boolean }>(`/projects/${projectId}/shots/${shotId}`, { method: 'DELETE' })
  }

  function updateShotTitle(projectId: string, shotId: string, title: string) {
    return api<{ ok: boolean }>(`/projects/${projectId}/shots/${shotId}/title`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    })
  }

  function shotChat(
    projectId: string,
    shotId: string,
    message: string,
    selectedVersionIds: string[] = [],
    selectedRefIds: string[] = [],
  ): Promise<{ reply: string; generating: boolean }> {
    return api<{ reply: string; generating: boolean }>(
      `/projects/${projectId}/shots/${shotId}/chat`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          selected_version_ids: selectedVersionIds,
          selected_ref_ids: selectedRefIds,
        }),
      },
    )
  }

  function uploadShotRef(projectId: string, shotId: string, file: File) {
    const fd = new FormData()
    fd.append('image', file, file.name)
    return api<{ id: string; type: null; status: string; created_at: string }>(
      `/projects/${projectId}/shots/${shotId}/refs`,
      { method: 'POST', body: fd },
    )
  }

  function listShotRefs(projectId: string, shotId: string) {
    return api<Array<{
      id: string; type: string | null; status: string; created_at: string
      original_url: string; processed_url?: string | null; processed_text?: string
    }>>(`/projects/${projectId}/shots/${shotId}/refs`)
  }

  function deleteShotRef(projectId: string, shotId: string, refId: string) {
    return api<{ ok: boolean }>(
      `/projects/${projectId}/shots/${shotId}/refs/${refId}`,
      { method: 'DELETE' },
    )
  }

  function listVersions(projectId: string, shotId: string) {
    return api<Array<{
      id: string; parent_ids: string[]; prompt: string; created_at: string; image_url: string | null
    }>>(`/projects/${projectId}/shots/${shotId}/versions`)
  }

  function deleteVersion(projectId: string, shotId: string, versionId: string) {
    return api<{ ok: boolean }>(`/projects/${projectId}/shots/${shotId}/versions/${versionId}`, { method: 'DELETE' })
  }

  function activateVersion(projectId: string, shotId: string, versionId: string) {
    return api<{ ok: boolean }>(`/projects/${projectId}/shots/${shotId}/versions/${versionId}/activate`, { method: 'PATCH' })
  }

  function getShot(projectId: string, shotId: string): Promise<any> {
    return api<any>(`/projects/${projectId}/shots/${shotId}`)
  }

  async function saveImage(
    projectId: string,
    shotId: string,
    blob: Blob,
    parentVersionId?: string,   // omit for fresh uploads (root node); pass for crop saves (child)
  ): Promise<void> {
    const fd = new FormData()
    fd.append('file', new File([blob], 'generated.png', { type: 'image/png' }))
    if (parentVersionId) fd.append('parent_version_id', parentVersionId)
    await api<{ ok: boolean }>(`/projects/${projectId}/shots/${shotId}/image`, {
      method: 'PUT',
      body: fd,
    })
  }

  function updateShotStatus(projectId: string, shotId: string, status: string) {
    return api<{ ok: boolean }>(`/projects/${projectId}/shots/${shotId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
  }

  async function getGuide(projectId: string, shotId: string, guideType: string) {
    const r = await _fetchAuth(`${BASE}/projects/${projectId}/shots/${shotId}/guides/${guideType}`)
    if (r.status === 404) return null
    if (!r.ok) throw new Error(await r.text())
    return r.json() as Promise<{ guide: any; sketch_url: string | null }>
  }

  function generateGuide(projectId: string, shotId: string, guideType: string) {
    return api<{ guide: any; sketch_url: string }>(`/projects/${projectId}/shots/${shotId}/guides/${guideType}`, { method: 'POST' })
  }

  function chat(
    message: string,
    history: { role: 'user' | 'assistant'; content: string }[],
    visualSpec?: string | null,
    currentProfile?: object | null,
    sessionId?: string | null,
  ) {
    return api<{
      reply: string
      profile: {
        character: string
        series: string
        worldSetting: { genre: string; era: string; themes: string[]; description: string }
        characterBackground: { role: string; age: string; coreTrait: string; description: string; relations: string[] }
      } | null
      awaiting_confirm: boolean
    }>('/new-project/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        history,
        visual_spec: visualSpec ?? null,
        current_profile: currentProfile ?? null,
        session_id: sessionId ?? null,
        reply_lang: useLocale().locale.value,
      }),
    })
  }

  function verifyCharacter(file: File, sessionId: string) {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('session_id', sessionId)
    fd.append('reply_lang', useLocale().locale.value)
    return api<{ same: boolean; reason: string }>('/new-project/verify-character', { method: 'POST', body: fd })
  }

  function analyzeImage(file: File, sessionId: string | null = null) {
    const fd = new FormData()
    fd.append('file', file)
    if (sessionId) fd.append('session_id', sessionId)
    return api<{
      session_id: string
      done: boolean
      gender: 'male' | 'female'
      message: string
      visual_spec: { zh: string; en: string; ja: string } | null
      extracted: Record<string, string | null>
      extracted_i18n: { zh: Record<string, string | null>; en: Record<string, string | null>; ja: Record<string, string | null> } | null
      missing_fields: string[]
    }>('/new-project/analyze-image', { method: 'POST', body: fd })
  }

  return {
    chat,
    verifyCharacter,
    deleteProject,
    analyzeImage,
    createProject,
    uploadReference,
    runExtract,
    runProfile,
    runScenes,
    getProject,
    listProjects,
    savePlanData,
    saveWardrobe,
    grabCover,
    uploadCover,
    uploadAvatarSource,
    cropAvatar,
    autoAvatarCrop,
    exportProject,
    importProject,
    projectChat,
    addExtraRef,
    createShot,
    deleteShot,
    updateShotTitle,
    shotChat,
    listVersions,
    deleteVersion,
    activateVersion,
    getShot,
    updateShotStatus,
    saveImage,
    getGuide,
    generateGuide,
    uploadShotRef,
    listShotRefs,
    deleteShotRef,
  }
}
