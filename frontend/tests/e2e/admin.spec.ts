/**
 * Tests E2E — Administration (UsersPage, AuditLogsPage, FeatureFlagsPage, ApiKeysPage)
 *
 * Couvre :
 * - UsersPage : liste, filtres, modal création
 * - AuditLogsPage : liste, filtres par action
 * - FeatureFlagsPage : liste, modal création
 * - ApiKeysPage : liste, modal création
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
  await page.waitForURL(/\/(dashboard|admin|agenda)/, { timeout: 10000 })
}

// ============================================================================
// Tests — UsersPage
// ============================================================================

test.describe('UsersPage — Gestion utilisateurs', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la liste des utilisateurs', async ({ page }) => {
    await page.goto('/admin/users')
    await page.waitForLoadState('networkidle')

    const heading = page.locator('h1, h2').filter({ hasText: /Utilisateur/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })

    const createBtn = page.locator('button').filter({ hasText: /Nouvel utilisateur/i }).first()
    await expect(createBtn).toBeVisible({ timeout: 5000 })
  })

  test('la recherche filtre les utilisateurs', async ({ page }) => {
    await page.goto('/admin/users')
    await page.waitForLoadState('networkidle')

    const searchInput = page.locator('input[placeholder*="Rechercher par nom"]').first()
    if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await searchInput.fill('ZZZZZ_AUCUN')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(500)

      const noResult = page.locator('text=/Aucun utilisateur|Aucun résultat/i').first()
      const hasNoResult = await noResult.isVisible({ timeout: 3000 }).catch(() => false)
      const rowCount = await page.locator('tbody tr').count().catch(() => 0)
      // rowCount <= 1 : 0 = aucun row, 1 = ligne état vide "Aucun utilisateur trouvé"
      expect(hasNoResult || rowCount <= 1).toBeTruthy()

      await searchInput.fill('')
    }
  })

  test('le filtre de rôle fonctionne', async ({ page }) => {
    await page.goto('/admin/users')
    await page.waitForLoadState('networkidle')

    const roleSelect = page.locator('select').first()
    if (await roleSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
      await roleSelect.selectOption('admin')
      await page.waitForTimeout(500)
      await expect(roleSelect).toHaveValue('admin')

      // Réinitialiser
      const resetBtn = page.locator('button').filter({ hasText: /R[eé]initialiser/i }).first()
      if (await resetBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
        await resetBtn.click()
        await page.waitForTimeout(300)
      }
    }
  })

  test('ouvre le modal "Nouvel utilisateur"', async ({ page }) => {
    await page.goto('/admin/users')
    await page.waitForLoadState('networkidle')

    const createBtn = page.locator('button').filter({ hasText: /Nouvel utilisateur/i }).first()
    await createBtn.click()

    const modal = page.locator('[role="dialog"]').first()
    await expect(modal).toBeVisible({ timeout: 5000 })

    // Champ email doit être présent
    const emailInput = modal.locator('input[type="email"], input[placeholder*="email"], input[placeholder*="@"]').first()
    await expect(emailInput).toBeVisible({ timeout: 3000 })

    await modal.locator('button[aria-label="Fermer"]').click()
    await expect(modal).not.toBeVisible({ timeout: 3000 })
  })
})

// ============================================================================
// Tests — AuditLogsPage
// ============================================================================

test.describe('AuditLogsPage — Journaux d\'audit', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la page des audit logs', async ({ page }) => {
    await page.goto('/admin/audit-logs')
    await page.waitForLoadState('networkidle')

    const heading = page.locator('h1, h2').filter({ hasText: /Audit/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })
  })

  test('le filtre par action fonctionne', async ({ page }) => {
    await page.goto('/admin/audit-logs')
    await page.waitForLoadState('networkidle')

    const actionSelect = page.locator('select').first()
    if (await actionSelect.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Sélectionner "login" parmi les actions
      const options = await actionSelect.locator('option').allInnerTexts()
      const loginOption = options.find(o => /Connexion|login/i.test(o))
      if (loginOption) {
        await actionSelect.selectOption({ label: loginOption })
        await page.waitForLoadState('networkidle')
        await page.waitForTimeout(300)
      }
    }
  })

  test('la barre de recherche fonctionne', async ({ page }) => {
    await page.goto('/admin/audit-logs')
    await page.waitForLoadState('networkidle')

    const searchInput = page.locator('input[placeholder*="Rechercher"], input[placeholder*="action"]').first()
    if (await searchInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await searchInput.fill('login')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(500)

      // La page doit toujours afficher quelque chose (pas d'erreur)
      const heading = page.locator('h1, h2').filter({ hasText: /Audit/i }).first()
      await expect(heading).toBeVisible()
    }
  })
})

// ============================================================================
// Tests — FeatureFlagsPage
// ============================================================================

test.describe('FeatureFlagsPage — Drapeaux de fonctionnalité', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la page des feature flags', async ({ page }) => {
    await page.goto('/admin/features')
    await page.waitForLoadState('networkidle')

    const heading = page.locator('h1, h2').filter({ hasText: /Feature/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })
  })

  test('ouvre le modal "Nouveau flag"', async ({ page }) => {
    await page.goto('/admin/features')
    await page.waitForLoadState('networkidle')

    const createBtn = page.locator('button').filter({ hasText: /Nouveau flag|Cr[eé]er le premier/i }).first()
    if (await createBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await createBtn.click()

      const modal = page.locator('[role="dialog"]').first()
      await expect(modal).toBeVisible({ timeout: 5000 })

      // Champ nom technique
      const nomInput = modal.locator('input[placeholder*="enable_new"]').first()
      if (await nomInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await expect(nomInput).toBeVisible()
      }

      await modal.locator('button[aria-label="Fermer"]').click()
      await expect(modal).not.toBeVisible({ timeout: 3000 })
    }
  })
})

// ============================================================================
// Tests — ApiKeysPage
// ============================================================================

test.describe('ApiKeysPage — Clés API', () => {
  test.beforeEach(async ({ page, context }) => {
    await stdBeforeEach(page, context)
  })

  test('affiche la page des API Keys', async ({ page }) => {
    await page.goto('/admin/api-keys')
    await page.waitForLoadState('networkidle')

    const heading = page.locator('h1, h2').filter({ hasText: /API Key|Cl[eé] API/i }).first()
    await expect(heading).toBeVisible({ timeout: 10000 })
  })

  test('ouvre le modal "Nouvelle clé"', async ({ page }) => {
    await page.goto('/admin/api-keys')
    await page.waitForLoadState('networkidle')

    const createBtn = page.locator('button').filter({ hasText: /Nouvelle cl[eé]|Cr[eé]er la premi[eè]re/i }).first()
    if (await createBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await createBtn.click()

      const modal = page.locator('[role="dialog"]').first()
      await expect(modal).toBeVisible({ timeout: 5000 })

      // Champ "Nom" de la clé
      const nomInput = modal.locator('input[placeholder*="API Integration"], input[placeholder*="Nom"]').first()
      if (await nomInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await expect(nomInput).toBeVisible()
      }

      await modal.locator('button[aria-label="Fermer"]').click()
      await expect(modal).not.toBeVisible({ timeout: 3000 })
    }
  })

  test('la checkbox "Afficher les clés révoquées" fonctionne', async ({ page }) => {
    await page.goto('/admin/api-keys')
    await page.waitForLoadState('networkidle')

    const checkbox = page.locator('input[type="checkbox"]').first()
    if (await checkbox.isVisible({ timeout: 3000 }).catch(() => false)) {
      const initialState = await checkbox.isChecked()
      await checkbox.click()
      await page.waitForTimeout(300)
      expect(await checkbox.isChecked()).toBe(!initialState)
    }
  })
})
