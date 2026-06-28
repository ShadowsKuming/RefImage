const { public: { apiBase: BASE } } = useRuntimeConfig()

async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const r = await fetch(BASE + path, opts)
  if (!r.ok) {
    const msg = await r.text().catch(() => r.statusText)
    throw new Error(msg)
  }
  return r.json()
}

export const useApi = () => {
  function createProject(params: {
    images: { file: File; url: string }[]
    extracted: Record<string, any>
    visualSpec: { zh: string; en: string; ja: string }
    world: Record<string, any>
    character: Record<string, any>
  }) {
    const fd = new FormData()
    params.images.forEach(img => fd.append('images', img.file, img.file.name))
    fd.append('extracted',   JSON.stringify(params.extracted))
    fd.append('visual_spec', JSON.stringify(params.visualSpec))  // multilang dict as JSON string
    fd.append('world',       JSON.stringify(params.world))
    fd.append('character',   JSON.stringify(params.character))
    return api<{ project_id: string; character: string; series: string; created_at: string }>(
      '/projects/create', { method: 'POST', body: fd },
    )
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

  function listProjects() {
    return api<any[]>('/home/')
  }

  async function exportProject(projectId: string): Promise<void> {
    const r = await fetch(`${BASE}/projects/${projectId}/export`)
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
  ): Promise<{ reply: string; brief: Record<string, any> | null }> {
    return api<{ reply: string; brief: Record<string, any> | null }>(`/projects/${projectId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history }),
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

  function shotChat(
    projectId: string,
    shotId: string,
    message: string,
  ): Promise<{ reply: string; generating: boolean }> {
    return api<{ reply: string; generating: boolean }>(
      `/projects/${projectId}/shots/${shotId}/chat`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      },
    )
  }

  function getShot(projectId: string, shotId: string): Promise<any> {
    return api<any>(`/projects/${projectId}/shots/${shotId}`)
  }

  async function saveImage(projectId: string, shotId: string, blob: Blob): Promise<void> {
    const fd = new FormData()
    fd.append('file', new File([blob], 'generated.png', { type: 'image/png' }))
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
    const r = await fetch(`${BASE}/projects/${projectId}/shots/${shotId}/guides/${guideType}`)
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
  ) {
    return api<{
      reply: string
      profile: {
        character: string
        series: string
        worldSetting: { genre: string; era: string; themes: string[]; description: string }
        characterBackground: { role: string; age: string; coreTrait: string; description: string; relations: string[] }
      } | null
    }>('/new-project/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        history,
        visual_spec: visualSpec ?? null,
        current_profile: currentProfile ?? null,
      }),
    })
  }

  function verifyCharacter(file: File, sessionId: string) {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('session_id', sessionId)
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
      extracted: { zh: Record<string, string | null>; en: Record<string, string | null>; ja: Record<string, string | null> }
      missing_fields: string[]
    }>('/new-project/analyze-image', { method: 'POST', body: fd })
  }

  return {
    chat,
    verifyCharacter,
    analyzeImage,
    createProject,
    uploadReference,
    runExtract,
    runProfile,
    runScenes,
    getProject,
    listProjects,
    exportProject,
    importProject,
    projectChat,
    addExtraRef,
    createShot,
    deleteShot,
    shotChat,
    getShot,
    updateShotStatus,
    saveImage,
    getGuide,
    generateGuide,
  }
}
