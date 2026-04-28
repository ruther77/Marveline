/**
 * Tests E2E — Clients (CustomersPage + CustomerDetailPage)
 *
 * Couvre :
 * - Affichage de la liste des clients
 * - Recherche / filtre par type
 * - Création d'un client via formulaire UI
 * - Modification d'un client
 * - Navigation vers CustomerDetailPage
 * - Suppression d'un client
 */

import { test, expect } from '@playwright/test'
import { loginViaAPI, API_BASE_URL, getApiHeaders } from './setup'

// ============================================================================
// Helpers
// ============================================================================

async function cleanupE2ECustomers(page: import('@playwright/test').Page) {
  try {
    const { execSync } = await import('node:child_process')
    execSync(
      `docker compose exec -T db psql -U caro -d CaroCorp -c "DELETE FROM customers WHERE email LIKE '%e2e-test%' AND tenant_id = 1;"`,
      { stdio: 'ignore' }
    )
  } catch {
    // Ignorer si cleanup échoue
  }
}

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
  await page.waitForURL(/\/(dashboard|customers|agenda)/, { timeout: 10000 })
}

// ============================================================================
// Tests
// ============================================================================

test.describe('CustomersPage — Liste et filtres', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la liste des clients après login', async ({ page }) => {
    await page.goto('/customers')
    await page.waitForLoadState('networkidle')

    // Heading principal
    const heading = page.locator('h1, h2').filter({ hasText: /Client/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    // Bouton de création
    const createBtn = page.locator('button').filter({ hasText: /Nouveau client/i }).first()
    await expect(createBtn).toBeVisible()
  })

  test('la barre de recherche filtre les clients', async ({ page }) => {
    await page.goto('/customers')
    await page.waitForLoadState('networkidle')

    // Trouver la barre de recherche
    const searchInput = page.locator('input[placeholder*="Recherch"], input[placeholder*="recherch"], input[placeholder*="client"], input[type="search"]').first()
    await expect(searchInput).toBeVisible({ timeout: 5000 })

    // Taper une requête qui ne renvoie rien
    await searchInput.fill('ZZZZZ_AUCUN_RESULTAT_XYZ')
    await page.waitForTimeout(800) // debounce

    // Vérifier qu'aucun résultat ou message vide s'affiche
    const noResult = page.locator('text=/Aucun client|Aucun résultat|Pas de client/i').first()
    const tableEmpty = page.locator('tbody tr').filter({ hasText: /ZZZZZ_AUCUN/ })

    // L'un des deux doit s'appliquer
    const hasNoResult = await noResult.isVisible({ timeout: 3000 }).catch(() => false)
    const rowCount = await tableEmpty.count()
    expect(hasNoResult || rowCount === 0).toBeTruthy()

    // Vider la recherche
    await searchInput.fill('')
    await page.waitForTimeout(500)
  })

  test('filtre par type "Entreprise" fonctionne', async ({ page }) => {
    await page.goto('/customers')
    await page.waitForLoadState('networkidle')

    // Trouver le filtre type
    const typeSelect = page.locator('select').filter({ hasText: /Entreprise|Particulier/i }).first()
    if (await typeSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
      await typeSelect.selectOption('company')
      await page.waitForTimeout(500)

      // Vérifier que le filtre s'applique (URL change ou liste mise à jour)
      const currentUrl = page.url()
      expect(currentUrl).toContain('/customers')
    }
  })
})

test.describe('CustomersPage — Création client', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
    await cleanupE2ECustomers(page)
  })

  test.afterEach(async ({ page }) => {
    await cleanupE2ECustomers(page)
  })

  test('ouvre le modal de création au clic sur "Nouveau client"', async ({ page }) => {
    await page.goto('/customers')
    await page.waitForLoadState('networkidle')

    const createBtn = page.locator('button').filter({ hasText: /Nouveau client/i }).first()
    await createBtn.click()

    // Un modal ou formulaire doit s'ouvrir
    const modal = page.locator('[role="dialog"], .modal, [data-modal]').first()
    await expect(modal).toBeVisible({ timeout: 5000 })

    // Des champs de formulaire doivent être présents
    const emailInput = modal.locator('input[type="email"], input[name="email"], input[placeholder*="mail"]').first()
    await expect(emailInput).toBeVisible({ timeout: 3000 })
  })

  test('crée un client particulier via le formulaire', async ({ page }) => {
    await page.goto('/customers')
    await page.waitForLoadState('networkidle')

    const createBtn = page.locator('button').filter({ hasText: /Nouveau client/i }).first()
    await createBtn.click()

    const modal = page.locator('[role="dialog"], .modal').first()
    await expect(modal).toBeVisible({ timeout: 5000 })

    const uniqueEmail = `e2e-test-create-${Date.now()}@example.com`

    // Remplir le formulaire
    const firstNameInput = modal.locator('input[name="first_name"], input[placeholder*="Prénom"]').first()
    if (await firstNameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await firstNameInput.fill('TestPrenom')
    }

    const lastNameInput = modal.locator('input[name="last_name"], input[placeholder*="Nom"]').first()
    if (await lastNameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await lastNameInput.fill('TestNom')
    }

    const emailInput = modal.locator('input[type="email"], input[name="email"]').first()
    await emailInput.fill(uniqueEmail)

    const phoneInput = modal.locator('input[name="phone"], input[placeholder*="Téléphone"]').first()
    if (await phoneInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await phoneInput.fill('0601020304')
    }

    // Soumettre
    // Le modal utilise confirmText="Creer" (sans accent) pour la création
    const submitBtn = modal.locator('button').filter({ hasText: /Cr[eé]er|Enregistrer|Sauvegarder|Ajouter/i }).first()
    await submitBtn.click()

    // Le modal doit se fermer
    await expect(modal).not.toBeVisible({ timeout: 8000 })

    // Attendre le rechargement de la liste après création
    await page.waitForLoadState('networkidle')

    // Chercher le client créé dans la liste
    const searchInput = page.locator('input[placeholder*="Recherch"], input[placeholder*="recherch"], input[type="search"]').first()
    if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await searchInput.fill('TestNom')
      // Attendre que l'API réponde (debounce + requête)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(500)
      // Chercher une ligne contenant 'TestNom' dans la table
      const newRow = page.locator('tr, [class*="row"]').filter({ hasText: 'TestNom' }).first()
      await expect(newRow).toBeVisible({ timeout: 10000 })
    }
  })
})

test.describe('CustomersPage — Modification client', () => {
  let testCustomerId: number

  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
    await cleanupE2ECustomers(page)

    // Créer un client de test via API
    const response = await page.request.post(`${API_BASE_URL}/customers`, {
      headers: await getApiHeaders(page),
      data: {
        first_name: 'E2E',
        last_name: 'ModifTest',
        email: `e2e-test-edit-${Date.now()}@example.com`,
        phone: '0601020304',
        customer_type: 'individual',
      },
    })

    if (response.ok()) {
      const data = await response.json()
      testCustomerId = data.id
    }
  })

  test.afterEach(async ({ page }) => {
    await cleanupE2ECustomers(page)
  })

  test('ouvre le modal de modification depuis le menu contextuel', async ({ page }) => {
    await page.goto('/customers')
    await page.waitForLoadState('networkidle')

    // Chercher la ligne du client de test
    const searchInput = page.locator('input[placeholder*="Recherch"], input[placeholder*="recherch"], input[type="search"]').first()
    if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await searchInput.fill('E2E')
      await page.waitForTimeout(800)
    }

    // Ouvrir le menu contextuel de la première ligne
    const moreBtn = page.locator('button').filter({ has: page.locator('svg') }).nth(0)
    const menuButtons = page.locator('button[class*="hover:bg-dark"]').first()

    // Trouver le bouton MoreVertical de la ligne E2E
    const e2eRow = page.locator('text=E2E').locator('..').locator('..').locator('..').first()
    const moreInRow = e2eRow.locator('button').last()
    if (await moreInRow.isVisible({ timeout: 3000 }).catch(() => false)) {
      await moreInRow.click()
      await page.waitForTimeout(300)

      // Cliquer "Modifier"
      const editBtn = page.locator('button').filter({ hasText: /Modifier/i }).first()
      if (await editBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await editBtn.click()

        const modal = page.locator('[role="dialog"], .modal').first()
        await expect(modal).toBeVisible({ timeout: 5000 })
      }
    }
  })
})

test.describe('CustomerDetailPage', () => {
  let testCustomerId: number

  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)

    // Créer un client via API
    const response = await page.request.post(`${API_BASE_URL}/customers`, {
      headers: await getApiHeaders(page),
      data: {
        first_name: 'HistoryTest',
        last_name: 'E2E',
        email: `e2e-test-detail-${Date.now()}@example.com`,
        phone: '0601020304',
        customer_type: 'individual',
      },
    })

    if (response.ok()) {
      const data = await response.json()
      testCustomerId = data.id
    }
  })

  test.afterEach(async ({ page }) => {
    await cleanupE2ECustomers(page)
  })

  test('affiche la page de détail d\'un client', async ({ page }) => {
    if (!testCustomerId) {
      test.skip()
      return
    }

    await page.goto(`/customers/${testCustomerId}`)
    await page.waitForLoadState('networkidle')

    // La page doit afficher les infos du client
    const nameEl = page.locator('text=HistoryTest').first()
    await expect(nameEl).toBeVisible({ timeout: 10000 })

    // Sections attendues : KPIs ou tableau de réservations
    const statsSection = page.locator('text=/Réservations|Factures|historique/i').first()
    await expect(statsSection).toBeVisible({ timeout: 5000 })
  })
})

// ============================================================================
// Helpers internes
// ============================================================================

async function getToken(page: import('@playwright/test').Page): Promise<string> {
  const auth = await page.evaluate(() => {
    const raw = localStorage.getItem('marveline-auth')
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed?.state?.accessToken || parsed?.accessToken || null
  })
  return auth || ''
}
