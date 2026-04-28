/**
 * Helpers et utilities pour tests E2E Playwright
 *
 * Fonctions communes pour :
 * - Authentication (login, logout)
 * - CSRF token handling
 * - MFA operations
 * - Session management
 * - Assertions communes
 */

import { expect, type Page } from '@playwright/test'
import * as OTPAuth from 'otpauth'

// ============================================================================
// Configuration & Constants
// ============================================================================

export const TEST_USER = {
  email: 'test@carocorp.com',
  password: 'testpass123',
  tenant_id: 1,
}

export const API_BASE_URL = 'http://localhost:8001/api/v1'
export const FRONTEND_BASE_URL = 'http://localhost:3002'

// ============================================================================
// Authentication Helpers
// ============================================================================

/**
 * Login utilisateur via formulaire UI
 */
export async function login(page: Page, email: string = TEST_USER.email, password: string = TEST_USER.password) {
  await page.goto('/login')
  await page.fill('input[name="email"]', email)
  await page.fill('input[name="password"]', password)
  await page.click('button[type="submit"]')

  // Attendre redirection après login réussi
  await page.waitForURL(/\/(dashboard|profile|agenda)/, { timeout: 5000 })
}

/**
 * Login utilisateur via API (plus rapide pour setup tests)
 */
export async function loginViaAPI(page: Page, email: string = TEST_USER.email, password: string = TEST_USER.password) {
  const response = await page.request.post(`${API_BASE_URL}/auth/login`, {
    form: {
      username: email,
      password: password,
    },
  })

  if (!response.ok()) {
    const errorText = await response.text()
    console.error(`[loginViaAPI] Login failed - Status: ${response.status()}, Body: ${errorText}`)
  }

  expect(response.ok()).toBeTruthy()
  const data = await response.json()

  // Stocker accessToken + isAuthenticated dans localStorage
  // NOTE: refreshToken est httpOnly (absent du JSON) — non stocké ici
  // _app.tsx:beforeLoad lit state.isAuthenticated pour le fallback localAuth
  await page.evaluate(
    ({ accessToken }) => {
      localStorage.setItem('marveline-auth', JSON.stringify({
        state: {
          isAuthenticated: true,
          accessToken: accessToken,
        },
        version: 0,
      }))
    },
    { accessToken: data.access_token }
  )

  // Naviguer et attendre que l'auth soit établie (cookie refresh → _doRefresh auto)
  await page.goto('/')
  await page.waitForURL(/\/(dashboard|profile|agenda)/, { timeout: 10000 })
}

/**
 * Logout utilisateur
 */
export async function logout(page: Page) {
  await page.click('[data-testid="user-menu"]', { timeout: 5000 })
  await page.click('text=Déconnexion')
  await page.waitForURL('/login', { timeout: 5000 })
}

/**
 * Vérifier que l'utilisateur est authentifié
 */
export async function expectAuthenticated(page: Page) {
  const isAuthenticated = await page.evaluate(() => {
    const authData = localStorage.getItem('marveline-auth')
    if (!authData) return false
    const parsed = JSON.parse(authData)
    // Zustand persist: { state: { isAuthenticated: true, ... }, version: 0 }
    return !!parsed?.state?.isAuthenticated
  })

  expect(isAuthenticated).toBe(true)
}

/**
 * Vérifier que l'utilisateur n'est PAS authentifié
 */
export async function expectNotAuthenticated(page: Page) {
  const auth = await page.evaluate(() => {
    return localStorage.getItem('marveline-auth')
  })

  expect(auth).toBeNull()
}

// ============================================================================
// CSRF Helpers
// ============================================================================

/**
 * Attendre que le CSRF token soit fetch et stocké
 */
export async function waitForCSRFToken(page: Page, timeout: number = 5000) {
  await page.waitForFunction(
    () => {
      const ui = localStorage.getItem('marveline-ui')
      if (!ui) return false
      const parsed = JSON.parse(ui)
      // Zustand persist format: {state: {...}, version: 0}
      return !!parsed?.state?.csrfToken || !!parsed?.csrfToken
    },
    { timeout }
  )
}

/**
 * Récupérer le CSRF token actuel depuis localStorage
 */
export async function getCSRFToken(page: Page): Promise<string | null> {
  return await page.evaluate(() => {
    const ui = localStorage.getItem('marveline-ui')
    if (!ui) return null
    const parsed = JSON.parse(ui)
    // Zustand persist format: {state: {...}, version: 0}
    return parsed?.state?.csrfToken || parsed?.csrfToken || null
  })
}

/**
 * Retourne les headers API complets (Authorization + CSRF + Content-Type)
 * À utiliser dans tous les appels page.request.post/put/delete.
 *
 * NOTE: appelle toujours GET /auth/csrf pour obtenir un token CSRF frais car
 * le CSRF en localStorage peut être invalidé par Redis FLUSHDB dans les beforeEach.
 */
export async function getApiHeaders(page: Page): Promise<Record<string, string>> {
  const token = await page.evaluate(() => {
    const raw = localStorage.getItem('marveline-auth')
    if (!raw) return ''
    const parsed = JSON.parse(raw)
    return parsed?.state?.accessToken || parsed?.accessToken || ''
  })

  // Toujours obtenir un CSRF frais via API (le localStorage peut être obsolète après Redis FLUSHDB)
  let csrfToken = ''
  if (token) {
    try {
      const csrfResp = await page.request.get(`${API_BASE_URL}/auth/csrf`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (csrfResp.ok()) {
        const csrfData = await csrfResp.json()
        csrfToken = csrfData.csrf_token || ''
      }
    } catch { /* pas de CSRF si erreur */ }
  }

  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-CSRF-Token': csrfToken,
  }
}

/**
 * Forcer un renouvellement du CSRF token
 */
export async function renewCSRFToken(page: Page) {
  await page.evaluate(() => {
    const ui = localStorage.getItem('marveline-ui')
    if (ui) {
      const parsed = JSON.parse(ui)
      parsed.csrfToken = null
      localStorage.setItem('marveline-ui', JSON.stringify(parsed))
    }
  })

  // Déclencher un fetch (n'importe quelle requête GET)
  await page.request.get(`${API_BASE_URL}/auth/csrf`)
}

// ============================================================================
// MFA Helpers
// ============================================================================

/**
 * Générer un code TOTP valide basé sur un secret
 * @param secret - Secret TOTP en base32 (retourné par POST /mfa/setup)
 * @returns Code TOTP à 6 chiffres valide pour le window courant (30s)
 *
 * Utilise otpauth qui est compatible avec pyotp (backend)
 * Les deux suivent strictement RFC 6238
 */
export function generateTOTPCode(secret: string): string {
  const totp = new OTPAuth.TOTP({
    algorithm: 'SHA1',
    digits: 6,
    period: 30,
    secret: OTPAuth.Secret.fromBase32(secret),
  })
  return totp.generate()
}

/**
 * Attendre le début du prochain window TOTP (max 30s)
 * Utile pour éviter les rejets anti-replay quand on génère plusieurs codes
 */
export async function waitForNextTOTPWindow(): Promise<void> {
  const now = Math.floor(Date.now() / 1000)
  const timeInCurrentWindow = now % 30
  const timeUntilNextWindow = 30 - timeInCurrentWindow

  console.log(`[waitForNextTOTPWindow] Attente ${timeUntilNextWindow}s pour nouveau window TOTP...`)

  // Ajouter 1s de marge pour être sûr
  await new Promise(resolve => setTimeout(resolve, (timeUntilNextWindow + 1) * 1000))
}

/**
 * Setup MFA pour utilisateur de test
 */
export async function setupMFA(page: Page): Promise<{ secret: string; qrCode: string }> {
  await page.goto('/profile')
  await page.click('text=Activer MFA')

  // Attendre que le QR code soit affiché
  await page.waitForSelector('[data-testid="mfa-qr-code"]', { timeout: 5000 })

  const secret = await page.textContent('[data-testid="mfa-secret"]')
  const qrCode = await page.getAttribute('[data-testid="mfa-qr-code"]', 'src')

  return {
    secret: secret || '',
    qrCode: qrCode || '',
  }
}

/**
 * Enable MFA avec code TOTP
 */
export async function enableMFA(page: Page, totpCode: string) {
  await page.fill('input[name="totp-code"]', totpCode)
  await page.click('button:has-text("Confirmer")')

  // Attendre confirmation
  await page.waitForSelector('text=MFA activé avec succès', { timeout: 5000 })
}

/**
 * Disable MFA (via UI)
 */
export async function disableMFA(page: Page, password: string, totpCode: string) {
  await page.goto('/profile')
  await page.click('text=Désactiver MFA')

  await page.fill('input[name="password"]', password)
  await page.fill('input[name="totp-code"]', totpCode)
  await page.click('button:has-text("Désactiver")')

  // Attendre confirmation
  await page.waitForSelector('text=MFA désactivé avec succès', { timeout: 5000 })
}

/**
 * Cleanup MFA (via API) - pour beforeEach dans tests
 * Désactive MFA si activé, ignore l'erreur sinon
 */
export async function cleanupMFA(page: Page, email: string = TEST_USER.email, password: string = TEST_USER.password) {
  try {
    // Obtenir access_token via login API
    const loginResponse = await page.request.post(`${API_BASE_URL}/auth/login`, {
      form: {
        username: email,
        password: password,
      },
    })

    if (!loginResponse.ok()) {
      console.warn('[cleanupMFA] Login failed:', await loginResponse.text())
      return
    }

    const loginData = await loginResponse.json()
    const accessToken = loginData.access_token

    // Désactiver MFA via DELETE /mfa
    const disableResponse = await page.request.delete(`${API_BASE_URL}/mfa`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    })

    // 200 = désactivé, 400 = pas activé (OK), autre = erreur
    if (disableResponse.status() === 200) {
      console.log('[cleanupMFA] MFA désactivé avec succès')
    } else if (disableResponse.status() === 400) {
      console.log('[cleanupMFA] MFA déjà désactivé')
    } else {
      console.warn('[cleanupMFA] Erreur inattendue:', disableResponse.status(), await disableResponse.text())
    }
  } catch (error) {
    console.warn('[cleanupMFA] Exception:', error)
  }
}

// ============================================================================
// Session Helpers
// ============================================================================

/**
 * Récupérer toutes les sessions actives
 */
export async function getSessions(page: Page) {
  await page.goto('/admin/sessions')
  await page.waitForSelector('[data-testid="sessions-list"]', { timeout: 5000 })

  return await page.$$('[data-testid="session-item"]')
}

/**
 * Terminer une session spécifique
 */
export async function terminateSession(page: Page, sessionId: string) {
  await page.goto('/admin/sessions')
  await page.click(`[data-session-id="${sessionId}"] button:has-text("Terminer")`)

  // Attendre confirmation
  await page.waitForSelector('text=Session terminée', { timeout: 5000 })
}

// ============================================================================
// Toast & Notification Helpers
// ============================================================================

/**
 * Attendre qu'un toast success apparaisse
 */
export async function expectToastSuccess(page: Page, message?: string) {
  const toast = page.locator('[data-testid="toast-success"]')
  await expect(toast).toBeVisible({ timeout: 5000 })

  if (message) {
    await expect(toast).toContainText(message)
  }
}

/**
 * Attendre qu'un toast error apparaisse
 */
export async function expectToastError(page: Page, message?: string) {
  const toast = page.locator('[data-testid="toast-error"]')
  await expect(toast).toBeVisible({ timeout: 5000 })

  if (message) {
    await expect(toast).toContainText(message)
  }
}

// ============================================================================
// API Mocking Helpers
// ============================================================================

/**
 * Mock une réponse API pour tests
 */
export async function mockAPIResponse(page: Page, url: string, response: any, status: number = 200) {
  await page.route(url, (route) => {
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(response),
    })
  })
}

/**
 * Mock une erreur API
 */
export async function mockAPIError(page: Page, url: string, status: number = 500, message: string = 'Internal Server Error') {
  await page.route(url, (route) => {
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify({ detail: message }),
    })
  })
}

// ============================================================================
// Wait & Retry Helpers
// ============================================================================

/**
 * Attendre que le backend soit prêt (healthcheck)
 */
export async function waitForBackend(timeout: number = 30000) {
  const start = Date.now()

  while (Date.now() - start < timeout) {
    try {
      const response = await fetch(`${API_BASE_URL}/health`)
      if (response.ok) return true
    } catch (error) {
      // Backend pas encore prêt, retry
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }

  throw new Error('Backend ne répond pas après ' + timeout + 'ms')
}

/**
 * Retry une fonction jusqu'à succès ou timeout
 */
export async function retry<T>(
  fn: () => Promise<T>,
  options: { maxRetries?: number; delay?: number } = {}
): Promise<T> {
  const { maxRetries = 3, delay = 1000 } = options

  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn()
    } catch (error) {
      if (i === maxRetries - 1) throw error
      await new Promise((resolve) => setTimeout(resolve, delay))
    }
  }

  throw new Error('Max retries exceeded')
}
