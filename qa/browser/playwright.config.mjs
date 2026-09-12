import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const runDir = process.env.M9_RUN_DIR || path.join(here, '.m9-runs', 'manual');

export default defineConfig({
  testDir: path.join(here, 'tests'),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  outputDir: path.join(runDir, 'test-results'),
  reporter: [['line'], ['html', { outputFolder: path.join(runDir, 'playwright-report'), open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:8765',
    locale: 'es-ES',
    timezoneId: 'Europe/Madrid',
    deviceScaleFactor: 1,
    trace: 'on',
    screenshot: 'off',
    video: 'off'
  },
  webServer: {
    command: 'python webapp/server.py --host 127.0.0.1 --port 8765',
    cwd: root,
    url: 'http://127.0.0.1:8765/api/config',
    reuseExistingServer: false,
    timeout: 30_000
  },
  projects: [
    { name: 'desktop-1440x900', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile-390x844', use: { viewport: { width: 390, height: 844 } } },
    { name: 'mobile-360x800', use: { viewport: { width: 360, height: 800 } } }
  ]
});
