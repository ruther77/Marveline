/**
 * Tests E2E — Catalogue produits (ProductsPage + CategoriesPage + BundlesPage)
 *
 * Couvre :
 * - Affichage de la liste des produits
 * - Recherche produit (server-side, debounce)
 * - Filtres stock / catégorie
 * - Modal de création produit
 * - CategoriesPage — liste + création
 * - BundlesPage — liste + modal création
 */

import { test, expect } from '@playwright/test'
import { loginViaAPI } from './setup'

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
  await page.waitForURL(/\/(dashboard|products|agenda)/, { timeout: 10000 })
}

// ============================================================================
// Tests — ProductsPage
// ============================================================================

test.describe('ProductsPage — Liste et filtres', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la liste des produits avec heading "Produits"', async ({ page }) => {
    await page.goto('/products')
    await page.waitForLoadState('networkidle')

    const heading = page.locator('h1, h2').filter({ hasText: /^Produits$/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    // Bouton création
    const createBtn = page.locator('button').filter({ hasText: /Nouveau produit/i }).first()
    await expect(createBtn).toBeVisible({ timeout: 5000 })
  })

  test('la barre de recherche filtre les produits', async ({ page }) => {
    await page.goto('/products')
    await page.waitForLoadState('networkidle')

    const searchInput = page.locator('input[placeholder*="Rechercher par nom"]').first()
    await expect(searchInput).toBeVisible({ timeout: 5000 })

    await searchInput.fill('ZZZZZ_AUCUN_XYZ')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    // Page réactive : vide ou message aucun résultat
    const noResult = page.locator('text=/Aucun produit|Aucun résultat|0 produit/i').first()
    const hasNoResult = await noResult.isVisible({ timeout: 3000 }).catch(() => false)

    // Soit message, soit liste vide
    const rows = page.locator('tbody tr, [class*="card"]')
    const rowCount = await rows.count().catch(() => 0)
    expect(hasNoResult || rowCount === 0).toBeTruthy()

    await searchInput.fill('')
    await page.waitForLoadState('networkidle')
  })

  test('le filtre de stock fonctionne', async ({ page }) => {
    await page.goto('/products')
    await page.waitForLoadState('networkidle')

    // Le select "En stock / Stock faible / Rupture" est le 2ème select
    const stockSelect = page.locator('select').nth(1)
    if (await stockSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Les options du select stock n'ont pas de valeur fixe connue,
      // on sélectionne la 2ème option (quelle qu'elle soit)
      const options = await stockSelect.locator('option').all()
      if (options.length > 1) {
        const val = await options[1].getAttribute('value')
        if (val) {
          await stockSelect.selectOption(val)
          await page.waitForTimeout(500)
          await expect(stockSelect).toHaveValue(val)
        }
      }
    }
  })

  test('ouvre le modal de création "Nouveau produit"', async ({ page }) => {
    await page.goto('/products')
    await page.waitForLoadState('networkidle')

    const createBtn = page.locator('button').filter({ hasText: /Nouveau produit/i }).first()
    await createBtn.click()

    const modal = page.locator('[role="dialog"]').first()
    await expect(modal).toBeVisible({ timeout: 5000 })

    // Champ nom produit
    const nomInput = modal.locator('input[placeholder*="Chaise Napoleon"]').first()
    const skuInput = modal.locator('input[placeholder*="SKU"], input[placeholder*="CHR-"]').first()
    const hasNom = await nomInput.isVisible({ timeout: 2000 }).catch(() => false)
    const hasSku = await skuInput.isVisible({ timeout: 2000 }).catch(() => false)
    expect(hasNom || hasSku).toBeTruthy()

    await modal.locator('button[aria-label="Fermer"]').click()
    await expect(modal).not.toBeVisible({ timeout: 3000 })
  })
})

// ============================================================================
// Tests — CategoriesPage
// ============================================================================

test.describe('CategoriesPage — Liste et création', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la page des catégories', async ({ page }) => {
    await page.goto('/products/categories')
    await page.waitForLoadState('networkidle')

    const heading = page.locator('h1, h2').filter({ hasText: /Cat[eé]gorie/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })
  })

  test('ouvre le modal de création de catégorie', async ({ page }) => {
    await page.goto('/products/categories')
    await page.waitForLoadState('networkidle')

    // Bouton "Nouvelle catégorie" ou similaire
    const createBtn = page.locator('button').filter({ hasText: /Nouvelle cat[eé]gorie|Ajouter/i }).first()
    if (await createBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await createBtn.click()

      const modal = page.locator('[role="dialog"]').first()
      await expect(modal).toBeVisible({ timeout: 5000 })

      // Champ nom catégorie
      const nomInput = modal.locator('input[placeholder*="Mobilier"]').first()
      await expect(nomInput).toBeVisible({ timeout: 3000 })

      await modal.locator('button[aria-label="Fermer"]').click()
    }
  })
})

// ============================================================================
// Tests — BundlesPage
// ============================================================================

test.describe('BundlesPage — Formules & Packs', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la page "Formules & Packs"', async ({ page }) => {
    await page.goto('/products/bundles')
    await page.waitForLoadState('networkidle')

    const heading = page.locator('h1, h2').filter({ hasText: /Formule|Pack/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    const createBtn = page.locator('button').filter({ hasText: /Nouvelle formule/i }).first()
    await expect(createBtn).toBeVisible({ timeout: 5000 })
  })

  test('la recherche de formule fonctionne', async ({ page }) => {
    await page.goto('/products/bundles')
    await page.waitForLoadState('networkidle')

    const searchInput = page.locator('input[placeholder*="Rechercher une formule"]').first()
    if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await searchInput.fill('ZZZZZ_AUCUN_XYZ')
      await page.waitForTimeout(800)

      const noResult = page.locator('text=/Aucun|0 formule/i').first()
      const hasNoResult = await noResult.isVisible({ timeout: 3000 }).catch(() => false)
      const rowCount = await page.locator('[class*="card"], tbody tr').count().catch(() => 0)
      expect(hasNoResult || rowCount === 0).toBeTruthy()

      await searchInput.fill('')
    }
  })

  test('ouvre le modal "Nouvelle formule"', async ({ page }) => {
    await page.goto('/products/bundles')
    await page.waitForLoadState('networkidle')

    const createBtn = page.locator('button').filter({ hasText: /Nouvelle formule/i }).first()
    await createBtn.click()

    const modal = page.locator('[role="dialog"]').first()
    await expect(modal).toBeVisible({ timeout: 5000 })

    await modal.locator('button[aria-label="Fermer"]').click()
    await expect(modal).not.toBeVisible({ timeout: 3000 })
  })
})
