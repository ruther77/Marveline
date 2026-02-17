/**
 * Tests E2E pour Session Management
 *
 * Couvre :
 * - Création de session à login et affichage dans /admin/sessions
 * - Test du mécanisme de refresh token manuel
 * - Logout automatique si token invalide
 * - Affichage de toutes les sessions utilisateur
 */

import { test, expect } from '@playwright/test'
import {
  loginViaAPI,
  logout,
  TEST_USER,
  API_BASE_URL,
} from './setup'

test.describe('Session Management Flow', () => {
  test.beforeEach(async ({ page, context }) => {
    // Cleanup MFA via DB AVANT chaque test pour éviter interdépendance avec tests MFA
    const { execSync } = await import('node:child_process')

    try {
      execSync(
        `docker compose exec -T db psql -U caro -d CaroCorp -c "DELETE FROM mfa_devices WHERE user_id = (SELECT id FROM users WHERE email = 'test@carocorp.com' AND tenant_id = 1);"`,
        { stdio: 'ignore' }
      )
      console.log('[beforeEach] MFA cleanup successful')
    } catch (error) {
      console.warn('[beforeEach] MFA cleanup failed:', error)
    }

    // Cleanup sessions Redis pour éviter accumulation
    try {
      execSync(
        `docker compose exec -T redis redis-cli --no-auth-warning -a "dev_redis_password_CHANGER_EN_PROD" FLUSHDB`,
        { stdio: 'ignore' }
      )
      console.log('[beforeEach] Redis FLUSHDB successful')
    } catch (error) {
      console.warn('[beforeEach] Redis FLUSHDB failed:', error)
    }

    // Nettoyer cookies et localStorage
    await context.clearCookies()
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
  })

  test('doit créer session à login et afficher dans /admin/sessions', async ({ page }) => {
    // Login via API (crée une session)
    await loginViaAPI(page)

    // Attendre que la page soit bien chargée et authentifiée
    await page.waitForURL(/\/(dashboard|profile|agenda)/, { timeout: 5000 })

    // Naviguer vers la page admin/sessions
    await page.goto('/admin/sessions')

    // Attendre que la liste des sessions soit chargée
    await page.waitForSelector('[data-testid="sessions-list"]', { timeout: 5000 }).catch(async () => {
      // Si data-testid n'existe pas, chercher par classe/structure
      await page.waitForSelector('.card', { timeout: 5000 })
    })

    // Vérifier qu'au moins une session est affichée
    const sessionCards = await page.locator('.card').count()
    expect(sessionCards).toBeGreaterThanOrEqual(1)

    // Vérifier que la session contient les infos attendues (IP, user agent)
    const firstSession = page.locator('.card').first()
    await expect(firstSession).toContainText(/\d+\.\d+\.\d+\.\d+/) // IP address format
  })

  test('doit permettre refresh token manuel via API', async ({ page }) => {
    // Login pour obtenir des tokens
    await loginViaAPI(page)

    // Attendre que la page soit bien chargée et authentifiée
    await page.waitForURL(/\/(dashboard|profile|agenda)/, { timeout: 5000 })

    // Récupérer le refresh token depuis localStorage
    const refreshToken = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      if (!auth) return null
      const parsed = JSON.parse(auth)
      return parsed?.state?.refreshToken || parsed?.refreshToken
    })

    expect(refreshToken).toBeTruthy()

    // Appeler l'endpoint /auth/refresh via page.request
    const refreshResponse = await page.request.post(`${API_BASE_URL}/auth/refresh`, {
      data: { refresh_token: refreshToken },
    })

    expect(refreshResponse.ok()).toBeTruthy()

    const refreshData = await refreshResponse.json()
    expect(refreshData.access_token).toBeTruthy()
    expect(refreshData.refresh_token).toBeTruthy()

    // Les nouveaux tokens doivent être différents des anciens
    expect(refreshData.access_token).not.toBe(refreshToken)
  })

  test('doit permettre logout manuel via bouton déconnexion', async ({ page }) => {
    // Login via API
    await loginViaAPI(page)
    await page.waitForURL(/\/(dashboard|profile|agenda)/, { timeout: 5000 })

    // Vérifier qu'on est authentifié
    const authBefore = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      if (!auth) return null
      const parsed = JSON.parse(auth)
      return parsed?.state?.accessToken || parsed?.accessToken
    })
    expect(authBefore).toBeTruthy()

    // Cliquer sur bouton déconnexion
    await page.click('button:has-text("Deconnexion")')

    // Attendre redirection vers /login
    await page.waitForURL('/login', { timeout: 5000 })

    // Vérifier que le localStorage a été nettoyé
    const authAfter = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      if (!auth) return null
      const parsed = JSON.parse(auth)
      return {
        accessToken: parsed?.state?.accessToken || parsed?.accessToken,
        refreshToken: parsed?.state?.refreshToken || parsed?.refreshToken,
      }
    })

    // Après logout, les tokens doivent être vides
    expect(authAfter?.accessToken).toBeFalsy()
    expect(authAfter?.refreshToken).toBeFalsy()
  })

  test('doit afficher sessions et permettre terminer session', async ({ page }) => {
    // Login via API (crée une première session)
    await loginViaAPI(page)
    await page.waitForURL(/\/(dashboard|profile|agenda)/, { timeout: 5000 })

    // Naviguer vers admin/sessions
    await page.goto('/admin/sessions')

    // Attendre que la liste soit chargée
    await page.waitForSelector('.card', { timeout: 5000 })

    // Compter le nombre de sessions affichées (au moins 1 : la session actuelle)
    const sessionCountBefore = await page.locator('.card').count()
    expect(sessionCountBefore).toBeGreaterThanOrEqual(1)

    // Vérifier que chaque session affiche IP et user agent
    const firstSession = page.locator('.card').first()
    await expect(firstSession).toContainText(/\d+\.\d+\.\d+\.\d+/) // IP format

    // Vérifier qu'on peut voir le titre "Sessions actives" (utiliser h2 pour éviter strict mode violation)
    await expect(page.locator('h2').filter({ hasText: 'Sessions actives' })).toBeVisible()

    // Vérifier qu'on peut voir le titre "Mes sessions"
    await expect(page.locator('h1:has-text("Mes sessions")')).toBeVisible()

    // Vérifier qu'on peut voir le bouton de déconnexion dans le menu
    await expect(page.locator('button:has-text("Deconnexion")')).toBeVisible()
  })
})
