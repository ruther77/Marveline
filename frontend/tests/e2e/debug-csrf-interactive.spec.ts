/**
 * Test E2E interactif pour déboguer le CSRF token fetch
 *
 * Ce test ouvre le navigateur, fait un login, puis PAUSE pour permettre
 * l'inspection manuelle avec DevTools.
 *
 * Utilisation :
 * npx playwright test debug-csrf-interactive.spec.ts --headed --debug
 *
 * Ou :
 * npx playwright test debug-csrf-interactive.spec.ts --headed
 *
 * Ce qui vérifie :
 * 1. Console logs : voir les logs [authStore] et [uiStore]
 * 2. Network tab : voir si GET /csrf-token est appelé
 * 3. Application > Local Storage : voir si marveline-ui.csrfToken existe
 * 4. Sources tab : breakpoints dans uiStore.fetchCsrfToken()
 */

import { test, expect } from '@playwright/test'
import { login, API_BASE_URL } from './setup'

test.describe('CSRF Debug Interactif', () => {
  test('Login et inspection CSRF token', async ({ page }) => {
    // Activer console logs
    page.on('console', (msg) => {
      const text = msg.text()
      if (text.includes('[authStore]') || text.includes('[uiStore]') || text.includes('CSRF')) {
        console.log('BROWSER CONSOLE:', text)
      }
    })

    // Tracker les requêtes réseau
    const requests: string[] = []
    page.on('request', (req) => {
      const url = req.url()
      if (url.includes('csrf') || url.includes('login') || url.includes('me')) {
        const method = req.method()
        requests.push(`${method} ${url}`)
        console.log(`NETWORK REQUEST: ${method} ${url}`)
      }
    })

    page.on('response', (res) => {
      const url = res.url()
      if (url.includes('csrf') || url.includes('login') || url.includes('me')) {
        const status = res.status()
        console.log(`NETWORK RESPONSE: ${status} ${url}`)
      }
    })

    // Nettoyer localStorage avant test
    await page.goto('/')
    await page.evaluate(() => {
      localStorage.clear()
      console.log('[TEST] localStorage cleared')
    })

    console.log('\n=== ÉTAPE 1: LOGIN ===')
    // Login via UI pour déclencher le flow complet
    await login(page)

    console.log('\n=== ÉTAPE 2: ATTENDRE STABILISATION ===')
    // Attendre un peu pour laisser les stores s'initialiser
    await page.waitForTimeout(2000)

    console.log('\n=== ÉTAPE 3: INSPECTER L\'ÉTAT ===')
    // Vérifier l'état actuel
    const authState = await page.evaluate(() => {
      const auth = localStorage.getItem('marveline-auth')
      return auth ? JSON.parse(auth) : null
    })

    const uiState = await page.evaluate(() => {
      const ui = localStorage.getItem('marveline-ui')
      return ui ? JSON.parse(ui) : null
    })

    console.log('AuthStore localStorage:', JSON.stringify(authState, null, 2))
    console.log('UIStore localStorage:', JSON.stringify(uiState, null, 2))
    console.log('Requêtes réseau capturées:', requests)

    console.log('\n=== ÉTAPE 4: PAUSE POUR INSPECTION MANUELLE ===')
    console.log('Le navigateur est maintenant en pause.')
    console.log('Ouvrez DevTools et inspectez :')
    console.log('  1. Console : logs [authStore] et [uiStore]')
    console.log('  2. Network : cherchez GET /csrf-token')
    console.log('  3. Application > Local Storage > http://localhost:3002')
    console.log('     - Vérifiez marveline-auth.state.accessToken')
    console.log('     - Vérifiez marveline-ui.csrfToken')
    console.log('  4. Sources : mettez un breakpoint dans stores/uiStore.ts fetchCsrfToken()')
    console.log('\nAppuyez sur F8 ou cliquez sur Resume pour continuer.')

    // PAUSE pour inspection manuelle
    await page.pause()

    console.log('\n=== ÉTAPE 5: VÉRIFICATIONS POST-PAUSE ===')
    // Après la pause, vérifier si le token est là
    const finalUiState = await page.evaluate(() => {
      const ui = localStorage.getItem('marveline-ui')
      return ui ? JSON.parse(ui) : null
    })

    console.log('État final UIStore:', JSON.stringify(finalUiState, null, 2))

    // Ne pas faire d'assertion stricte, c'est juste pour debug
    if (finalUiState?.csrfToken || finalUiState?.state?.csrfToken) {
      console.log('✅ CSRF token trouvé après inspection!')
    } else {
      console.log('❌ CSRF token toujours absent après inspection')
    }
  })

  test('Forcer fetchCsrfToken manuellement', async ({ page }) => {
    console.log('\n=== TEST: FORCER FETCH CSRF MANUELLEMENT ===')

    // Setup : login et attendre
    await page.goto('/')
    await page.evaluate(() => localStorage.clear())
    await login(page)
    await page.waitForTimeout(1000)

    console.log('AVANT: Vérifier état localStorage')
    let uiState = await page.evaluate(() => {
      const ui = localStorage.getItem('marveline-ui')
      return ui ? JSON.parse(ui) : null
    })
    console.log('UIStore avant appel manuel:', JSON.stringify(uiState, null, 2))

    console.log('\nAPPEL MANUEL: fetchCsrfToken()')
    // Appeler manuellement fetchCsrfToken depuis la console
    await page.evaluate(() => {
      const { useUIStore } = window as {
        useUIStore?: {
          getState: () => {
            fetchCsrfToken: () => Promise<unknown> | void
          }
        }
      }
      if (useUIStore) {
        console.log('[TEST] Appel manuel de fetchCsrfToken()')
        useUIStore.getState().fetchCsrfToken()
      } else {
        console.error('[TEST] useUIStore non accessible!')
      }
    })

    console.log('ATTENTE: 3 secondes pour la requête réseau')
    await page.waitForTimeout(3000)

    console.log('\nAPRES: Vérifier état localStorage')
    uiState = await page.evaluate(() => {
      const ui = localStorage.getItem('marveline-ui')
      return ui ? JSON.parse(ui) : null
    })
    console.log('UIStore après appel manuel:', JSON.stringify(uiState, null, 2))

    if (uiState?.csrfToken || uiState?.state?.csrfToken) {
      console.log('✅ Appel manuel réussi!')
    } else {
      console.log('❌ Appel manuel aussi échoué')
    }

    // Pause pour inspection
    await page.pause()
  })
})
