/**
 * Step 1 resilience tests — no manual devtools clicking, no real backend/AI
 * calls. Every `/new-project/*` request is intercepted at the network layer
 * so each failure mode (drop, hang, backend error, slow) is deterministic.
 *
 * These encode the DESIRED behavior, not just current behavior — some are
 * expected to fail until the corresponding fix lands (see the comment on
 * each test). Run with: npx playwright test
 */
import { test, expect, type Page } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const FIXTURE_IMAGE = `${__dirname}fixtures/tiny.png`

const EXTRACTED_FIELDS = {
  hairstyle: '黑长直发', face_makeup: '略带害羞的表情', upper_body: '水手服上衣',
  lower_body: '格纹短裙', shoes: '黑色乐福鞋', proportions: '中等身高',
  distinctive: '贝斯乐器', color_palette: '黑白蓝配色',
}

function analyzeDoneBody(sessionId = 'test-session-1') {
  return {
    session_id: sessionId,
    done: true,
    gender: 'female',
    message: '',
    visual_spec: { zh: '测试角色外观描述', en: 'test appearance', ja: 'テスト外見' },
    extracted: EXTRACTED_FIELDS,
    extracted_i18n: { zh: EXTRACTED_FIELDS, en: EXTRACTED_FIELDS, ja: EXTRACTED_FIELDS },
    missing_fields: [],
  }
}

function guessReplyBody() {
  return { reply: '我仔细看了看，这个角色好像是测试角色，对吗？', profile: null, awaiting_confirm: true }
}

// A first-turn chat reply that already carries a built profile — shortcuts the
// confirm→build round trip so a test can reach Step 2 with a `personality` set.
function profileReplyBody() {
  return {
    reply: '（built）',
    awaiting_confirm: false,
    profile: {
      character: '秋山澪',
      series: '轻音少女',
      worldSetting: {
        genre: '', era: '', timeline: '',
        tone: { visual: '', narrative: '', emotion: '' },
        synopsis: '', themes: [], iconic_settings: [],
      },
      characterBackground: {
        role: '', age: '', backstory: '',
        personality: { surface: '', inner: '', strength: '', weakness: '', core_desire: '', fear: '' },
        emotional_range: { baseline: '', stress: '', breaking_point: '', recovery: '' },
        behavior: {
          speech_style: { tone: '', volume: '', humor: '', vocabulary: '' },
          habits: [], values: [], likes: [], dislikes: [],
        },
        key_events: [], iconic_moments: [], relations: [],
      },
    },
  }
}

async function gotoStep1(page: Page) {
  await page.context().addCookies([
    { name: 'refimg_token', value: 'test-token', url: 'http://localhost:3000' },
  ])
  await page.goto('/projects/new')
  await page.waitForSelector('.add-card.big')
}

async function uploadImage(page: Page) {
  // The <input type=file> is display:none (opened via a styled dropzone), and
  // driving it directly with locator.setInputFiles() proved unreliable here
  // (files.length stayed 0, no change event). The filechooser-event pattern
  // is Playwright's documented approach for exactly this custom-UI case and
  // was reliable in testing.
  const [fileChooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    page.locator('.add-card.big').click(),
  ])
  await fileChooser.setFiles(FIXTURE_IMAGE)
}

// ── Image analysis phase ────────────────────────────────────────────────────

test('image analysis: network failure shows an error and clears the loading state', async ({ page }) => {
  await gotoStep1(page)
  await page.route('**/new-project/analyze-image', route => route.abort('failed'))

  await uploadImage(page)

  await expect(page.locator('.verify-error-inline')).toBeVisible({ timeout: 10_000 })
  await expect(page.locator('.scan-label')).toHaveCount(0)
})

test('image analysis: a request that never resolves should not hang the UI forever', async ({ page }) => {
  // No route.fulfill/abort — the request just stays pending, simulating a
  // hung backend or a silently dropped connection. The client-side timeout in
  // useApi.ts (REQUEST_TIMEOUT_MS, 90s) rescues it: the request aborts, the
  // catch surfaces an error, and loading clears. Allow room past the 90s cap.
  test.setTimeout(120_000)
  await gotoStep1(page)
  await page.route('**/new-project/analyze-image', () => {})

  await uploadImage(page)

  await expect(page.locator('.verify-error-inline')).toBeVisible({ timeout: 100_000 })
})

// ── Chat / identification phase ─────────────────────────────────────────────

test('chat kickoff: one transient failure recovers via the built-in auto-retry', async ({ page }) => {
  await gotoStep1(page)
  await page.route('**/new-project/analyze-image', route => route.fulfill({ json: analyzeDoneBody() }))
  let chatCalls = 0
  await page.route('**/new-project/chat', route => {
    chatCalls++
    if (chatCalls === 1) return route.abort('failed')
    return route.fulfill({ json: guessReplyBody() })
  })

  await uploadImage(page)

  await expect(page.getByText('测试角色')).toBeVisible({ timeout: 15_000 })
  expect(chatCalls).toBeGreaterThanOrEqual(2)
})

test('chat kickoff: persistent failure shows a retry action, and retrying recovers', async ({ page }) => {
  await gotoStep1(page)
  await page.route('**/new-project/analyze-image', route => route.fulfill({ json: analyzeDoneBody() }))
  let chatCalls = 0
  await page.route('**/new-project/chat', route => {
    chatCalls++
    if (chatCalls <= 3) return route.abort('failed') // beyond the single built-in auto-retry
    return route.fulfill({ json: guessReplyBody() })
  })

  await uploadImage(page)

  const retryBtn = page.locator('.retry-btn')
  await expect(retryBtn).toBeVisible({ timeout: 15_000 })
  await retryBtn.click()

  await expect(page.getByText('测试角色')).toBeVisible({ timeout: 15_000 })
})

test('chat kickoff: a request that never resolves should not hang the UI forever', async ({ page }) => {
  // Same hung-request scenario as the image-analysis test above, but for the
  // identification call — the 90s client timeout aborts it and surfaces a
  // retry action instead of a permanently-stuck typing indicator.
  test.setTimeout(120_000)
  await gotoStep1(page)
  await page.route('**/new-project/analyze-image', route => route.fulfill({ json: analyzeDoneBody() }))
  await page.route('**/new-project/chat', () => {})

  await uploadImage(page)

  await expect(page.locator('.retry-btn')).toBeVisible({ timeout: 100_000 })
})

test('chat kickoff: a backend/AI error should read differently from a plain network error', async ({ page }) => {
  // Currently every failure — dropped connection or a real 500 from the AI
  // provider — collapses into the same "网络错误，请重试" text. A backend/AI
  // failure should say something that doesn't imply "check your own network."
  // Expected to fail until the two are distinguished.
  await gotoStep1(page)
  await page.route('**/new-project/analyze-image', route => route.fulfill({ json: analyzeDoneBody() }))
  await page.route('**/new-project/chat', route =>
    route.fulfill({ status: 500, json: { detail: 'AI 服务出错了' } }))

  await uploadImage(page)

  await expect(page.locator('.retry-btn')).toBeVisible({ timeout: 15_000 })
  const bubbleText = await page.locator('.assistant-bubble').innerText()
  expect(bubbleText).not.toContain('网络');
})

test('chat kickoff: a slow-but-working request eventually completes normally', async ({ page }) => {
  await gotoStep1(page)
  await page.route('**/new-project/analyze-image', route => route.fulfill({ json: analyzeDoneBody() }))
  await page.route('**/new-project/chat', async route => {
    await new Promise(r => setTimeout(r, 6000))
    await route.fulfill({ json: guessReplyBody() })
  })

  await uploadImage(page)

  await expect(page.getByText('我在辨认这是哪位角色')).toBeVisible()
  await expect(page.getByText('测试角色')).toBeVisible({ timeout: 15_000 })
})

// ── Auth expiry ─────────────────────────────────────────────────────────────

test('mid-session 401 redirects to login with an explanation, not a silent bounce', async ({ page }) => {
  await gotoStep1(page)
  // Token gets rejected mid-flow (expired/revoked server-side).
  await page.route('**/new-project/analyze-image', route =>
    route.fulfill({ status: 401, json: { detail: 'Token 无效' } }))

  await uploadImage(page)

  await expect(page).toHaveURL(/\/login\?expired=1/, { timeout: 15_000 })
  await expect(page.getByText('登录已失效，请重新输入 Token 登录。')).toBeVisible()
})

// ── Step 2: project creation ────────────────────────────────────────────────

test('create project: a backend failure reads as a server error and re-enables the button', async ({ page }) => {
  // Drive the whole way to Step 2 with a built profile, then fail /create with a
  // 500. The status line must use the server-flavoured copy (not the network
  // one, and never raw backend text), and the create button must become
  // clickable again so the user can retry.
  await gotoStep1(page)
  await page.route('**/new-project/analyze-image', route => route.fulfill({ json: analyzeDoneBody() }))
  await page.route('**/new-project/chat', route => route.fulfill({ json: profileReplyBody() }))
  await page.route('**/projects/create', route =>
    route.fulfill({ status: 500, body: 'Traceback (most recent call last): RuntimeError: boom' }))

  await uploadImage(page)

  // Profile built on the first chat turn → the "next step" chip appears.
  const nextBtn = page.getByRole('button', { name: '好嘞，去看看' })
  await expect(nextBtn).toBeVisible({ timeout: 15_000 })
  await nextBtn.click()

  const createBtn = page.locator('.finish-btn')
  await expect(createBtn).toBeVisible()
  await createBtn.click()

  // Wait for the status to flip from "saving…" to the server-error copy
  // (set synchronously to "saving" before the request, then replaced on catch).
  const status = page.locator('.project-status')
  await expect(status).toContainText('联系', { timeout: 15_000 })  // "contact the developer"
  const statusText = await status.innerText()
  expect(statusText).not.toContain('网络')          // not the network message
  expect(statusText).not.toContain('Traceback')      // no raw backend text leaked
  await expect(createBtn).toBeEnabled()              // retry is possible
})
