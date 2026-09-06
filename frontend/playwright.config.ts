import { defineConfig, devices } from '@playwright/test'

// End-to-end config (scaffold-frontend-testing skill). E2E is the CROWN of the
// pyramid, not the whole net: keep these few and high-value. Traces/screenshots are
// captured on first retry only and land in .data/test_artifacts/ (AGENTS 5.7).
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  // Fail the CI run if a test.only was committed by accident.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { outputFolder: '../.data/test_artifacts/playwright-report', open: 'never' }]],
  outputDir: '../.data/test_artifacts/playwright-artifacts',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  // Boot the dev server for the run; reuse an already-running one locally.
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
