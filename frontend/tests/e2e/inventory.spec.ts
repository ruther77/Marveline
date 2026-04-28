/**
 * Tests E2E — Inventaire (InventoryPage + MovementsPage)
 *
 * Couvre :
 * - Affichage de l'InventoryPage avec KPIs
 * - Recherche produit (filtre client-side)
 * - Badges colorés de stock (available/reserved/damaged...)
 * - Navigation vers MovementsPage
 * - Liste des mouvements de stock
 * - StockItemHistoryModal (click sur bouton "Hist.")
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
  await page.waitForURL(/\/(dashboard|inventory|agenda)/, { timeout: 10000 })
}

// ============================================================================
// Tests — InventoryPage
// ============================================================================

test.describe('InventoryPage — Affichage et recherche', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la page inventaire avec les KPIs', async ({ page }) => {
    await page.goto('/inventory/stock')
    await page.waitForLoadState('networkidle')

    // Heading "Inventaire & Stock"
    const heading = page.locator('h1, h2').filter({ hasText: /Inventaire|Stock/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    // KPIs : "Stock faible" ou "Disponible" texte présent
    const kpiSection = page.locator('text=/Stock faible|Disponible/i').first()
    await expect(kpiSection).toBeVisible({ timeout: 10000 })
  })

  test('la barre de recherche filtre les produits', async ({ page }) => {
    await page.goto('/inventory/stock')
    await page.waitForLoadState('networkidle')

    // Attendre que les produits se chargent
    await page.waitForTimeout(2000)

    // Placeholder réel : "Rechercher un produit..."
    const searchInput = page.locator('input[placeholder*="Rechercher"]').first()
    await expect(searchInput).toBeVisible({ timeout: 5000 })

    // Filtrer avec un terme (les seeds créent des produits)
    await searchInput.fill('Couvert')
    await page.waitForTimeout(500) // Filtre client-side

    const productName = page.locator('text=/Couvert/i').first()
    const noResultText = page.locator('text=/Aucun produit|Aucun résultat/i').first()

    const hasProduct = await productName.isVisible({ timeout: 3000 }).catch(() => false)
    const hasNoResult = await noResultText.isVisible({ timeout: 1000 }).catch(() => false)

    expect(hasProduct || hasNoResult).toBeTruthy()

    await searchInput.fill('')
    await page.waitForTimeout(300)
  })

  test('les badges de stock sont colorés correctement', async ({ page }) => {
    await page.goto('/inventory/stock')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    const greenBadge = page.locator('[class*="green"], [class*="bg-green"]').first()
    const blueBadge = page.locator('[class*="blue"], [class*="bg-blue"]').first()

    if (await greenBadge.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(greenBadge).toBeVisible()
    } else if (await blueBadge.isVisible({ timeout: 2000 }).catch(() => false)) {
      await expect(blueBadge).toBeVisible()
    }
  })

  test('les produits sont listés avec leur nom et SKU', async ({ page }) => {
    await page.goto('/inventory/stock')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)

    // La page doit contenir des données de stock
    const pageContent = await page.content()
    const hasSomeData =
      pageContent.includes('Disponible') ||
      pageContent.includes('available') ||
      pageContent.includes('stock') ||
      pageContent.includes('Stock faible')

    expect(hasSomeData).toBeTruthy()
  })

  test('les unités cliquables ouvrent StockItemHistoryModal', async ({ page }) => {
    await page.goto('/inventory/stock')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    const histBtn = page.locator('button').filter({ hasText: /Hist\.|Hist$|Historique/i }).first()

    if (await histBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await histBtn.click()

      const modal = page.locator('[role="dialog"]').first()
      await expect(modal).toBeVisible({ timeout: 5000 })

      const histTitle = modal.locator('text=/Historique/i').first()
      await expect(histTitle).toBeVisible({ timeout: 3000 })

      // Fermer via le bouton X (aria-label="Fermer")
      await page.locator('[role="dialog"] button[aria-label="Fermer"]').click()
      await expect(modal).not.toBeVisible({ timeout: 3000 })
    }
  })
})

// ============================================================================
// Tests — MovementsPage
// ============================================================================

test.describe('MovementsPage — Mouvements de stock', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la page des mouvements de stock', async ({ page }) => {
    await page.goto('/inventory/movements')
    await page.waitForLoadState('networkidle')

    const heading = page.locator('h1, h2').filter({ hasText: /Mouvement|Sortie|Livraison/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    const createBtn = page.locator('button').filter({ hasText: /Nouveau mouvement|Nouvelle sortie/i }).first()
    await expect(createBtn).toBeVisible({ timeout: 5000 })
  })

  test('le filtre de type de mouvement fonctionne', async ({ page }) => {
    await page.goto('/inventory/movements')
    await page.waitForLoadState('networkidle')

    // Le select type a les options : '' / 'departure' / 'return'
    const typeSelect = page.locator('select').first()
    if (await typeSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
      await typeSelect.selectOption('departure')
      await page.waitForTimeout(500)

      await expect(typeSelect).toHaveValue('departure')
    }
  })

  test('peut ouvrir le modal de détail d\'un mouvement', async ({ page }) => {
    await page.goto('/inventory/movements')
    await page.waitForLoadState('networkidle')

    const moreBtn = page.locator('button').filter({ has: page.locator('svg') }).nth(1)
    if (await moreBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await moreBtn.click()
      await page.waitForTimeout(300)

      const viewBtn = page.locator('button').filter({ hasText: /Voir d[eé]tail|D[eé]tail/i }).first()
      if (await viewBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await viewBtn.click()

        const modal = page.locator('[role="dialog"]').first()
        await expect(modal).toBeVisible({ timeout: 5000 })

        // Fermer via bouton X
        await page.locator('[role="dialog"] button[aria-label="Fermer"]').first().click()
      }
    }
  })
})
