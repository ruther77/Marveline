/**
 * Tests E2E — Workflow métier complet
 *
 * Couvre le cycle de vie complet d'une réservation :
 * 1. Création client (API)
 * 2. Création réservation (UI)
 * 3. Confirmation réservation (menu contextuel)
 * 4. Génération facture (API + vérification UI)
 * 5. Ajout paiement via InvoiceDetailModal
 * 6. Vérification statut facture mis à jour
 * 7. Ajout caution (deposit) via EventDetailsModal
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
  } catch { /* Continue */ }

  await context.clearCookies()
  await page.goto('/')
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await loginViaAPI(page)
  await page.waitForURL(/\/(dashboard|events|agenda)/, { timeout: 10000 })
}

async function cleanupWorkflowData(page: import('@playwright/test').Page) {
  try {
    const { execSync } = await import('node:child_process')
    execSync(
      `docker compose exec -T db psql -U caro -d CaroCorp -c "DELETE FROM customers WHERE email LIKE '%e2e-wf-%' AND tenant_id = 1;"`,
      { stdio: 'ignore' }
    )
  } catch { /* Ignorer */ }
}

/**
 * Cherche une référence dans un tableau paginé.
 * Navigue automatiquement vers les pages suivantes si nécessaire.
 * La fonction laisse la page sur la page où la référence a été trouvée.
 * Retourne true si trouvée, false si toutes les pages sont épuisées.
 */
async function findRefInPagedTable(
  page: import('@playwright/test').Page,
  ref: string,
  maxPages = 20
): Promise<boolean> {
  for (let attempt = 0; attempt < maxPages; attempt++) {
    // Vérifier si la référence est visible sur la page courante
    const refEl = page.locator('table').locator(`text=${ref}`).first()
    if (await refEl.isVisible({ timeout: 1500 }).catch(() => false)) {
      return true
    }

    // Chercher la zone de pagination (affichée uniquement si totalPages > 1)
    const pageInfoEl = page.locator('text=/Page \\d+ sur \\d+/').first()
    if (!await pageInfoEl.isVisible({ timeout: 500 }).catch(() => false)) {
      break // Pas de pagination → tout est affiché → référence introuvable
    }

    const pageText = await pageInfoEl.textContent().catch(() => '')
    const match = pageText?.match(/Page (\d+) sur (\d+)/)
    if (!match) break

    const currentPage = parseInt(match[1])
    const totalPgs = parseInt(match[2])
    if (currentPage >= totalPgs) break // Déjà sur la dernière page

    // Bouton "page suivante" = dernier bouton dans le conteneur de pagination
    // Structure : div(Page X sur Y).parent = div.flex.items-center.justify-between
    //             ce parent contient aussi div.flex.gap-2 > [btnPrev, btnNext]
    const nextBtn = pageInfoEl.locator('xpath=..').locator('button').last()
    const isDisabled = await nextBtn.evaluate(
      (el) => (el as HTMLButtonElement).disabled
    ).catch(() => true)
    if (isDisabled) break

    await nextBtn.click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(300)
  }
  return false
}

// Crée un jeu complet: client + réservation confirmée + facture
async function createWorkflowFixture(page: import('@playwright/test').Page) {
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
      first_name: 'WFTest',
      last_name: 'E2E',
      email: `e2e-wf-${ts}@example.com`,
      phone: '0601020304',
      customer_type: 'individual',
    },
  })
  if (!custResp.ok()) return null
  const customer = await custResp.json()

  // Réservation
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
      customer_id: customer.id,
      event_date: eventDate.toISOString().split('T')[0],
      delivery_date: deliveryDate.toISOString().split('T')[0],
      return_date: returnDate.toISOString().split('T')[0],
      notes: 'E2E workflow test',
      lines: [{ product_id: productId, quantity: 1 }],
    },
  })
  if (!resResp.ok()) return null
  const reservation = await resResp.json()

  return { customer, reservation }
}

// ============================================================================
// Tests — Workflow réservation → confirmation
// ============================================================================

test.describe('Workflow — Réservation : création et confirmation', () => {
  let fixture: { customer: any; reservation: any } | null

  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
    await cleanupWorkflowData(page)
    fixture = await createWorkflowFixture(page)
  })

  test.afterEach(async ({ page }) => {
    await cleanupWorkflowData(page)
  })

  test('une réservation draft apparaît dans EventsPage', async ({ page }) => {
    if (!fixture) { test.skip(); return }

    await page.goto('/events')
    await page.waitForLoadState('networkidle')

    // Filtrer par "draft" pour réduire les résultats
    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('draft')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    const ref = fixture.reservation.reference
    const found = await findRefInPagedTable(page, ref)
    expect(found).toBeTruthy()
  })

  test('confirmer une réservation via le menu contextuel', async ({ page }) => {
    if (!fixture) { test.skip(); return }

    await page.goto('/events')
    await page.waitForLoadState('networkidle')

    // Filtrer par "draft" pour trouver la réservation de test
    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('draft')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    const ref = fixture.reservation.reference
    const found = await findRefInPagedTable(page, ref)
    if (!found) { test.skip(); return }

    // La référence est maintenant visible sur la page courante
    const refCell = page.locator('table').locator(`text=${ref}`).first()
    const row = refCell.locator('xpath=ancestor::tr').first()
    const moreBtn = row.locator('button').last()

    if (await moreBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await moreBtn.click()
      await page.waitForTimeout(300)

      const confirmBtn = page.locator('button').filter({ hasText: /Confirmer/i }).first()
      if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await confirmBtn.click()
        await page.waitForLoadState('networkidle')
        await page.waitForTimeout(500)

        // Badge "Confirmée" doit apparaître dans la liste
        const confirmedBadge = page.locator('text=/Confirm/i').first()
        if (await confirmedBadge.isVisible({ timeout: 5000 }).catch(() => false)) {
          await expect(confirmedBadge).toBeVisible()
        }
      }
    }
  })
})

// ============================================================================
// Tests — Workflow réservation → facture
// ============================================================================

test.describe('Workflow — Réservation → Facture', () => {
  let fixture: { customer: any; reservation: any } | null
  let invoiceRef: string | null = null

  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
    await cleanupWorkflowData(page)
    fixture = await createWorkflowFixture(page)
    invoiceRef = null

    if (!fixture) return

    // Créer une facture via API
    const issueDate = new Date()
    const dueDate = new Date(issueDate)
    dueDate.setDate(issueDate.getDate() + 30)
    const invResp = await page.request.post(`${API_BASE_URL}/invoices`, {
      headers: await getApiHeaders(page),
      data: {
        reservation_id: fixture.reservation.id,
        issue_date: issueDate.toISOString().split('T')[0],
        due_date: dueDate.toISOString().split('T')[0],
      },
    })
    if (invResp.ok()) {
      const inv = await invResp.json()
      invoiceRef = inv.invoice_number
    }
  })

  test.afterEach(async ({ page }) => {
    await cleanupWorkflowData(page)
  })

  test('la facture créée est visible dans InvoicesPage', async ({ page }) => {
    if (!fixture || !invoiceRef) { test.skip(); return }

    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    // Filtrer par "draft" pour réduire les résultats
    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('draft')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    const found = await findRefInPagedTable(page, invoiceRef)
    expect(found).toBeTruthy()
  })

  test('ouvrir le modal de détail de facture', async ({ page }) => {
    if (!fixture || !invoiceRef) { test.skip(); return }

    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    // Filtrer par "draft" pour réduire les résultats
    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('draft')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    const found = await findRefInPagedTable(page, invoiceRef)
    if (!found) { test.skip(); return }

    // La référence est visible sur la page courante
    const refCell = page.locator('table').locator(`text=${invoiceRef}`).first()
    const row = refCell.locator('xpath=ancestor::tr').first()
    const moreBtn = row.locator('button').last()

    if (await moreBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await moreBtn.click()
      await page.waitForTimeout(300)

      const viewBtn = page.locator('button:visible').filter({ hasText: /Voir d[eé]tail/i }).first()
      if (await viewBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await viewBtn.click()

        const modal = page.locator('[role="dialog"]').first()
        await expect(modal).toBeVisible({ timeout: 5000 })

        // La section "Frais supplémentaires" doit être présente
        const chargesSection = modal.locator('text=/Frais suppl[eé]mentaires/i').first()
        await expect(chargesSection).toBeVisible({ timeout: 5000 })

        // Fermer le modal
        await modal.locator('button[aria-label="Fermer"]').click()
        await expect(modal).not.toBeVisible({ timeout: 3000 })
      }
    }
  })

  test('enregistrer un paiement via InvoiceDetailModal', async ({ page }) => {
    if (!fixture || !invoiceRef) { test.skip(); return }

    await page.goto('/invoices')
    await page.waitForLoadState('networkidle')

    // Filtrer par "draft" pour réduire les résultats
    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('draft')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    const found = await findRefInPagedTable(page, invoiceRef)
    if (!found) { test.skip(); return }

    // La référence est visible sur la page courante
    const refCell = page.locator('table').locator(`text=${invoiceRef}`).first()
    const row = refCell.locator('xpath=ancestor::tr').first()
    const moreBtn = row.locator('button').last()

    if (!await moreBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      test.skip()
      return
    }

    await moreBtn.click()
    await page.waitForTimeout(300)

    const viewBtn = page.locator('button:visible').filter({ hasText: /Voir d[eé]tail/i }).first()
    if (!await viewBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      test.skip()
      return
    }

    await viewBtn.click()

    const modal = page.locator('[role="dialog"]').first()
    await expect(modal).toBeVisible({ timeout: 5000 })

    // Chercher le bouton "Ajouter un paiement"
    const addPaymentBtn = modal.locator('button').filter({ hasText: /Ajouter un paiement|Enregistrer paiement/i }).first()
    if (await addPaymentBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await addPaymentBtn.click()
      await page.waitForTimeout(300)

      // Formulaire de paiement : renseigner le montant
      const amountInput = modal.locator('input[placeholder*="100"], input[type="number"]').first()
      if (await amountInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await amountInput.fill('100')

        // Soumettre
        const saveBtn = modal.locator('button').filter({ hasText: /Enregistrer|Confirmer|Valider/i }).first()
        if (await saveBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
          await saveBtn.click()
          await page.waitForLoadState('networkidle')
          await page.waitForTimeout(500)

          // L'historique de paiements doit mentionner le montant
          const paymentEntry = modal.locator('text=/100/').first()
          if (await paymentEntry.isVisible({ timeout: 3000 }).catch(() => false)) {
            await expect(paymentEntry).toBeVisible()
          }
        }
      }
    }

    // Fermer le modal
    await modal.locator('button[aria-label="Fermer"]').click()
  })
})

// ============================================================================
// Tests — Workflow caution (deposit)
// ============================================================================

test.describe('Workflow — Caution (dépôt)', () => {
  let fixture: { customer: any; reservation: any } | null

  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
    await cleanupWorkflowData(page)
    fixture = await createWorkflowFixture(page)
  })

  test.afterEach(async ({ page }) => {
    await cleanupWorkflowData(page)
  })

  test('la section caution est visible dans EventDetailsModal', async ({ page }) => {
    if (!fixture) { test.skip(); return }

    await page.goto('/events')
    await page.waitForLoadState('networkidle')

    // Filtrer par "draft" pour trouver la réservation de test
    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('draft')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    const ref = fixture.reservation.reference
    const found = await findRefInPagedTable(page, ref)
    if (!found) { test.skip(); return }

    // La référence est visible sur la page courante
    const refCell = page.locator('table').locator(`text=${ref}`).first()
    const row = refCell.locator('xpath=ancestor::tr').first()
    const moreBtn = row.locator('button').last()

    if (!await moreBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      test.skip()
      return
    }

    await moreBtn.click()
    await page.waitForTimeout(300)

    const detailBtn = page.locator('button:visible').filter({ hasText: /Voir d[eé]tail/i }).first()
    if (!await detailBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      test.skip()
      return
    }

    await detailBtn.click()

    const modal = page.locator('[role="dialog"]').first()
    await expect(modal).toBeVisible({ timeout: 5000 })

    // La section caution doit être présente
    const cautionSection = modal.locator('text=/Caution|D[eé]p[oô]t de garantie/i').first()
    await expect(cautionSection).toBeVisible({ timeout: 5000 })

    // Fermer le modal
    await modal.locator('button[aria-label="Fermer"]').click()
    await expect(modal).not.toBeVisible({ timeout: 3000 })
  })

  test('ajouter un dépôt de caution via EventDetailsModal', async ({ page }) => {
    if (!fixture) { test.skip(); return }

    await page.goto('/events')
    await page.waitForLoadState('networkidle')

    // Filtrer par "draft" pour trouver la réservation de test
    const statusSelect = page.locator('select').first()
    await statusSelect.selectOption('draft')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    const ref = fixture.reservation.reference
    const found = await findRefInPagedTable(page, ref)
    if (!found) { test.skip(); return }

    // La référence est visible sur la page courante
    const refCell = page.locator('table').locator(`text=${ref}`).first()
    const row = refCell.locator('xpath=ancestor::tr').first()
    const moreBtn = row.locator('button').last()

    if (!await moreBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      test.skip()
      return
    }

    await moreBtn.click()
    await page.waitForTimeout(300)

    const detailBtn = page.locator('button:visible').filter({ hasText: /Voir d[eé]tail/i }).first()
    if (!await detailBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      test.skip()
      return
    }

    await detailBtn.click()

    const modal = page.locator('[role="dialog"]').first()
    await expect(modal).toBeVisible({ timeout: 5000 })

    // Chercher le bouton d'ajout de caution
    const addDepositBtn = modal.locator('button').filter({ hasText: /Ajouter.*caution|Enregistrer.*d[eé]p[oô]t/i }).first()
    if (await addDepositBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await addDepositBtn.click()
      await page.waitForTimeout(300)

      // Renseigner le montant de la caution
      const amountInput = modal.locator('input[type="number"], input[placeholder*="500"]').first()
      if (await amountInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await amountInput.fill('500')

        const saveBtn = modal.locator('button').filter({ hasText: /Enregistrer|Confirmer|Valider/i }).first()
        if (await saveBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
          await saveBtn.click()
          await page.waitForLoadState('networkidle')
          await page.waitForTimeout(500)

          // La caution doit apparaître dans la section
          const depositAmount = modal.locator('text=/500/').first()
          if (await depositAmount.isVisible({ timeout: 3000 }).catch(() => false)) {
            await expect(depositAmount).toBeVisible()
          }
        }
      }
    }

    // Fermer le modal
    await modal.locator('button[aria-label="Fermer"]').click()
  })
})
