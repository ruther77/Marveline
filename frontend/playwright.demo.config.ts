import { defineConfig, devices } from '@playwright/test'

/**
 * Configuration Playwright dédiée à la démo commerciale Marveline.
 *
 * Séparé de playwright.config.ts pour ne pas perturber les tests E2E existants.
 *
 * Usage :
 *   npx playwright test --config=playwright.demo.config.ts
 *   npx playwright test --config=playwright.demo.config.ts --headed  (visualisation live)
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/demo-marveline-mobile.spec.ts',

  // Durée max par test : 4 minutes (scénario 7 étapes avec pauses)
  timeout: 4 * 60 * 1000,

  // Pas de retry pour la démo (on veut un enregistrement propre)
  retries: 0,

  // 1 worker : enregistrement séquentiel
  workers: 1,

  use: {
    baseURL: 'http://localhost:3002',

    // iPhone 14 Pro : 393×852, Safari simulé (webkit)
    ...devices['iPhone 14 Pro'],

    // Lisibilité humaine : 500ms entre chaque action
    slowMo: 500,

    // Enregistrer TOUJOURS (même en cas de succès)
    video: 'on',

    // Screenshot à chaque étape clé
    screenshot: 'on',

    // Locale française
    locale: 'fr-FR',

    // Headers Accept-Language
    extraHTTPHeaders: {
      'Accept-Language': 'fr-FR,fr;q=0.9',
    },
  },

  // Dossier de sortie : frontend/demo-output/
  outputDir: 'demo-output/',

  reporter: [
    ['html', { outputFolder: 'demo-output/report', open: 'never' }],
    ['list'],
  ],

  projects: [
    {
      name: 'demo-iphone14pro',
      use: {
        browserName: 'chromium',
        viewport: { width: 393, height: 852 },
        deviceScaleFactor: 3,
        isMobile: true,
        hasTouch: true,
        userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
      },
    },
  ],
})
