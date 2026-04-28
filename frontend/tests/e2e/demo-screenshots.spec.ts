/**
 * Script de captures d'écran — Démo commerciale Marveline
 *
 * Produit ~35 screenshots (dark) + ~35 screenshots (light) haute qualité
 * couvrant tous les flows utilisateur, avec focus sur les réservations.
 *
 * Pré-requis :
 *   docker compose exec -T api python scripts/demo/seed_marveline_demo.py
 *
 * Exécution :
 *   cd frontend
 *   npx playwright test --config=playwright.screenshots.config.ts
 *
 * Résultat : frontend/demo-screenshots/dark/ et frontend/demo-screenshots/light/
 */

import { test, expect, type Page } from '@playwright/test'
import path from 'path'
import { fileURLToPath } from 'url'
import fs from 'fs'

const DEMO_EMAIL = 'demo@marveline.fr'
const DEMO_PASSWORD = 'DemoMarveline2026!'
const API_BASE = 'http://localhost:3000/api/v1'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const BASE_DIR = path.resolve(__dirname, '../../demo-screenshots')

// ── Helpers ─────────────────────────────────────────────────────────────────

let stepCounter = 0
let currentDir = ''

async function screenshot(page: Page, name: string, description: string) {
  stepCounter++
  const filename = `${String(stepCounter).padStart(2, '0')}_${name}.png`
  await page.screenshot({
    path: path.join(currentDir, filename),
    fullPage: false,
  })
  console.log(`  ${filename} — ${description}`)
}

async function screenshotFull(page: Page, name: string, description: string) {
  stepCounter++
  const filename = `${String(stepCounter).padStart(2, '0')}_${name}.png`
  await page.screenshot({
    path: path.join(currentDir, filename),
    fullPage: true,
  })
  console.log(`  ${filename} — ${description}`)
}

async function waitAndPause(page: Page, selector: string, timeout = 10000) {
  try {
    await page.waitForSelector(selector, { state: 'visible', timeout })
  } catch {
    // Continue
  }
  await page.waitForTimeout(1500)
}

/** Résout les IDs demo via l'API */
async function resolveDemoIds(page: Page): Promise<{
  resa: { confirmed: number; draft: number; returnedClean: number; returnedDamage: number }
  customer: number
  product: number
}> {
  // Appeler l'API pour trouver les reservations DEMO-EV*
  const resp = await page.request.get('/api/v1/reservations?page=1&per_page=20')
  const data = await resp.json().catch(() => null)
  const items = data?.items || data?.results || data || []

  const demoResas = (Array.isArray(items) ? items : [])
    .filter((r: { reference?: string }) => r.reference?.startsWith('DEMO-EV'))
    .sort((a: { id: number }, b: { id: number }) => a.id - b.id)

  if (demoResas.length >= 4) {
    return {
      resa: {
        confirmed: demoResas[0].id,
        draft: demoResas[1].id,
        returnedClean: demoResas[2].id,
        returnedDamage: demoResas[3].id,
      },
      customer: 10,
      product: 211,
    }
  }

  // Fallback si API echoue : derniers IDs connus
  console.log('WARN: DEMO reservations not found via API, using fallback IDs')
  return {
    resa: { confirmed: 3, draft: 4, returnedClean: 5, returnedDamage: 6 },
    customer: 10,
    product: 211,
  }
}

/** Attendre que le contenu de la page soit réellement chargé (pas juste le shell) */
async function waitForContent(page: Page, textOrSelector: string, timeout = 12000) {
  try {
    // D'abord attendre networkidle
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {})
    // Puis attendre le texte ou selecteur spécifique
    if (textOrSelector.startsWith('/') || textOrSelector.startsWith('.') || textOrSelector.startsWith('[')) {
      await page.waitForSelector(textOrSelector, { state: 'visible', timeout })
    } else {
      await page.getByText(textOrSelector, { exact: false }).first().waitFor({ state: 'visible', timeout })
    }
  } catch {
    // Continue anyway
  }
  // Attendre les sections secondaires (timeline, produits, factures liees)
  await page.waitForTimeout(3000)
}

async function login(page: Page) {
  await page.goto('/login')
  await waitAndPause(page, 'input[type="email"], input[name="email"]')
  await page.locator('input[type="email"], input[name="email"]').first().fill(DEMO_EMAIL)
  await page.locator('input[type="password"], input[name="password"]').first().fill(DEMO_PASSWORD)
  await page.locator('button[type="submit"]').first().click()
  await page.waitForURL(/\/(dashboard|agenda|events)/, { timeout: 15000 })
  await page.waitForTimeout(2000)
}

async function scrollTo(page: Page, pct: number) {
  await page.evaluate((p) => {
    const h = document.documentElement.scrollHeight
    window.scrollTo({ top: h * p, behavior: 'smooth' })
  }, pct)
  await page.waitForTimeout(800)
}

async function scrollBottom(page: Page) {
  // Attendre que la hauteur de page se stabilise (contenu async charge)
  await page.waitForTimeout(500)
  await page.evaluate(async () => {
    let prevHeight = 0
    for (let i = 0; i < 10; i++) {
      const h = document.documentElement.scrollHeight
      if (h > prevHeight) { prevHeight = h; await new Promise(r => setTimeout(r, 500)) }
      else break
    }
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' })
  })
  await page.waitForTimeout(1000)
}

async function scrollTop(page: Page) {
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
  await page.waitForTimeout(500)
}

async function setTheme(page: Page, theme: 'dark' | 'light') {
  await page.evaluate((t) => {
    // L'app utilise data-theme sur <html> pour les CSS variables
    document.documentElement.dataset.theme = t
    // Aussi mettre la classe pour Tailwind dark mode
    document.documentElement.classList.remove('dark', 'light')
    document.documentElement.classList.add(t)
    // Persist dans Zustand via localStorage
    try {
      const raw = localStorage.getItem('ui-store')
      if (raw) {
        const data = JSON.parse(raw)
        if (data.state) {
          data.state.theme = t
          data.state.resolvedTheme = t
          localStorage.setItem('ui-store', JSON.stringify(data))
        }
      }
    } catch {}
  }, theme)
  await page.waitForTimeout(500)
}

/** Capture toutes les pages pour un thème donné */
async function captureAllScreens(page: Page, theme: 'dark' | 'light', demoIds: Awaited<ReturnType<typeof resolveDemoIds>>) {
  stepCounter = 0
  currentDir = path.join(BASE_DIR, theme)
  fs.mkdirSync(currentDir, { recursive: true })

  console.log(`\n=== Mode ${theme.toUpperCase()} ===`)

  /** Helper : goto + theme + attendre contenu + re-theme + screenshot */
  async function snap(url: string, waitText: string, name: string, desc: string) {
    await page.goto(url)
    await setTheme(page, theme)
    await waitForContent(page, waitText)
    await setTheme(page, theme)
    await screenshot(page, name, desc)
  }

  /** Helper : scroller tout en bas (attend que la page soit chargee) */
  async function snapBottom(name: string, desc: string) {
    // Attendre que le DOM se stabilise puis forcer scroll max
    await page.waitForTimeout(2000)
    await page.evaluate(() => window.scrollTo(0, 999999))
    await page.waitForTimeout(1000)
    await setTheme(page, theme)
    await screenshot(page, name, desc)
  }

  // ── DASHBOARD ──
  await snap('/dashboard', 'Bonjour', 'dashboard', 'Tableau de bord — Accueil, KPIs, activité')

  // ── PLANNING ──
  await snap('/planning/calendar', 'Avril', 'planning', 'Planning — Calendrier mensuel')

  // ── LISTE RÉSERVATIONS ──
  await snap('/reservations', 'réservations', 'reservations_liste', 'Réservations — Compteurs et cards')

  // ── RESA LIVRÉE — haut + bas ──
  await snap(`/reservations/${demoIds.resa.confirmed}/`, '0001', 'resa_livree_haut', 'Livrée — Countdown, caution, solde')
  await snapBottom('resa_livree_bas', 'Livrée — Produits, total, facture liée')

  // ── RESA BROUILLON — haut + bas ──
  await snap(`/reservations/${demoIds.resa.draft}/`, '0002', 'resa_brouillon_haut', 'Brouillon — Prochaine étape')
  await snapBottom('resa_brouillon_bas', 'Brouillon — Actions, produit, total, signer')

  // ── RESA BROUILLON — page lignes ──
  await snap(`/reservations/${demoIds.resa.draft}/lines`, 'Articles', 'resa_lignes', 'Articles loués — Liste et ajout')

  // ── RESA BROUILLON — signature ──
  await snap(`/reservations/${demoIds.resa.draft}/signature`, 'Signature', 'resa_signature', 'Signature contrat — Pad intégré')

  // ── RESA CONFIRMÉE — haut + bas ──
  await snap(`/reservations/${demoIds.resa.returnedClean}/`, 'EV001', 'resa_confirmee_haut', 'Confirmée — Signature, caution, stock')
  await snapBottom('resa_confirmee_bas', 'Confirmée — Documents contractuels, pre-check')

  // ── RESA RETOURNÉE — haut + bas ──
  await snap(`/reservations/${demoIds.resa.returnedDamage}/`, 'EV00', 'resa_retournee_haut', 'Retournée — Timeline, contrôle')
  await snapBottom('resa_retournee_bas', 'Retournée — Clôture, produits, total, facture')

  // ── DEVIS 3 étapes ──
  await snap('/devis/new?step=1', 'Etape 1', 'devis_step1', 'Devis — Étape 1 : Client & Événement')
  await snap('/devis/new?step=2', 'Etape 2', 'devis_step2', 'Devis — Étape 2 : Articles')
  await snap('/devis/new?step=3', 'Etape 3', 'devis_step3', 'Devis — Étape 3 : Livraison')

  // ── CATALOGUE + PRODUIT ──
  await snap('/catalogue/products', 'Produits', 'catalogue', 'Catalogue — Articles en location')
  await snap(`/catalogue/products/${demoIds.product}/`, 'Chaise', 'produit_detail', 'Fiche produit — Prix, stock, disponibilité')

  // ── STOCK ──
  await snap('/stock/items', 'Stock', 'stock', 'Stock — Grille produits avec badges statut')

  // ── CLIENTS ──
  await snap('/customers', 'Clients', 'clients', 'Clients — Répertoire')

  // ── FACTURES LISTE ──
  await snap('/finance/invoices', 'Factures', 'factures_liste', 'Factures — Suivi paiements et progression')

  // ── FACTURE DETAIL — clic sur chaque facture ──
  // Cliquer la 1ere facture
  const fac1 = page.locator('a, [class*="card"]').filter({ hasText: /INV-2026-0001|634/i }).first()
  if (await fac1.isVisible({ timeout: 3000 }).catch(() => false)) {
    await fac1.click()
    await page.waitForTimeout(2000)
    await setTheme(page, theme)
    await screenshot(page, 'facture_detail_40', 'Facture 40% — Acompte, échéances, historique')
    // Fermer modale
    await page.keyboard.press('Escape')
    await page.waitForTimeout(500)
  }

  // Cliquer la 2e facture
  const fac2 = page.locator('a, [class*="card"]').filter({ hasText: /DEMO-INV001|4.?200/i }).first()
  if (await fac2.isVisible({ timeout: 3000 }).catch(() => false)) {
    await fac2.click()
    await page.waitForTimeout(2000)
    await setTheme(page, theme)
    await screenshot(page, 'facture_detail_4200', 'Facture 4200€ — Envoyée, reste 2520€')
    await page.keyboard.press('Escape')
    await page.waitForTimeout(500)
  }

  // ── OPÉRATIONS ──
  await snap('/operations', 'Départs', 'operations', 'Opérations — Départs et retours du jour')

  // ── SCAN ──
  await snap('/operations/scan', 'Recherche', 'scan', 'Scanner — Recherche rapide')

  // ── MENU ──
  await snap('/plus', 'Menu', 'menu', 'Menu — Toutes les fonctionnalités')

  console.log(`\n  ${stepCounter} captures mode ${theme}`)
}

// ── Test principal ──────────────────────────────────────────────────────────

test('Captures écran — Dark + Light', async ({ page }) => {
  test.setTimeout(15 * 60 * 1000)

  // === LOGIN SCREENSHOTS (avant authentification) ===
  for (const theme of ['dark', 'light'] as const) {
    const dir = path.join(BASE_DIR, theme)
    fs.mkdirSync(dir, { recursive: true })
    stepCounter = 0
    currentDir = dir

    await page.goto('/login')
    await waitAndPause(page, 'input[type="email"], input[name="email"]')
    await setTheme(page, theme)
    await page.waitForTimeout(300)
    await screenshot(page, 'login', 'Page de connexion')
  }

  // Login une seule fois
  await page.locator('input[type="email"], input[name="email"]').first().fill(DEMO_EMAIL)
  await page.locator('input[type="password"], input[name="password"]').first().fill(DEMO_PASSWORD)
  await page.locator('button[type="submit"]').first().click()
  await page.waitForURL(/\/(dashboard|agenda|events|reservations)/, { timeout: 15000 })
  await page.waitForTimeout(2500)

  // Résoudre les IDs demo dynamiquement
  const demoIds = await resolveDemoIds(page)
  console.log('IDs demo:', JSON.stringify(demoIds))

  // === DARK ===
  await captureAllScreens(page, 'dark', demoIds)

  // === LIGHT ===
  await captureAllScreens(page, 'light', demoIds)

  const darkCount = fs.readdirSync(path.join(BASE_DIR, 'dark')).filter(f => f.endsWith('.png')).length
  const lightCount = fs.readdirSync(path.join(BASE_DIR, 'light')).filter(f => f.endsWith('.png')).length

  console.log(`\n  Total : ${darkCount} dark + ${lightCount} light = ${darkCount + lightCount} captures`)
  console.log('  Dossier : demo-screenshots/dark/ et demo-screenshots/light/')

  expect(darkCount).toBeGreaterThan(15)
  expect(lightCount).toBeGreaterThan(15)
})
