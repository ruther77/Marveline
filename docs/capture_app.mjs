/**
 * Capture screenshots réels du frontend CaroCorp_new
 * Viewport : iPhone 14 Pro (390×844) — même que LAYER.html pour comparaison
 * Output   : docs/screenshots/app/{screens,modals}/
 */
import { chromium } from '/home/ruuuzer/Documents/CaroCorp_new/frontend/node_modules/playwright/index.mjs'
import { mkdirSync, writeFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const BASE_URL   = 'http://localhost:5173'
const OUT_SCREENS = resolve(__dirname, 'screenshots/app/screens')
const OUT_MODALS  = resolve(__dirname, 'screenshots/app/modals')
mkdirSync(OUT_SCREENS, { recursive: true })
mkdirSync(OUT_MODALS,  { recursive: true })

const EMAIL    = 'admin@marveline.fr'
const PASSWORD = 'Admin123!'

// ── Routes à capturer ──────────────────────────────────────────────────────
const ROUTES = [
  { id: 's-login',          path: '/login',                    label: 'Page login',            group: 'Auth' },
  { id: 's-dashboard',      path: '/dashboard',                label: 'Dashboard',             group: 'Home' },
  { id: 's-finances',       path: '/finances',                 label: 'Finances',              group: 'Home' },
  { id: 's-agenda',         path: '/agenda',                   label: 'Agenda',                group: 'Planning' },
  { id: 's-events',         path: '/events',                   label: 'Événements',            group: 'Événements' },
  { id: 's-reservations',   path: '/events',                   label: 'Réservations (list)',   group: 'Événements', scrollY: 400 },
  { id: 's-customers',      path: '/customers',                label: 'Clients',               group: 'Clients' },
  { id: 's-invoices',       path: '/invoices',                 label: 'Factures',              group: 'Facturation' },
  { id: 's-products',       path: '/products',                 label: 'Produits',              group: 'Catalogue' },
  { id: 's-categories',     path: '/products/categories',      label: 'Catégories',            group: 'Catalogue' },
  { id: 's-bundles',        path: '/products/bundles',         label: 'Packs',                 group: 'Catalogue' },
  { id: 's-delivery-zones', path: '/products/delivery-zones',  label: 'Zones de livraison',    group: 'Catalogue' },
  { id: 's-stock',          path: '/inventory/stock',          label: 'Stock',                 group: 'Inventaire' },
  { id: 's-movements',      path: '/inventory/movements',      label: 'Mouvements',            group: 'Inventaire' },
  { id: 's-devis',          path: '/devis',                    label: 'Devis',                 group: 'Devis' },
  { id: 's-profile',        path: '/profile',                  label: 'Profil',                group: 'Compte' },
  { id: 's-profile-security',path:'/profile/security',         label: 'Sécurité',              group: 'Compte' },
  { id: 's-admin-users',    path: '/admin/users',              label: 'Utilisateurs',          group: 'Admin' },
  { id: 's-admin-audit',    path: '/admin/audit-logs',         label: 'Logs audit',            group: 'Admin' },
  { id: 's-admin-apikeys',  path: '/admin/api-keys',           label: 'API Keys',              group: 'Admin' },
  { id: 's-admin-features', path: '/admin/features',           label: 'Feature Flags',         group: 'Admin' },
  { id: 's-admin-sessions', path: '/admin/sessions',           label: 'Sessions',              group: 'Admin' },
]

// ── Modals à capturer (route + action pour ouvrir) ─────────────────────────
const MODALS = [
  {
    id: 'm-creer-client', label: 'Créer client', group: 'Clients',
    path: '/customers',
    open: async (page) => {
      await page.locator('button', { hasText: /nouveau client|ajouter/i }).first().click()
      await page.waitForSelector('[role="dialog"], .modal, [class*="modal"]', { timeout: 3000 }).catch(() => {})
    },
  },
  {
    id: 'm-creer-event', label: 'Créer événement', group: 'Événements',
    path: '/events',
    open: async (page) => {
      await page.locator('button', { hasText: /nouvel.* événement|créer|ajouter/i }).first().click()
      await page.waitForSelector('[role="dialog"], .modal', { timeout: 3000 }).catch(() => {})
    },
  },
  {
    id: 'm-detail-event', label: 'Détail événement', group: 'Événements',
    path: '/events',
    open: async (page) => {
      const rows = page.locator('table tbody tr, [class*="row"], [class*="card"]').first()
      const count = await rows.count()
      if (count > 0) {
        await rows.click()
        await page.waitForSelector('[role="dialog"], .modal', { timeout: 3000 }).catch(() => {})
      }
    },
  },
  {
    id: 'm-creer-facture', label: 'Créer facture', group: 'Facturation',
    path: '/invoices',
    open: async (page) => {
      await page.locator('button', { hasText: /nouvelle facture|créer/i }).first().click()
      await page.waitForSelector('[role="dialog"], .modal', { timeout: 3000 }).catch(() => {})
    },
  },
  {
    id: 'm-detail-facture', label: 'Détail facture', group: 'Facturation',
    path: '/invoices',
    open: async (page) => {
      const btn = page.locator('button[aria-label*="détail"], button', { hasText: /voir|détail/i }).first()
      if (await btn.count() > 0) {
        await btn.click()
        await page.waitForSelector('[role="dialog"], .modal', { timeout: 3000 }).catch(() => {})
      }
    },
  },
  {
    id: 'm-creer-produit', label: 'Créer produit', group: 'Catalogue',
    path: '/products',
    open: async (page) => {
      await page.locator('button', { hasText: /nouveau produit|ajouter|créer/i }).first().click()
      await page.waitForSelector('[role="dialog"], .modal', { timeout: 3000 }).catch(() => {})
    },
  },
  {
    id: 'm-creer-devis', label: 'Créer devis', group: 'Devis',
    path: '/devis',
    open: async (page) => {
      await page.locator('button', { hasText: /nouveau devis|créer/i }).first().click()
      await page.waitForSelector('[role="dialog"], .modal', { timeout: 3000 }).catch(() => {})
    },
  },
  {
    id: 'm-modifier-client', label: 'Modifier client', group: 'Clients',
    path: '/customers',
    open: async (page) => {
      // Ouvrir menu actions sur le premier client
      const moreBtn = page.locator('button[aria-label*="action"], button[aria-label*="menu"]').first()
      if (await moreBtn.count() > 0) {
        await moreBtn.click()
        await page.locator('button', { hasText: /modifier|éditer/i }).first().click()
        await page.waitForSelector('[role="dialog"], .modal', { timeout: 3000 }).catch(() => {})
      }
    },
  },
]

async function login(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' })
  await page.waitForSelector('#email', { timeout: 15000 })
  await page.fill('#email', EMAIL)
  await page.fill('#password', PASSWORD)
  await page.locator('button[type="submit"]').click()
  // Attendre la redirection vers le dashboard
  await page.waitForURL(/dashboard/, { timeout: 15000 }).catch(() => {})
  await page.waitForLoadState('networkidle')
  console.log('  ✓ Connecté')
}

async function run() {
  const browser = await chromium.launch({ headless: true })
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
  })
  const page = await ctx.newPage()

  // ── LOGIN ────────────────────────────────────────────────────────────────
  console.log('\n── LOGIN ──')
  // Capture page login d'abord (avant auth)
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2000)
  await page.waitForSelector('#email', { timeout: 15000 })
  await page.screenshot({ path: `${OUT_SCREENS}/s-login.png`, fullPage: false })
  console.log('  ✓ s-login capturé')

  await page.fill('#email', EMAIL)
  await page.fill('#password', PASSWORD)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL(/dashboard/, { timeout: 15000 }).catch(() => {})
  await page.waitForSelector('[class*="dashboard"], main, .main-content, #root > *', { timeout: 10000 }).catch(() => {})
  await page.waitForTimeout(1000)
  console.log('  ✓ Connecté')

  // ── ÉCRANS ───────────────────────────────────────────────────────────────
  const done = []
  console.log(`\n── ÉCRANS (${ROUTES.length - 1}) ──`)
  for (const route of ROUTES) {
    if (route.id === 's-login') continue // déjà capturé

    try {
      await page.goto(`${BASE_URL}${route.path}`, { waitUntil: 'domcontentloaded', timeout: 15000 })
      await page.waitForTimeout(1200)
      if (route.scrollY) await page.evaluate(y => window.scrollTo(0, y), route.scrollY)
      await page.screenshot({ path: `${OUT_SCREENS}/${route.id}.png`, fullPage: false })
      process.stdout.write('.')
      done.push({ ...route, status: 'ok' })
    } catch (e) {
      console.log(`\n  SKIP ${route.id}: ${e.message.slice(0, 60)}`)
      done.push({ ...route, status: 'skip' })
    }
  }

  // ── MODALS ───────────────────────────────────────────────────────────────
  console.log(`\n\n── MODALS (${MODALS.length}) ──`)
  const doneMod = []
  for (const modal of MODALS) {
    try {
      await page.goto(`${BASE_URL}${modal.path}`, { waitUntil: 'domcontentloaded', timeout: 15000 })
      await page.waitForTimeout(1500)
      await modal.open(page)
      await page.waitForTimeout(600)
      await page.screenshot({ path: `${OUT_MODALS}/${modal.id}.png`, fullPage: false })
      process.stdout.write('.')
      doneMod.push({ ...modal, status: 'ok' })
    } catch (e) {
      console.log(`\n  SKIP ${modal.id}: ${e.message.slice(0, 60)}`)
      doneMod.push({ ...modal, status: 'skip' })
    }
  }

  await browser.close()

  const allItems = [...done, ...doneMod]
  const ok = allItems.filter(x => x.status === 'ok').length
  const skip = allItems.filter(x => x.status === 'skip').length
  console.log(`\n\n✅ ${ok} captures — ${skip} skips`)
  console.log(`📁 ${OUT_SCREENS}`)
  console.log(`📁 ${OUT_MODALS}`)

  // Écrire le manifest pour le diaporama
  writeFileSync(
    resolve(__dirname, 'screenshots/app/manifest.json'),
    JSON.stringify({ screens: done, modals: doneMod, capturedAt: new Date().toISOString() }, null, 2)
  )
  console.log('📄 manifest.json écrit')
}

run().catch(e => { console.error(e); process.exit(1) })
