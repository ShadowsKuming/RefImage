import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  fullyParallel: true,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'retain-on-failure',
  },
  // Runs against the production build, not `npm run dev` — the dev server's
  // HMR/vite-client overhead was causing flaky setInputFiles/change-event
  // timing (see session notes). A built server is deterministic and closer
  // to what actually ships.
  webServer: {
    command: 'node .output/server/index.mjs',
    url: 'http://localhost:3000',
    reuseExistingServer: false,
    timeout: 30_000,
    env: { PORT: '3000' },
  },
})
