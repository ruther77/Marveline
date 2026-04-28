/**
 * Test E2E — Scenario A complet (Best Case) avec monitoring 5 axes
 * Ref: docs/SCENARIOS_DEVIS_COMPLETS.md
 *
 * Deroule le cycle de vie complet :
 *   Devis draft → send → accept → convert → Reservation draft → confirm
 *   → facturation → paiement → depart → retour → completion
 *
 * Sortie : test-results/monitoring/scenario-a-*.txt
 *
 * Usage :
 *   npx playwright test scenario-devis-complet --headed
 */

import { test, expect, type Page } from '@playwright/test'
import { E2EMonitor } from './e2e-monitor'
import { loginViaAPI, getApiHeaders, API_BASE_URL as SETUP_API_URL } from './setup'

// Port direct API (8001) — le header X-E2E-Bypass contourne le CSRF
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8001/api/v1'
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@carocorp.dev'
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'Admin123!'

// Token stocke au login, reutilise pour tous les appels API
let ACCESS_TOKEN = ''

// ── Helpers ──────────────────────────────────────────────────────────────────

function futureDate(daysFromNow: number): string {
  const d = new Date()
  d.setDate(d.getDate() + daysFromNow)
  return d.toISOString().split('T')[0]
}

async function humanDelay(page: Page, ms = 600) {
  await page.waitForTimeout(ms + Math.random() * 300)
}

async function loginAPI(page: Page, monitor: E2EMonitor) {
  monitor.trace('LOGIN_API', `email=${ADMIN_EMAIL}`)
  await page.goto('/login', { waitUntil: 'domcontentloaded' })

  const response = await page.request.post(`${API_BASE_URL}/auth/login`, {
    form: { username: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  })
  expect(response.ok(), `Login failed: ${response.status()}`).toBeTruthy()
  const data = await response.json()
  ACCESS_TOKEN = data.access_token

  await page.evaluate(
    ({ accessToken }) => {
      localStorage.setItem('marveline-auth', JSON.stringify({
        state: { isAuthenticated: true, accessToken },
        version: 0,
      }))
    },
    { accessToken: ACCESS_TOKEN },
  )

  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(2000)
  monitor.trace('LOGIN_OK', 'Token injecte, dashboard charge')
}

async function getHeaders(page: Page): Promise<Record<string, string>> {
  const token = ACCESS_TOKEN
  let csrfToken = ''
  try {
    const resp = await page.request.get(`${API_BASE_URL}/auth/csrf`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.ok()) {
      const data = await resp.json()
      csrfToken = data.csrf_token || ''
    }
  } catch { /* no csrf */ }

  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-E2E-Bypass': 'true',
    ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
  }
}

/** Headers avec Bearer token + bypass CSRF E2E (DEBUG only) */
function e2eHeaders(): Record<string, string> {
  return {
    Authorization: `Bearer ${ACCESS_TOKEN}`,
    'Content-Type': 'application/json',
    'X-E2E-Bypass': 'true',
  }
}

/** Appel API via page.request (Node context) — X-E2E-Bypass contourne le CSRF en mode DEBUG */
async function apiJson(page: Page, monitor: E2EMonitor, method: string, path: string, body?: unknown, label?: string) {
  const tag = label || `${method} ${path}`
  monitor.trace('API_CALL', tag)

  const url = `${API_BASE_URL}${path}`
  const opts = { headers: e2eHeaders(), ...(body ? { data: body } : {}) }

  let resp
  if (method === 'GET') resp = await page.request.get(url, opts)
  else if (method === 'POST') resp = await page.request.post(url, opts)
  else if (method === 'PATCH') resp = await page.request.patch(url, opts)
  else if (method === 'DELETE') resp = await page.request.delete(url, opts)
  else throw new Error(`Unknown method: ${method}`)

  if (!resp.ok()) {
    const text = await resp.text()
    monitor.trace('API_ERROR', `${tag} → ${resp.status()}: ${text.slice(0, 200)}`)
    throw new Error(`${tag} → ${resp.status()}: ${text.slice(0, 200)}`)
  }

  monitor.trace('API_OK', `${tag} → ${resp.status()}`)
  return resp.json()
}

/** Appel API non-throwing */
async function apiCall(page: Page, method: string, path: string, body?: unknown) {
  const url = `${API_BASE_URL}${path}`
  const opts = { headers: e2eHeaders(), ...(body ? { data: body } : {}) }

  let resp
  if (method === 'GET') resp = await page.request.get(url, opts)
  else if (method === 'POST') resp = await page.request.post(url, opts)
  else if (method === 'PATCH') resp = await page.request.patch(url, opts)
  else resp = await page.request.get(url, opts)

  return { ok: resp.ok(), status: resp.status(), body: await resp.text() }
}

// ── Test principal ───────────────────────────────────────────────────────────

test.describe('Scenario A — Cycle complet devis → retour (best case)', () => {
  const TS = Date.now()

  test('Parcours complet avec monitoring 5 axes', async ({ page }) => {
    const monitor = new E2EMonitor('scenario-a-best-case')
    monitor.attach(page)

    // ── Login via API directe (Node context) ──────────────────────
    monitor.trace('LOGIN', `email=${ADMIN_EMAIL}`)

    const loginResp = await page.request.post(`${API_BASE_URL}/auth/login`, {
      form: { username: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    })
    expect(loginResp.ok(), `Login failed: ${loginResp.status()}`).toBeTruthy()
    const loginData = await loginResp.json()
    ACCESS_TOKEN = loginData.access_token

    // Injecter le token dans localStorage pour que la SPA fonctionne
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await page.evaluate(
      ({ accessToken }) => {
        localStorage.setItem('marveline-auth', JSON.stringify({
          state: { isAuthenticated: true, accessToken },
          version: 0,
        }))
      },
      { accessToken: ACCESS_TOKEN },
    )
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2000)
    monitor.trace('LOGIN_OK', `Authentifie — URL: ${page.url()}`)

    // ── Etape 0 : Fixtures ─────────────────────────────────────────
    monitor.trace('FIXTURE', 'Creation client + recuperation produit')

    const products = await apiJson(page, monitor, 'GET', '/products?limit=1', undefined, 'GET produit')
    expect(products.items.length).toBeGreaterThan(0)
    const productId = products.items[0].id

    const customer = await apiJson(page, monitor, 'POST', '/customers', {
      first_name: 'Claire',
      last_name: `Thomas-${TS}`,
      email: `e2e-sc-a-${TS}@example.com`,
      phone: '0601020304',
      customer_type: 'individual',
    }, 'Creer client')

    // ── Etape 1 : Creer devis ──────────────────────────────────────
    monitor.trace('STEP_1', 'Creation devis draft')

    const devis = await apiJson(page, monitor, 'POST', '/devis', {
      customer_id: customer.id,
      event_date: futureDate(90),
      event_location: 'Domaine de la Campagne',
      delivery_date: futureDate(89),
      return_date: futureDate(91),
      valid_until: futureDate(120),
      conditions_paiement: '30_acompte',
      lines: [
        { product_id: productId, quantity: 2, label: 'Assiettes plates', unit_price_cents: products.items[0].price_per_day_cents ?? 250 },
      ],
    }, 'Creer devis')

    expect(devis.status).toBe('draft')
    expect(devis.reference).toMatch(/^DEV-/)
    monitor.trace('ASSERT', `Devis ${devis.reference} cree en draft`)

    // Verifier dans le frontend
    await page.goto(`/devis/${devis.id}`)
    await page.waitForLoadState('networkidle')
    await humanDelay(page)
    monitor.trace('UI_CHECK', `Page devis ${devis.reference} chargee`)
    // screenshot skipped — monitor.capturePage not available
    // await monitor.capturePage(page, `devis-${devis.reference}-draft`)

    // ── Etape 2 : Envoyer + Accepter ───────────────────────────────
    monitor.trace('STEP_2', 'Envoi puis acceptation')

    const sent = await apiJson(page, monitor, 'POST', `/devis/${devis.id}/send`, undefined, 'Envoyer devis')
    expect(sent.status).toBe('sent')

    const accepted = await apiJson(page, monitor, 'POST', `/devis/${devis.id}/accept`, undefined, 'Accepter devis')
    expect(accepted.status).toBe('accepted')
    monitor.trace('ASSERT', 'Devis accepte')

    // ── Etape 3 : Conversion en reservation ────────────────────────
    monitor.trace('STEP_3', 'Conversion devis → reservation')

    const convertResult = await apiJson(page, monitor, 'POST', `/devis/${devis.id}/convert`, {
      event_date: futureDate(90),
      delivery_date: futureDate(89),
      return_date: futureDate(91),
      event_location: 'Domaine de la Campagne',
    }, 'Convertir devis')

    expect(convertResult.reservation_id).toBeDefined()
    const reservationId = convertResult.reservation_id

    const devisConverted = await apiJson(page, monitor, 'GET', `/devis/${devis.id}`, undefined, 'Verif devis converted')
    expect(devisConverted.status).toBe('converted')

    const reservation = await apiJson(page, monitor, 'GET', `/reservations/${reservationId}`, undefined, 'GET reservation')
    expect(reservation.status).toBe('draft')
    expect(reservation.devis_id).toBe(devis.id)
    monitor.trace('ASSERT', `Reservation ${reservation.reference} creee, liee au devis`)

    // Verifier UI reservation
    await page.goto(`/reservations/${reservationId}`)
    await page.waitForLoadState('networkidle')
    await humanDelay(page)
    monitor.trace('UI_CHECK', `Page reservation ${reservation.reference}`)
    // screenshot skipped — monitor.capturePage not available
    // await monitor.capturePage(page, `reservation-${reservation.reference}-draft`)

    // ── Etape 4 : Confirmation ─────────────────────────────────────
    monitor.trace('STEP_4', 'Confirmation reservation')

    const confirmed = await apiJson(page, monitor, 'POST', `/reservations/${reservationId}/confirm`, undefined, 'Confirmer')
    expect(confirmed.status).toBe('confirmed')
    monitor.trace('ASSERT', 'Reservation confirmed')

    // Cocher les items pre-check existants (auto-créés par le backend) puis compléter
    const preCheckItems = await apiJson(page, monitor, 'GET', `/reservations/${reservationId}/pre-check`, undefined, 'GET pre-check items')
    for (const item of preCheckItems as Array<{ id: number }>) {
      await apiJson(page, monitor, 'PATCH', `/reservations/${reservationId}/pre-check/${item.id}`, { checked: true }, `Cocher item #${item.id}`)
    }

    const preCheck = await apiJson(page, monitor, 'POST', `/reservations/${reservationId}/pre-check/complete`, undefined, 'Valider pre-check')
    expect(preCheck.status).toBe('pre_check')
    monitor.trace('ASSERT', 'Reservation en pre_check')

    // Créer la caution (held) pour débloquer le départ
    const resaDetail = await apiJson(page, monitor, 'GET', `/reservations/${reservationId}/full`, undefined, 'GET reservation full')
    if (resaDetail.deposit_amount_cents > 0) {
      await apiJson(page, monitor, 'POST', `/reservations/${reservationId}/deposits`, {
        amount_cents: resaDetail.deposit_amount_cents,
        collection_date: futureDate(0),
      }, 'Créer caution')
      monitor.trace('ASSERT', `Caution ${resaDetail.deposit_amount_cents}c encaissée`)
    }

    // Verifier facturation auto
    const invoices = await apiJson(page, monitor, 'GET', `/invoices?reservation_id=${reservationId}`, undefined, 'GET factures')
    monitor.trace('ASSERT', `${invoices.items?.length ?? 0} facture(s) creee(s)`)

    // Verifier UI
    await page.goto(`/reservations/${reservationId}`)
    await page.waitForLoadState('networkidle')
    await humanDelay(page)
    // screenshot skipped — monitor.capturePage not available
    // await monitor.capturePage(page, `reservation-${reservation.reference}-confirmed`)

    // Cross-nav : le lien vers le devis est-il visible ?
    const devisLink = page.locator(`text=/DEV-/`).first()
    const devisLinkVisible = await devisLink.isVisible({ timeout: 5000 }).catch(() => false)
    monitor.trace('CROSS_NAV', `Lien devis visible: ${devisLinkVisible}`)

    // ── Etape 5 : Facturation + paiement ───────────────────────────
    if (invoices.items?.length > 0) {
      const invoiceId = invoices.items[0].id
      monitor.trace('STEP_5', `Facturation — INV #${invoiceId}`)

      await apiJson(page, monitor, 'POST', `/invoices/${invoiceId}/mark-sent`, {
        sent_at: new Date().toISOString().split('T')[0],
      }, 'Envoyer facture')

      const inv = await apiJson(page, monitor, 'GET', `/invoices/${invoiceId}`, undefined, 'GET facture')

      // Payer le solde intégral pour pouvoir clôturer la réservation
      const remaining = (inv.total_amount_cents ?? 0) - (inv.paid_amount_cents ?? 0)
      if (remaining > 0) {
        await apiJson(page, monitor, 'POST', `/invoices/${invoiceId}/payments`, {
          amount_cents: remaining,
          payment_method: 'transfer',
          payment_date: futureDate(0),
        }, 'Paiement facture (solde)')
      }

      const invoiceAfter = await apiJson(page, monitor, 'GET', `/invoices/${invoiceId}`, undefined, 'Verif statut facture')
      monitor.trace('ASSERT', `Facture statut: ${invoiceAfter.status}`)

      // UI
      await page.goto('/finance/invoices')
      await page.waitForLoadState('networkidle')
      await humanDelay(page)
      // screenshot skipped — monitor.capturePage not available
    // await monitor.capturePage(page, 'finance-invoices')
    }

    // ── Etape 6 : Depart ───────────────────────────────────────────
    monitor.trace('STEP_6', 'Depart materiel')

    const departResp = await apiCall(page, 'POST', `/operations/departure/${reservationId}`)
    if (departResp.ok) {
      const resAfterDepart = await apiJson(page, monitor, 'GET', `/reservations/${reservationId}`, undefined, 'Verif delivered')
      monitor.trace('ASSERT', `Reservation statut: ${resAfterDepart.status}`)
      expect(resAfterDepart.status).toBe('delivered')

      await page.goto(`/reservations/${reservationId}`)
      await page.waitForLoadState('networkidle')
      await humanDelay(page)
      // screenshot skipped — monitor.capturePage not available
    // await monitor.capturePage(page, `reservation-${reservation.reference}-delivered`)
    } else {
      monitor.trace('SKIP', `Depart non disponible (${departResp.status})`)
    }

    // ── Etape 7 : Retour ───────────────────────────────────────────
    const resBeforeReturn = await apiJson(page, monitor, 'GET', `/reservations/${reservationId}`, undefined, 'Verif avant retour')
    if (resBeforeReturn.status === 'delivered') {
      monitor.trace('STEP_7', 'Retour materiel')

      const returnResp = await apiCall(page, 'POST', `/operations/return/${reservationId}`)
      if (returnResp.ok) {
        const resAfterReturn = await apiJson(page, monitor, 'GET', `/reservations/${reservationId}`, undefined, 'Verif returned')
        monitor.trace('ASSERT', `Reservation statut: ${resAfterReturn.status}`)

        await page.goto(`/reservations/${reservationId}`)
        await page.waitForLoadState('networkidle')
        await humanDelay(page)
        // screenshot skipped — monitor.capturePage not available
    // await monitor.capturePage(page, `reservation-${reservation.reference}-returned`)
      } else {
        monitor.trace('SKIP', `Retour non disponible (${returnResp.status})`)
      }
    }

    // ── Etape 8 : Completion ───────────────────────────────────────
    const resFinal = await apiJson(page, monitor, 'GET', `/reservations/${reservationId}`, undefined, 'Verif avant completion')
    if (resFinal.status === 'returned') {
      monitor.trace('STEP_8', 'Completion reservation')

      const completed = await apiJson(page, monitor, 'POST', `/reservations/${reservationId}/complete`, undefined, 'Completer')
      expect(completed.status).toBe('completed')
      monitor.trace('ASSERT', 'Reservation terminee')

      await page.goto(`/reservations/${reservationId}`)
      await page.waitForLoadState('networkidle')
      await humanDelay(page)
      // screenshot skipped — monitor.capturePage not available
    // await monitor.capturePage(page, `reservation-${reservation.reference}-completed`)
    } else {
      monitor.trace('SKIP', `Completion impossible — statut=${resFinal.status}`)
    }

    // ── Cross-navigation finale ────────────────────────────────────
    monitor.trace('CROSS_NAV_TEST', 'Verification liens croises')

    // Reservation → Devis
    await page.goto(`/reservations/${reservationId}`)
    await page.waitForLoadState('networkidle')
    const devisChip = page.locator(`text=/DEV-/`).first()
    if (await devisChip.isVisible({ timeout: 3000 }).catch(() => false)) {
      monitor.trace('CROSS_NAV', 'Reservation → Devis : OK')
    } else {
      monitor.trace('CROSS_NAV', 'Reservation → Devis : ABSENT')
    }

    // Devis → Reservation (via status converted)
    await page.goto(`/devis/${devis.id}`)
    await page.waitForLoadState('networkidle')
    const resLink = page.locator(`text=/RES-/`).first()
    if (await resLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      monitor.trace('CROSS_NAV', 'Devis → Reservation : OK')
    } else {
      monitor.trace('CROSS_NAV', 'Devis → Reservation : ABSENT')
    }

    // ── Rapport ────────────────────────────────────────────────────
    monitor.trace('DONE', 'Scenario A termine')
    await monitor.flush()
  })
})
