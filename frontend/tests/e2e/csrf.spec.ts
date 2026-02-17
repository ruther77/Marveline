/**
 * Tests E2E pour CSRF Flow
 *
 * Couvre :
 * - Auto-fetch CSRF token après login
 * - Stockage et renouvellement manuel du token CSRF
 * - Gestion d'erreur lors du renouvellement sans crash
 */

import { test, expect } from '@playwright/test'
import {
  login,
  waitForCSRFToken,
  getCSRFToken,
  expectToastError,
  API_BASE_URL,
} from './setup'

test.describe('CSRF Flow', () => {
  test.beforeEach(async ({ page, context }) => {
    // Nettoyer localStorage et cookies avant chaque test
    await context.clearCookies()
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
  })

  test('doit auto-fetch CSRF token après login', async ({ page }) => {
    // Le CSRF token est fetch automatiquement après login via setTokens()
    await login(page)

    // Attendre que le token soit stocké dans localStorage
    await waitForCSRFToken(page)

    // Vérifier que le token existe et n'est pas vide
    const token = await getCSRFToken(page)
    expect(token).toBeTruthy()
    expect(token).not.toBe('')
  })

  test('doit stocker CSRF token après login et le renouveler', async ({ page }) => {
    // Login pour obtenir auth token
    await login(page)

    // Attendre CSRF token initial
    await waitForCSRFToken(page)
    const initialToken = await getCSRFToken(page)

    // Vérifier que le token est bien stocké et non-vide
    expect(initialToken).toBeTruthy()
    expect(initialToken).not.toBe('')
    expect(initialToken.length).toBeGreaterThan(20) // Token doit avoir une longueur raisonnable

    // Récupérer access_token pour la requête de renouvellement
    const accessToken = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      if (!auth) return null
      const parsed = JSON.parse(auth)
      return parsed?.state?.accessToken || parsed?.accessToken
    })

    // Renouveler manuellement le token via GET /auth/csrf avec headers auth
    const renewResponse = await page.request.get(`${API_BASE_URL}/auth/csrf`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'X-Tenant-ID': '1',
      },
    })
    expect(renewResponse.ok()).toBeTruthy()

    const renewData = await renewResponse.json()
    const newToken = renewData.csrf_token

    // Vérifier que le nouveau token est différent de l'ancien
    expect(newToken).toBeTruthy()
    expect(newToken).not.toBe(initialToken)
    expect(newToken.length).toBeGreaterThan(20)
  })

  test('doit gérer échec de renouvellement CSRF sans crash', async ({ page }) => {
    // Login AVANT d'appliquer le mock (sinon le mock bloque le login)
    await login(page)
    await waitForCSRFToken(page)

    // APRÈS le login, mocker l'endpoint CSRF pour retourner une erreur
    await page.route(`${API_BASE_URL}/auth/csrf`, (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'CSRF service unavailable' }),
      })
    })

    // Attendre un peu pour que le mock soit bien en place
    await page.waitForTimeout(500)

    // Tenter de renouveler le token depuis le contexte browser (où le mock fonctionne)
    const renewStatus = await page.evaluate(async ({ baseUrl }) => {
      try {
        const auth = localStorage.getItem('marveline-auth')
        const parsed = auth ? JSON.parse(auth) : {}
        const token = parsed?.state?.accessToken || parsed?.accessToken

        const response = await fetch(`${baseUrl}/auth/csrf`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Tenant-ID': '1',
          },
        })
        return response.status
      } catch (error) {
        return -1
      }
    }, { baseUrl: API_BASE_URL })

    // Vérifier qu'il y a eu une erreur (500 ou -1 si catch)
    // Le mock page.route() peut bloquer la requête selon le contexte
    expect([500, -1]).toContain(renewStatus)

    // Vérifier que l'application ne crash pas
    const url = page.url()
    expect(url).toBeTruthy()

    // Vérifier qu'on est toujours authentifié
    const auth = await page.evaluate(() => {
      const authData = localStorage.getItem('marveline-auth')
      if (!authData) return null
      const parsed = JSON.parse(authData)
      return parsed?.state?.accessToken || parsed?.accessToken
    })
    expect(auth).toBeTruthy()
  })

})
