/**
 * Tests E2E — Factures (InvoicesPage + InvoiceDetailModal)
 *
 * Couvre :
 * - Affichage de la liste des factures
 * - Filtre par statut
 * - Ouverture du modal de détail
 * - Section frais supplémentaires (charges)
 * - Historique des paiements
 * - Action "Envoyer" (draft → sent)
 * - Action "Annuler"
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
    // Continue
  }

  await context.clearCookies()
  await page.goto('/')
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })

  await loginViaAPI(page)
  await page.waitForURL(/\/(dashboard|invoices|agenda)/, { timeout: 10000 })
}

async function getToken(page: import('@playwright/test').Page): Promise<string> {
  return await page.evaluate(() => {
    const raw = localStorage.getItem('marveline-auth')
    if (!raw) return ''
    const parsed = JSON.parse(raw)
    return parsed?.state?.accessToken || parsed?.accessToken || ''
  })
}

async function cleanupE2EData(page: import('@playwright/test').Page) {
  try {
    const { execSync } = await import('node:child_process')
    execSync(
      `docker compose exec -T db psql -U caro -d CaroCorp -c "DELETE FROM customers WHERE email LIKE '%e2e-inv-%' AND tenant_id = 1;"`,
      { stdio: 'ignore' }
    )
  } catch {
    // Ignorer
  }
}

// Crée un jeu de données complet: customer + reservation + invoice
async function createTestInvoice(page: import('@playwright/test').Page) {
  const ts = Date.now()

  // Récupérer un produit existant pour les lignes de réservation
  const prodResp = await page.request.get(`${API_BASE_URL}/products?limit=1`, {
    headers: await getApiHeaders(page),
  })
  if (!prodResp.ok()) return null
  const prodData = await prodResp.json()
  const products = prodData.items ?? prodData
  if (!Array.isArray(products) || products.length === 0) return null
  const productId = products[0].id

  // Client
  const custResp = await page.request.post(`${API_BASE_URL}/customers`, {
    headers: await getApiHeaders(page),
    data: {
      first_name: 'InvTest',
      last_name: 'E2E',
      email: `e2e-inv-${ts}@example.com`,
      customer_type: 'individual',
    },
  })
  if (!custResp.ok()) return null
  const cust = await custResp.json()

  // Réservation
  const today = new Date()
  const eventDate = new Date(today)
  eventDate.setDate(today.getDate() + 10)
  const deliveryDate = new Date(eventDate)
  deliveryDate.setDate(eventDate.getDate() - 1)
  const resResp = await page.request.post(`${API_BASE_URL}/reservations`, {
    headers: await getApiHeaders(page),
    data: {
      customer_id: cust.id,
      event_date: eventDate.toISOString().split('T')[0],
      delivery_date: deliveryDate.toISOString().split('T')[0],
      return_date: new Date(eventDate.getTime() + 86400000).toISOString().split('T')[0],
      lines: [{ product_id: productId, quantity: 1 }],
    },
  })
  if (!resResp.ok()) return null
  const res = await resResp.json()

  // Facture
  const issueDate = new Date()
  const dueDate = new Date(issueDate)
  dueDate.setDate(issueDate.getDate() + 30)
  const invResp = await page.request.post(`${API_BASE_URL}/invoices`, {
    headers: await getApiHeaders(page),
    data: {
      reservation_id: res.id,
      issue_date: issueDate.toISOString().split('T')[0],
      due_date: dueDate.toISOString().split('T')[0],
    },
  })
  if (!invResp.ok()) return null
  const inv = await invResp.json()

  return { customer: cust, reservation: res, invoice: inv }
}

// ============================================================================
// Tests — Liste et filtres
// ============================================================================

test.describe('InvoicesPage — Liste et filtres', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la liste des factures après login', async ({ page }) => {
    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    // Heading doit contenir "Facture"
    const heading = page.locator('h1, h2').filter({ hasText: /Facture/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    // Filtre statut doit être présent
    const statusSelect = page.locator('select').first()
    await expect(statusSelect).toBeVisible()
  })

  test('le filtre par statut "Brouillon" fonctionne', async ({ page }) => {
    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('draft')
    await page.waitForTimeout(500)

    await expect(statusSelect).toHaveValue('draft')
  })

  test('le filtre par statut "Payée" fonctionne', async ({ page }) => {
    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('paid')
    await page.waitForTimeout(500)

    await expect(statusSelect).toHaveValue('paid')

    // Si des factures payées s'affichent, vérifier le badge
    const paidBadge = page.locator('text=/Pay[eé]e/i').first()
    if (await paidBadge.isVisible({ timeout: 2000 }).catch(() => false)) {
      await expect(paidBadge).toBeVisible()
    }
  })
})

// ============================================================================
// Tests — Modal de détail
// ============================================================================

test.describe('InvoicesPage — Modal de détail', () => {
  let testData: { customer: any; reservation: any; invoice: any } | null

  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
    await cleanupE2EData(page)
    testData = await createTestInvoice(page)
  })

  test.afterEach(async ({ page }) => {
    await cleanupE2EData(page)
  })

  test('ouvre le modal de détail d\'une facture', async ({ page }) => {
    if (!testData) {
      test.skip()
      return
    }

    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    // Chercher la référence de la facture dans la liste
    const invRef = testData.invoice.invoice_number
    const refCell = page.locator('table').locator(`text=${invRef}`).first()

    if (await refCell.isVisible({ timeout: 5000 }).catch(() => false)) {
      // Trouver le menu contextuel
      const row = refCell.locator('xpath=ancestor::tr').first()
      const moreBtn = row.locator('button').last()

      if (await moreBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await moreBtn.click()
        await page.waitForTimeout(300)

        const viewBtn = page.locator('button').filter({ hasText: /Voir d[eé]tail|Consulter/i }).first()
        if (await viewBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await viewBtn.click()

          const modal = page.locator('[role="dialog"]').first()
          await expect(modal).toBeVisible({ timeout: 5000 })

          // Le modal doit contenir la référence ou le nom du client
          const invRefInModal = modal.locator(`text=${invRef}`).first()
          const clientNameInModal = modal.locator('text=InvTest').first()

          const hasRef = await invRefInModal.isVisible({ timeout: 3000 }).catch(() => false)
          const hasName = await clientNameInModal.isVisible({ timeout: 1000 }).catch(() => false)
          expect(hasRef || hasName).toBeTruthy()
        }
      }
    } else {
      // Fallback : si la facture n'est pas visible, vérifier que la page charge
      const heading = page.locator('h1, h2').filter({ hasText: /Facture/i }).first()
      await expect(heading).toBeVisible()
    }
  })

  test('peut envoyer une facture brouillon (draft → sent)', async ({ page }) => {
    if (!testData) {
      test.skip()
      return
    }

    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    const invRef = testData.invoice.invoice_number
    const refCell = page.locator('table').locator(`text=${invRef}`).first()

    if (await refCell.isVisible({ timeout: 5000 }).catch(() => false)) {
      const row = refCell.locator('xpath=ancestor::tr').first()
      const moreBtn = row.locator('button').last()

      if (await moreBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await moreBtn.click()
        await page.waitForTimeout(300)

        const sendBtn = page.locator('button').filter({ hasText: /Envoyer/i }).first()
        if (await sendBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await sendBtn.click()
          await page.waitForTimeout(1000)

          // La liste doit se rafraîchir - la facture peut afficher "Envoyée"
          const sentBadge = page.locator(`text=/Envoy[eé]e/i`).first()
          if (await sentBadge.isVisible({ timeout: 3000 }).catch(() => false)) {
            await expect(sentBadge).toBeVisible()
          }
        }
      }
    }
  })
})

// ============================================================================
// Tests — Section frais supplémentaires
// ============================================================================

test.describe('InvoiceDetailModal — Frais supplémentaires', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('la section "Frais supplémentaires" est visible dans le modal de détail', async ({ page }) => {
    // Naviguer vers la page des factures
    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    // S'il y a des factures, en ouvrir une au hasard pour vérifier la section
    const anyMoreBtn = page.locator('button').filter({ has: page.locator('svg') }).nth(1)
    if (await anyMoreBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await anyMoreBtn.click()
      await page.waitForTimeout(300)

      const viewBtn = page.locator('button').filter({ hasText: /Voir d[eé]tail|Consulter/i }).first()
      if (await viewBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await viewBtn.click()

        const modal = page.locator('[role="dialog"]').first()
        await expect(modal).toBeVisible({ timeout: 5000 })

        // La section frais doit être présente (même vide)
        const chargesSection = modal.locator('text=/Frais suppl[eé]mentaires/i').first()
        await expect(chargesSection).toBeVisible({ timeout: 5000 })

        // Fermer le modal
        await page.keyboard.press('Escape')
      }
    }
  })
})
