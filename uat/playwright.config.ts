import { defineConfig, devices } from '@playwright/test';

/**
 * Sign-off profile.
 *
 * `retries: 0` is the important line. A test that passes on the second
 * attempt has told you the product is unreliable, and counting it as a pass
 * throws that information away. Flake gets reported as flake, not laundered.
 *
 * One worker, because every spec talks to one Odoo instance holding one
 * shared dataset; parallel workers would be testing each other's leftovers.
 */
export default defineConfig({
  testDir: './specs',
  globalSetup: './global-setup.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['json', { outputFile: 'test-results/results.json' }],
  ],
  use: {
    baseURL: process.env.UAT_URL ?? 'http://127.0.0.1:8075',
    trace: 'on',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 20_000,
    navigationTimeout: 45_000,
    locale: 'en-US',
    timezoneId: 'Asia/Ho_Chi_Minh',
  },
  projects: [
    {
      name: 'api',
      testMatch: /specs[\\/]api[\\/].*\.spec\.ts/,
    },
    {
      name: 'web',
      testMatch: /specs[\\/]web[\\/].*\.spec\.ts/,
      testIgnore: /responsive\.spec\.ts/,
      dependencies: ['api'],
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      // The user directive is explicit: every custom screen must work on a
      // phone. 320px is the narrowest device still in real use.
      name: 'responsive',
      testMatch: /specs[\\/]web[\\/]responsive\.spec\.ts/,
      dependencies: ['api'],
      use: { ...devices['Desktop Chrome'], viewport: { width: 320, height: 720 } },
    },
  ],
});
