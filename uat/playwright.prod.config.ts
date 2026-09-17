import { defineConfig, devices } from '@playwright/test';

/**
 * Production data-entry profile for https://okr.aipower.vn.
 *
 * This is not the sign-off profile in playwright.config.ts. That one resets
 * and seeds a throwaway UAT database before every run; pointed at production
 * it would destroy a customer's data. Here there is no global setup at all,
 * and every spec re-checks which database it is talking to before it acts.
 *
 * Specs are numbered and run in order: the organisation must exist before
 * users can be attached to it, and cycles before objectives. Each spec looks
 * before it writes, so running the whole profile again changes nothing.
 */
export default defineConfig({
  testDir: './specs/prod',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60 * 60_000,
  expect: { timeout: 20_000 },
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report-prod', open: 'never' }],
    ['json', { outputFile: 'test-results/prod-results.json' }],
  ],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.PROD_URL ?? 'https://okr.aipower.vn',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
    locale: 'vi-VN',
    timezoneId: 'Asia/Ho_Chi_Minh',
  },
  outputDir: 'test-results/prod',
});
