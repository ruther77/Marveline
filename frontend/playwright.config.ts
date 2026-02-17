import { defineConfig, devices } from '@playwright/test'

/**
 * Configuration Playwright pour tests E2E CaroCorp_new (Marveline)
 *
 * Tests couvrent :
 * - CSRF flow (auto-fetch, retry, renewal)
 * - MFA flow (setup, enable, verify, disable)
 * - Session management (creation, expiration, refresh, logout)
 */
export default defineConfig({
  testDir: './tests/e2e',

  // Timeout pour chaque test (30s par défaut)
  timeout: 30 * 1000,

  // Nombre de retries en cas d'échec
  retries: process.env.CI ? 2 : 0,

  // Workers : parallélisation des tests
  workers: process.env.CI ? 1 : undefined,

  // Reporter : format de sortie des résultats
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list']
  ],

  // Options globales pour tous les tests
  use: {
    // Base URL de l'application frontend
    // 3003 en mode dev, 3002 en mode prod
    baseURL: process.env.FRONTEND_PORT ? `http://localhost:${process.env.FRONTEND_PORT}` : 'http://localhost:3002',

    // Capture screenshot uniquement sur échec
    screenshot: 'only-on-failure',

    // Capture vidéo uniquement sur échec
    video: 'retain-on-failure',

    // Trace pour debugging (off par défaut, on-first-retry en CI)
    trace: process.env.CI ? 'on-first-retry' : 'off',

    // Headers globaux (peuvent être overridés par test)
    extraHTTPHeaders: {
      'Accept-Language': 'fr-FR',
    },
  },

  // Configuration des projets (browsers à tester)
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    // Décommenter pour tester sur Firefox et Safari
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },

    // Tests mobile (décommenter si nécessaire)
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: { ...devices['iPhone 12'] },
    // },
  ],

  // Web server : désactivé car on utilise docker compose
  // webServer: {
  //   command: 'npm run dev',
  //   url: 'http://localhost:3002',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120 * 1000, // 2 minutes pour démarrer
  //   stdout: 'ignore',
  //   stderr: 'pipe',
  // },
})
