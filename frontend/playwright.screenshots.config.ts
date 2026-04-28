import { defineConfig } from '@playwright/test'

/**
 * Configuration Playwright — Captures d'écran démo commerciale.
 *
 * Produit des screenshots iPhone haute résolution pour la maquette Facebook.
 *
 * Usage :
 *   npx playwright test --config=playwright.screenshots.config.ts
 *   npx playwright test --config=playwright.screenshots.config.ts --headed
 */
export default defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/demo-screenshots.spec.ts',

  timeout: 8 * 60 * 1000,
  retries: 0,
  workers: 1,

  use: {
    baseURL: 'http://localhost:3000',

    // iPhone 14 Pro — viewport mobile haute résolution
    viewport: { width: 393, height: 852 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
    userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',

    // Locale française
    locale: 'fr-FR',
    extraHTTPHeaders: {
      'Accept-Language': 'fr-FR,fr;q=0.9',
    },

    // Pas de vidéo (on veut juste les screenshots)
    video: 'off',
    screenshot: 'off', // Géré manuellement dans le test

    // Pas de slowMo (on veut que ça aille vite)
  },

  outputDir: 'demo-screenshots-output/',

  reporter: [['list']],

  projects: [
    {
      name: 'screenshots-iphone14pro',
      use: { browserName: 'chromium' },
    },
  ],
})
