import { webUrl } from './e2e/urls'
import { defineConfig, devices } from '@playwright/test'

const inCi = Boolean(process.env.CI)
const localWindowsFirefoxHeaded = process.platform === 'win32'
  && !inCi
  && process.env.QUANTUMLEARN_FIREFOX_HEADLESS !== '1'

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.e2e.ts',
  outputDir: 'test-results/playwright',
  fullyParallel: false,
  forbidOnly: inCi,
  retries: inCi ? 2 : 0,
  workers: 1,
  reporter: inCi ? [['github'], ['list']] : 'list',
  use: {
    baseURL: webUrl,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    contextOptions: { reducedMotion: 'reduce' },
  },
  projects: [
    {
      name: 'chrome-stable',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome',
      },
    },
    {
      name: 'edge-stable',
      use: {
        ...devices['Desktop Edge'],
        channel: 'msedge',
      },
    },
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        headless: !localWindowsFirefoxHeaded,
      },
    },
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
      },
    },
  ],
})
