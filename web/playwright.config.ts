import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './tests', timeout: 180000, expect: { timeout: 30000 }, use: { baseURL: process.env.E2E_URL || 'http://localhost:3000', trace: 'retain-on-failure', screenshot: 'only-on-failure' }, reporter: [['list'], ['html', { open: 'never' }]], workers: 1 });
