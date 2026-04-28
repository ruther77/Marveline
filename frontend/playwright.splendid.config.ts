import { defineConfig, devices } from '@playwright/test'

/**
 * Configuration Playwright dédiée à la démo Splendid Events.
 *
 * Cible : tenant `lesplendid` via ngrok public URL (le frontend-splendid
 * container n'expose pas de port host direct, le reverse-proxy local
 * route par hostname Marveline/Massacorp uniquement).
 *
 * Usage :
 *   npx playwright test --config=playwright.splendid.config.ts
 *   npx playwright test --config=playwright.splendid.config.ts --headed
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/demo-splendid-desktop.spec.ts',

  // Durée max : 5 minutes (parcours bout en bout 8 articles + litige)
  timeout: 5 * 60 * 1000,

  retries: 0,
  workers: 1,

  use: {
    // Reverse-proxy local sur :3000 route /splendid/ vers frontend-splendid:80.
    // Slash final OBLIGATOIRE pour que les paths relatifs concatènent correctement.
    baseURL: 'http://localhost:3000/splendid/',

    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,

    // 600ms entre actions = oeil humain qui suit confortablement
    slowMo: 600,
    video: {
      mode: 'on',
      size: { width: 1440, height: 900 },
    },
    screenshot: 'on',
    locale: 'fr-FR',

    extraHTTPHeaders: {
      'Accept-Language': 'fr-FR,fr;q=0.9',
    },
  },

  outputDir: 'demo-output/',

  reporter: [
    ['html', { outputFolder: 'demo-output/report-splendid', open: 'never' }],
    ['list'],
  ],

  projects: [
    {
      name: 'demo-splendid-desktop',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
      },
    },
  ],
})
