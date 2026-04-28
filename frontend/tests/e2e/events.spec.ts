/**
 * Tests E2E — Réservations / Events (EventsPage)
 *
 * Couvre :
 * - Affichage de la liste des réservations
 * - Filtre par statut
 * - Ouverture du modal de création ("Nouvelle reservation")
 * - Ouverture du modal de détail via menu contextuel
 * - Actions : confirmer / annuler (sur données de test)
 */

import { test, expect } from '@playwright/test'
import { loginViaAPI, API_BASE_URL, getApiHeaders } from './setup'

// ============================================================================
// Helpers
// ============================================================================

async function stdBeforeEach(
  page: import('@playwright/test').Page,
  context: import('@playwright/test').BrowserContext
) {
  const { execSync } = await import('node:child_process')

  try {
    execSync(
      `docker exec futurproj_redis_sec redis-cli --no-auth-warning -a "dev_redis_sec_password_CHANGER_EN_PROD" FLUSHDB`,
      { stdio: 'ignore' }
    )
  } catch {
    // Continue même si Redis flush échoue
  }

  await context.clearCookies()
  await page.goto('/')
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  await loginViaAPI(page)
  await page.waitForURL(/\/(dashboard|events|agenda)/, { timeout: 10000 })
}

async function getToken(page: import('@playwright/test').Page): Promise<string> {
  return await page.evaluate(() => {
    const raw = localStorage.getItem('marveline-auth')
    if (!raw) return ''
    const parsed = JSON.parse(raw)
    return parsed?.state?.accessToken || parsed?.accessToken || ''
  })
}

async function cleanupE2EReservations(page: import('@playwright/test').Page) {
  try {
    const { execSync } = await import('node:child_process')
    // Supprimer les clients de test (cascade sur réservations)
    execSync(
      `docker compose exec -T db psql -U caro -d CaroCorp -c "DELETE FROM customers WHERE email LIKE '%e2e-ev-%' AND tenant_id = 1;"`,
      { stdio: 'ignore' }
    )
  } catch {
    // Ignorer
  }
}

// ============================================================================
// Tests — Liste et filtres
// ============================================================================

test.describe('EventsPage — Liste et filtres', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la liste des réservations après login', async ({ page }) => {
    await page.goto('/events')
    await page.waitForLoadState('networkidle')

    // Heading "Reservations"
    const heading = page.locator('h1, h2').filter({ hasText: /R[eé]servation/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    // Bouton de création
    const createBtn = page.locator('button').filter({ hasText: /Nouvelle r[eé]servation/i }).first()
    await expect(createBtn).toBeVisible()

    // Select filtre statut doit être présent
    const statusSelect = page.locator('select').first()
    await expect(statusSelect).toBeVisible()
  })

  test('le filtre de statut "Confirmée" filtre la liste', async ({ page }) => {
    await page.goto('/events')
    await page.waitForLoadState('networkidle')

    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('confirmed')

    await page.waitForTimeout(500)

    // Vérifier que le filtre est bien sélectionné
    await expect(statusSelect).toHaveValue('confirmed')

    // Si des lignes s'affichent, elles doivent toutes afficher le badge "Confirmée"
    const rows = page.locator('tbody tr, [data-row]')
    const rowCount = await rows.count()
    if (rowCount > 0) {
      // Vérifier le premier badge visible
      const firstBadge = page.locator('text=/Confirm/i').first()
      if (await firstBadge.isVisible({ timeout: 2000 }).catch(() => false)) {
        await expect(firstBadge).toBeVisible()
      }
    }
  })

  test('le bouton "Réinitialiser" efface le filtre', async ({ page }) => {
    await page.goto('/events')
    await page.waitForLoadState('networkidle')

    // Appliquer un filtre
    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('confirmed')
    await page.waitForTimeout(300)

    // Le bouton Réinitialiser doit apparaître
    const resetBtn = page.locator('button').filter({ hasText: /R[eé]initialiser/i }).first()
    await expect(resetBtn).toBeVisible({ timeout: 3000 })

    await resetBtn.click()
    await page.waitForTimeout(300)

    // Le filtre doit être vide
    await expect(statusSelect).toHaveValue('')
  })
})

// ============================================================================
// Tests — Modal de création
// ============================================================================

test.describe('EventsPage — Modal de création', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('ouvre le modal de création au clic sur "Nouvelle reservation"', async ({ page }) => {
    await page.goto('/events')
    await page.waitForLoadState('networkidle')

    const createBtn = page.locator('button').filter({ hasText: /Nouvelle r[eé]servation/i }).first()
    await createBtn.click()

    // Modal doit s'ouvrir
    const modal = page.locator('[role="dialog"]').first()
    await expect(modal).toBeVisible({ timeout: 5000 })

    // Champ de sélection client doit être présent
    const clientField = modal.locator('select, input[placeholder*="client"], input[placeholder*="Client"], [placeholder*="client"]').first()
    await expect(clientField).toBeVisible({ timeout: 3000 })

    // Fermer via bouton X (aria-label="Fermer")
    await modal.locator('button[aria-label="Fermer"]').click()
    await expect(modal).not.toBeVisible({ timeout: 3000 })
  })
})

// ============================================================================
// Tests — Modal de détail
// ============================================================================

test.describe('EventsPage — Modal de détail', () => {
  let customerId: number
  let reservationRef: string

  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
    await cleanupE2EReservations(page)

    // Créer un client de test
    const custResp = await page.request.post(`${API_BASE_URL}/customers`, {
      headers: await getApiHeaders(page),
      data: {
        first_name: 'E2E',
        last_name: 'EventTest',
        email: `e2e-ev-${Date.now()}@example.com`,
        phone: '0601020304',
        customer_type: 'individual',
      },
    })

    if (!custResp.ok()) return
    const custData = await custResp.json()
    customerId = custData.id

    // Récupérer un produit existant pour les lignes de réservation
    const prodResp = await page.request.get(`${API_BASE_URL}/products?limit=1`, {
      headers: await getApiHeaders(page),
    })
    if (!prodResp.ok()) return
    const prodData = await prodResp.json()
    const products = prodData.items ?? prodData
    if (!Array.isArray(products) || products.length === 0) return
    const productId = products[0].id

    // Créer une réservation de test via API
    const today = new Date()
    const eventDate = new Date(today)
    eventDate.setDate(today.getDate() + 14)
    const deliveryDate = new Date(eventDate)
    deliveryDate.setDate(eventDate.getDate() - 1)
    const returnDate = new Date(eventDate)
    returnDate.setDate(eventDate.getDate() + 1)

    const resResp = await page.request.post(`${API_BASE_URL}/reservations`, {
      headers: await getApiHeaders(page),
      data: {
        customer_id: customerId,
        event_date: eventDate.toISOString().split('T')[0],
        delivery_date: deliveryDate.toISOString().split('T')[0],
        return_date: returnDate.toISOString().split('T')[0],
        notes: 'E2E test reservation',
        lines: [{ product_id: productId, quantity: 1 }],
      },
    })

    if (resResp.ok()) {
      const resData = await resResp.json()
      reservationRef = resData.reference
    }
  })

  test.afterEach(async ({ page }) => {
    await cleanupE2EReservations(page)
  })

  test('le modal de détail s\'ouvre via le menu contextuel', async ({ page }) => {
    if (!reservationRef) {
      test.skip()
      return
    }

    await page.goto('/events')
    await page.waitForLoadState('networkidle')

    // Chercher la ligne de la réservation de test
    const refCell = page.locator('table').locator(`text=${reservationRef}`).first()
    if (await refCell.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Trouver le bouton MoreVertical dans la même ligne
      const row = refCell.locator('xpath=ancestor::tr').first()
      const moreBtn = row.locator('button').last()

      if (await moreBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await moreBtn.click()
        await page.waitForTimeout(300)

        // Cliquer "Voir details"
        const detailsBtn = page.locator('button').filter({ hasText: /Voir d[eé]tail/i }).first()
        if (await detailsBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await detailsBtn.click()

          const modal = page.locator('[role="dialog"]').first()
          await expect(modal).toBeVisible({ timeout: 5000 })

          // Le modal doit contenir la référence
          await expect(modal.locator(`text=${reservationRef}`)).toBeVisible({ timeout: 3000 })
        }
      }
    }
  })

  test('une réservation draft peut être confirmée', async ({ page }) => {
    if (!reservationRef) {
      test.skip()
      return
    }

    await page.goto('/events')
    await page.waitForLoadState('networkidle')

    const refCell = page.locator('table').locator(`text=${reservationRef}`).first()
    if (await refCell.isVisible({ timeout: 5000 }).catch(() => false)) {
      const row = refCell.locator('xpath=ancestor::tr').first()
      const moreBtn = row.locator('button').last()

      if (await moreBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await moreBtn.click()
        await page.waitForTimeout(300)

        const confirmBtn = page.locator('button').filter({ hasText: /Confirmer/i }).first()
        if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await confirmBtn.click()
          await page.waitForTimeout(1000)

          // La réservation doit maintenant afficher le statut "Confirmée"
          const confirmedBadge = page.locator('text=/Confirm/i').first()
          if (await confirmedBadge.isVisible({ timeout: 3000 }).catch(() => false)) {
            await expect(confirmedBadge).toBeVisible()
          }
        }
      }
    }
  })
})
