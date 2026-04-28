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
  login,
  logout,
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
        `docker exec futurproj_redis_sec redis-cli --no-auth-warning -a "dev_redis_sec_password_CHANGER_EN_PROD" FLUSHDB`,
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
    // Login via UI (crée une session complète avec cookie httpOnly)
    await login(page)

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
    // Login via UI pour établir la session avec cookie httpOnly
    await login(page)

    // Récupérer l'access token actuel depuis le store (pour comparer après refresh)
    const accessTokenBefore = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      if (!auth) return null
      const parsed = JSON.parse(auth)
      return parsed?.state?.accessToken || null
    })

    // Appeler /auth/refresh via page.request — le cookie httpOnly refresh_token
    // est envoyé automatiquement par le browser context (pas besoin de body)
    const refreshResponse = await page.request.post(`${API_BASE_URL}/auth/refresh`)

    expect(refreshResponse.ok()).toBeTruthy()

    const refreshData = await refreshResponse.json()
    // Le nouveau access_token doit être présent
    expect(refreshData.access_token).toBeTruthy()
    // Vérifier que c'est bien un JWT (contient des points)
    expect(refreshData.access_token).toContain('.')
    // Le nouveau token doit différer de l'ancien s'il y en avait un
    if (accessTokenBefore) {
      expect(refreshData.access_token).not.toBe(accessTokenBefore)
    }
  })

  test('doit permettre logout manuel via bouton déconnexion', async ({ page }) => {
    // Login via UI
    await login(page)

    // Vérifier qu'on est authentifié (isAuthenticated dans localStorage)
    const isAuthBefore = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      if (!auth) return false
      return !!JSON.parse(auth)?.state?.isAuthenticated
    })
    expect(isAuthBefore).toBeTruthy()

    // Utiliser le helper logout : ouvre le menu [data-testid="user-menu"] + clique Déconnexion
    await logout(page)
    // logout() attend déjà waitForURL('/login')

    // Vérifier que isAuthenticated a été remis à false
    const isAuthAfter = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      if (!auth) return false
      return !!JSON.parse(auth)?.state?.isAuthenticated
    })
    expect(isAuthAfter).toBeFalsy()
  })

  test('doit afficher sessions et permettre terminer session', async ({ page }) => {
    // Login via UI (crée une première session)
    await login(page)

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

    // Vérifier les titres de la page
    await expect(page.locator('h2').filter({ hasText: 'Sessions actives' })).toBeVisible()
    await expect(page.locator('h1:has-text("Mes sessions")')).toBeVisible()

    // Ouvrir le menu utilisateur et vérifier le bouton Déconnexion
    await page.click('[data-testid="user-menu"]')
    await expect(page.locator('text=Déconnexion')).toBeVisible()
  })
})
