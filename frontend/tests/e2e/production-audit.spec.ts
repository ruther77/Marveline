/**
 * Production Audit E2E — Simulation d'actions humaines avec monitoring 5 axes
 *
 * Scénarios réalistes exécutés via ngrok en conditions réelles.
 * Chaque test produit un rapport .txt complet dans test-results/monitoring/.
 *
 * Usage :
 *   npx playwright test production-audit --headed
 *   ./scripts/deploy/run-e2e-ngrok.sh   (orchestrateur complet)
 */

import { test, expect, type Page } from '@playwright/test'
import { E2EMonitor } from './e2e-monitor'

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8001/api/v1'
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@carocorp.dev'
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'Admin123!'

// ── Helpers ──────────────────────────────────────────────────────────────────

async function humanDelay(page: Page, ms = 800) {
  await page.waitForTimeout(ms + Math.random() * 400)
}

async function loginUI(page: Page, monitor: E2EMonitor) {
  monitor.trace('LOGIN_START', `email=${ADMIN_EMAIL}`)
  await page.goto('/login', { waitUntil: 'domcontentloaded' })
  await humanDelay(page, 500)

  await page.fill('input[name="email"]', ADMIN_EMAIL)
  await humanDelay(page, 300)
  await page.fill('input[name="password"]', ADMIN_PASSWORD)
  await humanDelay(page, 200)

  await page.click('button[type="submit"]')
  monitor.trace('LOGIN_SUBMIT', 'Attente redirect...')

  await page.waitForURL(/\/(dashboard|agenda|reservations)/, { timeout: 15000 })
  monitor.trace('LOGIN_OK', `Redirigé vers ${page.url()}`)
}

async function loginAPI(page: Page, monitor: E2EMonitor) {
  monitor.trace('LOGIN_API', `email=${ADMIN_EMAIL}`)
  await page.goto('/login', { waitUntil: 'domcontentloaded' })

  const response = await page.request.post(`${API_BASE_URL}/auth/login`, {
    form: { username: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  })
  expect(response.ok(), `Login API failed: ${response.status()}`).toBeTruthy()
  const data = await response.json()

  await page.evaluate(
    ({ accessToken }) => {
      localStorage.setItem('marveline-auth', JSON.stringify({
        state: { isAuthenticated: true, accessToken },
        version: 0,
      }))
    },
    { accessToken: data.access_token },
  )

  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2000)
  monitor.trace('LOGIN_API_OK', 'Token injecté, dashboard chargé')
}

// ── Test 1 : Parcours Login UI humain ────────────────────────────────────────

test.describe('Production Audit — Actions humaines', () => {
  test('SC-01 Login UI + navigation complète', async ({ page }) => {
    const monitor = new E2EMonitor('SC01_login_navigation')
    monitor.attach(page)

    // Login comme un humain
    await loginUI(page, monitor)

    // Navigation séquentielle — simule un utilisateur qui parcourt l'app
    const pages = [
      { name: 'Dashboard', url: '/dashboard' },
      { name: 'Réservations', url: '/reservations' },
      { name: 'Catalogue', url: '/catalogue' },
      { name: 'Packs', url: '/catalogue/bundles' },
      { name: 'Clients', url: '/clients' },
      { name: 'Factures', url: '/factures' },
      { name: 'Devis', url: '/devis' },
      { name: 'Stock', url: '/stock' },
      { name: 'Planning', url: '/planning' },
    ]

    for (const p of pages) {
      await monitor.measureNavigation(page, p.url, p.name, 2000)
      await humanDelay(page, 1000)
    }

    monitor.trace('SCENARIO_END', 'Navigation complète terminée')
    monitor.flush()
  })

  test('SC-02 CRUD Produit complet', async ({ page }) => {
    const monitor = new E2EMonitor('SC02_crud_produit')
    monitor.attach(page)
    await loginAPI(page, monitor)

    // Naviguer vers catalogue
    await monitor.measureNavigation(page, '/catalogue', 'Catalogue', 2000)

    // Cliquer sur "Nouveau produit"
    monitor.trace('PRODUCT_CREATE_START', 'Ouverture formulaire')
    const addBtn = page.locator('button:has-text("Nouveau"), a:has-text("Nouveau")')
    if (await addBtn.count() > 0) {
      await addBtn.first().click()
      await humanDelay(page)

      // Remplir le formulaire
      const nameInput = page.locator('input[name="name"], #product-name')
      if (await nameInput.count() > 0) {
        await nameInput.fill('Produit E2E Test ' + Date.now())
        monitor.trace('PRODUCT_FILL', 'Nom rempli')
        await humanDelay(page, 400)
      }

      const skuInput = page.locator('input[name="sku"], #product-sku')
      if (await skuInput.count() > 0) {
        await skuInput.fill('E2E-' + Date.now())
        monitor.trace('PRODUCT_FILL', 'SKU rempli')
      }

      // Soumettre si possible
      const submitBtn = page.locator('button[type="submit"], button:has-text("Créer"), button:has-text("Enregistrer")')
      if (await submitBtn.count() > 0) {
        await submitBtn.first().click()
        monitor.trace('PRODUCT_SUBMIT', 'Formulaire soumis')
        await humanDelay(page, 2000)
      }
    } else {
      monitor.trace('PRODUCT_CREATE_SKIP', 'Bouton "Nouveau" non trouvé')
    }

    // Revenir à la liste
    await monitor.measureNavigation(page, '/catalogue', 'Catalogue retour', 2000)

    // Recherche produit
    const searchInput = page.locator('input[placeholder*="echerch"], input[type="search"]')
    if (await searchInput.count() > 0) {
      await searchInput.first().fill('assiette')
      monitor.trace('PRODUCT_SEARCH', 'Recherche "assiette"')
      await humanDelay(page, 1500)
    }

    monitor.trace('SCENARIO_END', 'CRUD produit terminé')
    monitor.flush()
  })

  test('SC-03 Workflow réservation client', async ({ page }) => {
    const monitor = new E2EMonitor('SC03_workflow_reservation')
    monitor.attach(page)
    await loginAPI(page, monitor)

    // 1. Clients
    await monitor.measureNavigation(page, '/clients', 'Clients', 2000)
    monitor.trace('CLIENT_LIST', 'Liste clients chargée')

    // 2. Réservations
    await monitor.measureNavigation(page, '/reservations', 'Réservations', 2000)
    monitor.trace('RESERVATION_LIST', 'Liste réservations chargée')

    // Cliquer sur la première réservation si dispo
    const firstRow = page.locator('tr[data-testid], article, [class*="card"]').first()
    if (await firstRow.count() > 0) {
      await firstRow.click()
      monitor.trace('RESERVATION_DETAIL', 'Ouverture détail réservation')
      await humanDelay(page, 2000)
    }

    // 3. Devis
    await monitor.measureNavigation(page, '/devis', 'Devis', 2000)
    monitor.trace('DEVIS_LIST', 'Liste devis chargée')

    // 4. Factures
    await monitor.measureNavigation(page, '/factures', 'Factures', 2000)
    monitor.trace('INVOICE_LIST', 'Liste factures chargée')

    // 5. Opérations
    await monitor.measureNavigation(page, '/operations', 'Opérations', 2000)
    monitor.trace('OPERATIONS', 'Page opérations chargée')

    monitor.trace('SCENARIO_END', 'Workflow réservation terminé')
    monitor.flush()
  })

  test('SC-04 Admin + sessions + audit', async ({ page }) => {
    const monitor = new E2EMonitor('SC04_admin_sessions')
    monitor.attach(page)
    await loginAPI(page, monitor)

    // Admin pages
    const adminPages = [
      { name: 'Users', url: '/admin/users' },
      { name: 'Sessions', url: '/admin/sessions' },
      { name: 'Audit Logs', url: '/admin/audit' },
      { name: 'Feature Flags', url: '/admin/features' },
      { name: 'API Keys', url: '/admin/api-keys' },
      { name: 'Settings', url: '/admin/settings' },
    ]

    for (const p of adminPages) {
      await monitor.measureNavigation(page, p.url, p.name, 2000)
      await humanDelay(page, 800)
    }

    monitor.trace('SCENARIO_END', 'Pages admin parcourues')
    monitor.flush()
  })

  test('SC-05 Stress navigation rapide (parasitage)', async ({ page }) => {
    const monitor = new E2EMonitor('SC05_stress_navigation')
    monitor.attach(page)
    await loginAPI(page, monitor)

    // Navigation rapide sans attendre — détecte les requêtes fantômes
    const fastPages = [
      '/dashboard', '/reservations', '/catalogue', '/clients',
      '/factures', '/devis', '/stock', '/dashboard',
      '/reservations', '/catalogue',
    ]

    for (const url of fastPages) {
      const name = url.replace('/', '').replace(/\//g, '_') || 'root'
      monitor.trace('FAST_NAV', url)
      await page.goto(url, { waitUntil: 'commit' })
      await page.waitForTimeout(500) // Délai court — simule clic rapide
    }

    // Attendre que tout se stabilise
    await page.waitForTimeout(5000)
    monitor.trace('STABILIZE', 'Attente stabilisation 5s')

    monitor.trace('SCENARIO_END', 'Stress navigation terminé')
    monitor.flush()
  })

  test('SC-06 Logout + re-login + vérification session', async ({ page }) => {
    const monitor = new E2EMonitor('SC06_auth_lifecycle')
    monitor.attach(page)

    // Login UI
    await loginUI(page, monitor)
    await humanDelay(page, 1000)

    // Vérifier qu'on est bien authentifié
    monitor.trace('AUTH_CHECK', 'Vérification page protégée')
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2000)
    const url = page.url()
    monitor.trace('AUTH_CHECK_RESULT', `URL: ${url}`)

    // Logout
    monitor.trace('LOGOUT_START', 'Recherche bouton logout')
    const userMenu = page.locator('[data-testid="user-menu"], button:has-text("Déconnexion"), [aria-label*="profil"]')
    if (await userMenu.count() > 0) {
      await userMenu.first().click()
      await humanDelay(page, 500)
      const logoutBtn = page.locator('button:has-text("Déconnexion"), a:has-text("Déconnexion")')
      if (await logoutBtn.count() > 0) {
        await logoutBtn.first().click()
        monitor.trace('LOGOUT_CLICK', 'Bouton déconnexion cliqué')
        await page.waitForTimeout(3000)
        monitor.trace('LOGOUT_RESULT', `URL après logout: ${page.url()}`)
      }
    } else {
      monitor.trace('LOGOUT_SKIP', 'Menu utilisateur non trouvé — skip logout')
    }

    // Re-login
    await loginUI(page, monitor)
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2000)
    monitor.trace('RELOGIN_CHECK', `URL après re-login: ${page.url()}`)

    monitor.trace('SCENARIO_END', 'Auth lifecycle terminé')
    monitor.flush()
  })
})
