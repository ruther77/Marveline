/**
 * Tests E2E pour MFA (Multi-Factor Authentication) Flow
 *
 * Couvre :
 * - Setup MFA : générer secret TOTP + QR code + backup codes
 * - Verify setup : activer MFA avec code TOTP valide
 * - Login avec MFA : flow 2 étapes (login → mfa_session_token → verify → JWT tokens)
 * - Verify TOTP invalide : erreur si code incorrect
 * - Disable MFA : désactiver MFA avec code TOTP
 * - Backup codes : affichage et stockage après activation
 */

import { test, expect } from '@playwright/test'
import {
  login,
  loginViaAPI,
  waitForCSRFToken,
  generateTOTPCode,
  waitForNextTOTPWindow,
  cleanupMFA,
  API_BASE_URL,
  TEST_USER,
} from './setup'

test.describe('MFA Flow', () => {
  test.beforeEach(async ({ page, context }) => {
    // Cleanup MFA via DB AVANT chaque test pour éviter interdépendance
    // Utilise dynamic import (ESM) au lieu de require (CommonJS)
    const { execSync } = await import('node:child_process')

    try {
      execSync(
        `docker compose exec -T db psql -U caro -d CaroCorp -c "DELETE FROM mfa_devices WHERE user_id = (SELECT id FROM users WHERE email = 'test@carocorp.com' AND tenant_id = 1);"`,
        { stdio: 'ignore' }
      )
      console.log('[beforeEach] MFA cleanup successful')
    } catch (error) {
      console.warn('[beforeEach] MFA cleanup failed:', error)
      // Ne pas fail le test si cleanup échoue
    }

    // Réinitialiser TOUTES les données Redis pour éviter rate limit exceeded et autres cache
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

  test('doit afficher QR code et secret après setup MFA', async ({ page }) => {
    // Login via API (évite rate limiting)
    await loginViaAPI(page)

    // Attendre CSRF token (nécessaire pour POST /mfa/setup)
    await waitForCSRFToken(page)

    // Naviguer vers page MFA setup
    await page.goto('/profile/mfa')

    // Cliquer sur bouton "Configurer 2FA" (pas "Activer MFA")
    await page.click('button:has-text("Configurer 2FA")')

    // Attendre que le QR code soit affiché (svg dans div bg-white)
    await page.waitForSelector('.bg-white svg', { timeout: 5000 })

    // Vérifier que le secret TOTP est affiché (dans un <code> element)
    const secretElement = page.locator('code.font-mono')
    await expect(secretElement).toBeVisible()

    const secretText = await secretElement.textContent()
    expect(secretText).toBeTruthy()
    expect(secretText!.trim().length).toBeGreaterThanOrEqual(16) // Secret base32 minimal

    // Vérifier que le QR code (svg) est affiché
    const qrCode = page.locator('.bg-white svg')
    await expect(qrCode).toBeVisible()

    // Vérifier que le titre "Configurer 2FA" est présent
    await expect(page.locator('text=Configurer 2FA')).toBeVisible()
  })

  test('doit activer MFA après verify setup avec code TOTP valide', async ({ page }) => {
    // Écouter TOUS les messages console du navigateur
    page.on('console', (msg) => {
      console.log(`[BROWSER ${msg.type()}] ${msg.text()}`)
    })

    // Écouter les requêtes réseau pour capturer le payload MFA
    page.on('request', (request) => {
      if (request.url().includes('/mfa/verify-setup')) {
        console.log('[NETWORK REQUEST] URL:', request.url())
        console.log('[NETWORK REQUEST] Method:', request.method())
        console.log('[NETWORK REQUEST] Headers:', JSON.stringify(request.headers()))
        console.log('[NETWORK REQUEST] Post Data:', request.postData())
      }
    })

    page.on('response', async (response) => {
      if (response.url().includes('/mfa/verify-setup')) {
        console.log('[NETWORK RESPONSE] URL:', response.url())
        console.log('[NETWORK RESPONSE] Status:', response.status())
        const body = await response.text().catch(() => 'Could not read body')
        console.log('[NETWORK RESPONSE] Body:', body)
      }
    })

    // Login via API (évite rate limiting)
    await loginViaAPI(page)
    await waitForCSRFToken(page)

    // Setup MFA et récupérer secret
    await page.goto('/profile/mfa')
    await page.click('button:has-text("Configurer 2FA")')
    await page.waitForSelector('code.font-mono', { timeout: 5000 })

    const secretText = await page.locator('code.font-mono').textContent()
    // Nettoyer le secret: enlever tous les espaces, retours à la ligne, etc.
    const secret = secretText!.trim().replace(/\s/g, '')

    // DEBUG: Logger le secret
    console.log(`[DEBUG] Secret récupéré: "${secretText}"`)
    console.log(`[DEBUG] Secret nettoyé: "${secret}"`)

    // IMPORTANT: Générer le code JUSTE AVANT de soumettre pour éviter expiration
    const totpCode = generateTOTPCode(secret)
    console.log(`[DEBUG] Code TOTP généré: ${totpCode}`)

    // Entrer et soumettre immédiatement
    await page.fill('input[placeholder="000000"]', totpCode)
    await page.click('button:has-text("Activer 2FA")')

    // Attendre confirmation (backup codes affichés)
    await page.waitForSelector('text=Sauvegardez ces codes de récupération', { timeout: 5000 })

    // Vérifier que 8 backup codes sont affichés
    const backupCodes = await page.locator('.grid.grid-cols-2 > div').count()
    expect(backupCodes).toBe(8)

    // Vérifier que le statut MFA est "activé"
    await page.goto('/profile/mfa')
    await page.waitForSelector('text=2FA activé', { timeout: 5000 })
  })

  test('doit compléter login avec MFA (flow 2 étapes)', async ({ page }) => {
    // Prerequisite: Setup et enable MFA pour test user
    // (Ce test suppose que MFA est déjà activé pour test@carocorp.com)
    // En pratique, on pourrait faire le setup dans beforeAll ou via API

    // Note: Pour ce test, on va d'abord activer MFA, puis logout, puis login avec MFA

    // === PARTIE 1: Activer MFA ===
    await loginViaAPI(page)
    await waitForCSRFToken(page)

    await page.goto('/profile/mfa')
    await page.click('button:has-text("Configurer 2FA")')
    await page.waitForSelector('code.font-mono', { timeout: 5000 })

    const secretText = await page.locator('code.font-mono').textContent()
    // Nettoyer le secret: enlever tous les espaces, retours à la ligne, etc.
    const secret = secretText!.trim().replace(/\s/g, '')

    const setupCode = generateTOTPCode(secret)
    await page.fill('input[placeholder="000000"]', setupCode)
    await page.click('button:has-text("Activer 2FA")')

    // Attendre confirmation
    await page.waitForSelector('text=Sauvegardez ces codes de récupération', { timeout: 5000 })

    // === PARTIE 2: Logout ===
    await page.goto('/profile')
    await page.click('button:has-text("Deconnexion")')
    await page.waitForURL('/login', { timeout: 5000 })

    // Nettoyer localStorage pour simuler nouveau login
    await page.evaluate(() => {
      localStorage.clear()
      sessionStorage.clear()
    })

    // === PARTIE 3: Login avec MFA ===
    await page.goto('/login')
    await page.fill('input[name="email"]', TEST_USER.email)
    await page.fill('input[name="password"]', TEST_USER.password)
    await page.click('button[type="submit"]')

    // Attendre redirection vers page MFA verify
    await page.waitForURL('/mfa/verify', { timeout: 5000 })

    // Vérifier que mfa_session_token est dans localStorage
    const mfaSessionToken = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      if (!auth) return null
      const parsed = JSON.parse(auth)
      return parsed?.state?.mfaSessionToken || parsed?.mfaSessionToken
    })

    expect(mfaSessionToken).toBeTruthy()

    // Attendre nouveau window TOTP pour éviter anti-replay (setupCode utilisé précédemment)
    await waitForNextTOTPWindow()

    // Générer nouveau code TOTP (valide pour ce window)
    const loginCode = generateTOTPCode(secret)

    // Entrer le code TOTP (inputs séparés)
    for (let i = 0; i < 6; i++) {
      await page.fill(`input[data-index="${i}"]`, loginCode[i])
    }

    // Le code devrait être auto-submit après les 6 chiffres
    // Attendre redirection vers dashboard
    await page.waitForURL(/\/(dashboard|profile|agenda)/, { timeout: 5000 })

    // Vérifier que les tokens JWT sont présents
    const tokens = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      if (!auth) return null
      const parsed = JSON.parse(auth)
      return {
        accessToken: parsed?.state?.accessToken || parsed?.accessToken,
        refreshToken: parsed?.state?.refreshToken || parsed?.refreshToken,
      }
    })

    expect(tokens?.accessToken).toBeTruthy()
    expect(tokens?.refreshToken).toBeTruthy()
  })

  test('doit rejeter code TOTP invalide pendant verify setup', async ({ page }) => {
    // Login via API et setup MFA (évite rate limiting)
    await loginViaAPI(page)
    await waitForCSRFToken(page)

    await page.goto('/profile/mfa')
    await page.click('button:has-text("Configurer 2FA")')
    await page.waitForSelector('code.font-mono', { timeout: 5000 })

    // Entrer un code TOTP invalide (000000)
    await page.fill('input[placeholder="000000"]', '000000')
    await page.click('button:has-text("Activer 2FA")')

    // Attendre message d'erreur (affichée par enableMutation.error)
    await page.waitForSelector('text=Invalid TOTP code', { timeout: 5000 })

    // Vérifier que le MFA n'est pas activé
    await page.goto('/profile/mfa')
    const statusText = await page.textContent('body')
    expect(statusText).not.toContain('2FA activé')
  })

  test('doit désactiver MFA avec code TOTP valide', async ({ page }) => {
    // Prerequisite: Activer MFA (login via API pour éviter rate limiting)
    await loginViaAPI(page)
    await waitForCSRFToken(page)

    await page.goto('/profile/mfa')
    await page.click('button:has-text("Configurer 2FA")')
    await page.waitForSelector('code.font-mono', { timeout: 5000 })

    const secretText = await page.locator('code.font-mono').textContent()
    // Nettoyer le secret: enlever tous les espaces, retours à la ligne, etc.
    const secret = secretText!.trim().replace(/\s/g, '')

    const setupCode = generateTOTPCode(secret)
    await page.fill('input[placeholder="000000"]', setupCode)
    await page.click('button:has-text("Activer 2FA")')
    await page.waitForSelector('text=Sauvegardez ces codes de récupération', { timeout: 5000 })

    // Revenir à la page MFA
    await page.goto('/profile/mfa')
    await page.waitForSelector('text=2FA activé', { timeout: 5000 })

    // Le form de désactivation est déjà visible (pas de bouton séparé)
    // Entrer code TOTP de confirmation dans le form visible
    // Note: Pas besoin d'attendre 31s si le cleanup DB réinitialise last_totp_window
    const disableCode = generateTOTPCode(secret)

    // L'input est dans le form de désactivation, chercher par placeholder
    await page.fill('input[placeholder="000000"]:visible', disableCode)
    await page.click('button:has-text("Désactiver 2FA")')

    // Attendre que le statut change (toast ou changement d'état)
    await page.waitForTimeout(2000)

    // Vérifier que le statut MFA est désactivé en vérifiant que le bouton "Configurer 2FA" réapparaît
    await page.reload()
    await page.waitForSelector('button:has-text("Configurer 2FA")', { timeout: 5000 })
  })

  test('doit afficher 8 codes de récupération après activation MFA', async ({ page }) => {
    // Login et activer MFA (login via API pour éviter rate limiting)
    await loginViaAPI(page)
    await waitForCSRFToken(page)

    await page.goto('/profile/mfa')
    await page.click('button:has-text("Configurer 2FA")')
    await page.waitForSelector('code.font-mono', { timeout: 5000 })

    const secretText = await page.locator('code.font-mono').textContent()
    // Nettoyer le secret: enlever tous les espaces, retours à la ligne, etc.
    const secret = secretText!.trim().replace(/\s/g, '')

    const setupCode = generateTOTPCode(secret)
    await page.fill('input[placeholder="000000"]', setupCode)
    await page.click('button:has-text("Activer 2FA")')

    // Attendre affichage des backup codes
    await page.waitForSelector('text=Sauvegardez ces codes de récupération', { timeout: 5000 })

    // Vérifier qu'il y a exactement 8 codes (divs dans grid grid-cols-2)
    const backupCodesElements = await page.locator('.grid.grid-cols-2 > div').all()
    expect(backupCodesElements.length).toBe(8)

    // Vérifier que chaque code a le bon format (au moins 8 caractères)
    for (const element of backupCodesElements) {
      const codeText = await element.textContent()
      expect(codeText).toBeTruthy()
      expect(codeText!.trim().length).toBeGreaterThanOrEqual(8) // Au moins 8 caractères
    }

    // Vérifier que le bouton "Copier les codes" est présent
    const copyButton = page.locator('button:has-text("Copier les codes")')
    await expect(copyButton).toBeVisible()
  })
})
