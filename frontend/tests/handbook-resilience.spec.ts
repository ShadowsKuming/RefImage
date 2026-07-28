// Handbook (project PDF) resilience tests — no real backend. Every handbook
// request is intercepted so each state (ok / empty / failure / hang / 401) is
// deterministic. The handbook page is self-contained (it only calls
// getHandbook), which is exactly why it's a clean surface to pin: fault
// handling here must never leave a blank/crashed page.
//
// Run with: npm run build && npx playwright test handbook-resilience
import { test, expect, type Page } from '@playwright/test'

const PID = 'proj-1'
const ROUTE = '**localhost:8000/projects/' + PID + '/handbook'
const HB_URL = '/projects/' + PID + '/handbook'

function minimalPlan() {
  return {
    overview: { synopsis: '概述', goal: '目标', priority: 'mid', tags: ['校园'], constraints: [] },
    logistics: {
      scene: { location: '音乐教室', place: '教室', indoor_outdoor: '室内' },
      timing: { best_time: '午后', duration: '20 分钟', weather: '' },
      crew: { cosers: ['澪'], support: '' },
      props: { character: ['贝斯'], aux: [] },
      equipment: [{ name: '反光板', purpose: '补光' }],
    },
    technique: {
      params: { shot: '半身', angle: '平视', aspect: '横图', facing: '侧前', gaze: '看镜头', temp: '中性', mood: '适中', maincolor: '蓝' },
      expression: '害羞', pose_tips: ['坐姿'], composition: '三分', lighting: '窗光', risks: ['注意表情'], backup: '改走廊',
    },
  }
}

function handbookBody(overrides: Record<string, unknown> = {}) {
  return {
    project: {
      title: '秋山澪｜校园轻音', character: '秋山澪', series: '轻音少女',
      theme: '校园轻音', direction: '安静青春', shoot_date: '2026/08/15',
      cover_url: '', avatar_url: '',
    },
    summary: { shot_count: 1, scene_count: 1, duration_minutes: 20, costume_count: 1, tags: ['校园', '治愈'] },
    palette: ['#7fb3e0', '#efe7dc'],
    mood_images: [],
    schedule: [{ scene: '音乐教室', shot_ids: ['s01'], shots: 'S01', content: '贝斯练习', duration_minutes: 20, time: '' }],
    prep: { costumes: ['校服'], props: ['贝斯'], equipment: ['反光板'], locations: ['音乐教室'] },
    backups: [{ label: 'S01', title: '贝斯练习', backup: '改走廊', risks: ['注意表情'] }],
    pages: [{ shot_id: 's01', index: 1, title: '贝斯练习', completed: false, compiled_at: 't', plan: minimalPlan(), image_url: '' }],
    ...overrides,
  }
}

async function goHandbook(page: Page) {
  await page.context().addCookies([{ name: 'refimg_token', value: 'test-token', url: 'http://localhost:3000' }])
  await page.addInitScript(() => { window.print = () => {} })   // don't open a real print dialog
  await page.goto(HB_URL)
}

test('happy path: renders sections + shot pages, print enabled', async ({ page }) => {
  await page.route(ROUTE, route => route.fulfill({ json: handbookBody() }))
  await goHandbook(page)

  // cover + schedule/prep + visual? (no mood images, but palette present) + shot page + backup
  await expect(page.locator('.doc.cover')).toBeVisible()
  await expect(page.locator('.sc-table')).toBeVisible()          // schedule table
  await expect(page.locator('.prep-cols')).toBeVisible()         // prep checklist
  await expect(page.locator('.sheet')).toBeVisible()             // ShotSheet page
  await expect(page.locator('.bk-table')).toBeVisible()          // backup table

  const printBtn = page.locator('.hb-print')
  await expect(printBtn).toBeEnabled()
  await printBtn.click()                                          // must not throw / hang
})

test('empty: no compiled pages shows the empty state, not a blank page', async ({ page }) => {
  await page.route(ROUTE, route => route.fulfill({
    json: handbookBody({ pages: [], backups: [], schedule: [], mood_images: [], palette: [],
      prep: { costumes: [], props: [], equipment: [], locations: [] }, summary: { shot_count: 0, scene_count: 0, duration_minutes: 0, costume_count: 0, tags: [] } }),
  }))
  await goHandbook(page)

  await expect(page.locator('.hb-state')).toBeVisible()
  await expect(page.locator('.hb-print')).toBeDisabled()
})

test('load failure: an aborted request clears loading and shows a state (no crash)', async ({ page }) => {
  await page.route(ROUTE, route => route.abort('failed'))
  await goHandbook(page)

  // loading must resolve to the empty/error state, never hang on "加载中"
  await expect(page.locator('.hb-state')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.hb-print')).toBeDisabled()
})

test('hung request: the client timeout rescues the page', async ({ page }) => {
  test.setTimeout(120_000)
  await page.route(ROUTE, () => {})   // never resolves
  await goHandbook(page)
  await expect(page.locator('.hb-state')).toBeVisible({ timeout: 100_000 })
})

test('401: an expired session redirects to login', async ({ page }) => {
  await page.route(ROUTE, route => route.fulfill({ status: 401, json: { detail: 'Unauthorized' } }))
  await goHandbook(page)
  await expect(page).toHaveURL(/\/login\?expired=1/, { timeout: 10_000 })
})

test('partial data: missing optional sections still render what exists', async ({ page }) => {
  // only cover + one compiled page; no schedule/prep/visual/backup
  await page.route(ROUTE, route => route.fulfill({
    json: handbookBody({ schedule: [], backups: [], mood_images: [], palette: [],
      prep: { costumes: [], props: [], equipment: [], locations: [] } }),
  }))
  await goHandbook(page)

  await expect(page.locator('.doc.cover')).toBeVisible()
  await expect(page.locator('.sheet')).toBeVisible()
  await expect(page.locator('.sc-table')).toHaveCount(0)   // schedule section absent
  await expect(page.locator('.bk-table')).toHaveCount(0)   // backup section absent
})
