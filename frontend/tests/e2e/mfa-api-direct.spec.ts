/**
 * Test MFA en appelant directement l'API (sans UI)
 *
 * Ce test bypass complètement le frontend React pour isoler le problème.
 * Si ce test passe, le problème est dans l'UI.
 * Si ce test échoue, le problème est dans la communication HTTP ou le backend.
 */

import { test, expect } from '@playwright/test'
import {
  login,
  generateTOTPCode,
  API_BASE_URL,
} from './setup'

test.describe('MFA API Direct (bypass UI)', () => {
  test.beforeEach(async ({ page, context }) => {
    await context.clearCookies()
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })
  })

  test('doit activer MFA via appels API directs (pas UI)', async ({ page, request }) => {
    // Login pour obtenir access token
    await login(page)

    // Récupérer access token depuis localStorage
    const accessToken = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      if (!auth) return null
      const parsed = JSON.parse(auth)
      return parsed?.state?.accessToken || parsed?.accessToken
    })

    expect(accessToken).toBeTruthy()

    // Récupérer CSRF token
    const csrfResponse = await request.get(`${API_BASE_URL}/auth/csrf`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    })
    expect(csrfResponse.ok()).toBeTruthy()
    const csrfData = await csrfResponse.json()
    const csrfToken = csrfData.csrf_token

    console.log('[DEBUG] CSRF token:', csrfToken)

    // ========================================================================
    // ÉTAPE 1: POST /mfa/setup (générer secret + QR code)
    // ========================================================================
    console.log('\n=== ÉTAPE 1: POST /mfa/setup ===')

    const setupResponse = await request.post(`${API_BASE_URL}/mfa/setup`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'X-CSRF-Token': csrfToken,
        'Content-Type': 'application/json',
      },
    })

    console.log(`Status: ${setupResponse.status()}`)
    const setupData = await setupResponse.json()
    console.log(`Response keys: ${Object.keys(setupData).join(', ')}`)

    expect(setupResponse.status()).toBe(200)
    expect(setupData.secret).toBeTruthy()
    expect(setupData.provisioning_uri).toBeTruthy()
    expect(setupData.recovery_codes).toBeTruthy()
    expect(setupData.recovery_codes.length).toBe(8)

    const secret = setupData.secret.trim()
    console.log(`[DEBUG] Secret retourné: "${secret}"`)
    console.log(`[DEBUG] Longueur: ${secret.length} caractères`)

    // Vérifier format Base32 (A-Z, 2-7, pas d'espaces)
    const isValidBase32 = /^[A-Z2-7]+$/.test(secret)
    console.log(`[DEBUG] Format Base32 valide: ${isValidBase32}`)
    expect(isValidBase32).toBeTruthy()

    // ========================================================================
    // ÉTAPE 2: Générer code TOTP avec otpauth (comme le frontend)
    // ========================================================================
    console.log('\n=== ÉTAPE 2: Générer code TOTP ===')

    const totpCode = generateTOTPCode(secret)
    console.log(`[DEBUG] Code TOTP généré: ${totpCode}`)
    console.log(`[DEBUG] Timestamp: ${Math.floor(Date.now() / 1000)}`)
    console.log(`[DEBUG] Window: ${Math.floor(Date.now() / 1000 / 30)}`)

    // Vérifier format code (6 chiffres)
    expect(totpCode).toMatch(/^\d{6}$/)

    // ========================================================================
    // ÉTAPE 3: POST /mfa/verify-setup (activer MFA)
    // ========================================================================
    console.log('\n=== ÉTAPE 3: POST /mfa/verify-setup ===')

    const verifyResponse = await request.post(`${API_BASE_URL}/mfa/verify-setup`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'X-CSRF-Token': csrfToken,
        'Content-Type': 'application/json',
      },
      data: {
        totp_code: totpCode,
      },
    })

    console.log(`Status: ${verifyResponse.status()}`)
    const responseText = await verifyResponse.text()
    console.log(`Response body: ${responseText}`)

    if (!verifyResponse.ok()) {
      console.error('[ERROR] Verify setup failed!')
      console.error(`Status: ${verifyResponse.status()}`)
      console.error(`Body: ${responseText}`)

      // Parser response si JSON
      try {
        const errorData = JSON.parse(responseText)
        console.error(`Error detail: ${errorData.detail}`)
      } catch (e) {
        // Not JSON
      }
    }

    expect(verifyResponse.status()).toBe(200)

    const verifyData = JSON.parse(responseText)
    expect(verifyData.enabled).toBe(true)
    expect(verifyData.message).toBeTruthy()

    console.log('[SUCCESS] MFA activé avec succès via API directe!')

    // ========================================================================
    // ÉTAPE 4: Vérifier statut MFA
    // ========================================================================
    console.log('\n=== ÉTAPE 4: GET /mfa/status ===')

    const statusResponse = await request.get(`${API_BASE_URL}/mfa/status`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    })

    expect(statusResponse.ok()).toBeTruthy()
    const statusData = await statusResponse.json()

    console.log(`MFA enabled: ${statusData.mfa_enabled}`)
    console.log(`Recovery codes remaining: ${statusData.recovery_codes_remaining}`)

    expect(statusData.mfa_enabled).toBe(true)
    expect(statusData.recovery_codes_remaining).toBe(8)

    // ========================================================================
    // CLEANUP: Désactiver MFA
    // ========================================================================
    console.log('\n=== CLEANUP: DELETE /mfa ===')

    await request.delete(`${API_BASE_URL}/mfa`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'X-CSRF-Token': csrfToken,
      },
    })
  })
})
