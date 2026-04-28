/**
 * Démo commerciale Le Splendid Events — Scénario desktop bout-en-bout.
 *
 * 4 actes (~3 min) :
 *   1. Login + wizard 5 étapes (devis 8 articles)
 *   2. Send → Accept → Conversion (avec dates J-1/J/J+1 auto-déduites)
 *   3. Vue résa + modale avenant teasing
 *   4. Constat de retour (3 chaises endommagées + 1 colonne manquante)
 *      → bascule auto litige + journal append-only + clôture
 *
 * Pré-requis : tenant Splendid seed (id=5), devis & résa précédentes
 * supprimées avant lancement.
 *
 * Différenciateurs Lokki montrés :
 *   - Versioning devis (snapshot pre-conversion auto)
 *   - Avenant tracé (modale "Modifier le périmètre")
 *   - Constat ligne par ligne avec bascule auto litige
 *   - Journal append-only (open / note / charge / resolved)
 */

import { test, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'

const EMAIL = 'demo@lesplendidevent.fr'
const PWD = 'DemoSplendid2026!'

const PRODUCTS = [
  { name: 'Chaise Napoleon Blanche', qty: 100 },
  { name: 'Nappe ronde blanche', qty: 12 },
  { name: 'Arche hexagonale', qty: 1 },
  { name: 'Chemin de table vert sauge', qty: 12 },
  { name: 'Pupitre bois', qty: 1 },
  { name: 'Colonne gold', qty: 4 },
  { name: 'Toile cirque', qty: 2 },
  { name: 'Projecteur Par Led sur Batterie', qty: 6 },
]

async function pause(page: import('@playwright/test').Page, ms: number) {
  await page.waitForTimeout(ms)
}

/**
 * Scroll fluide de haut en bas de la page jusqu'au bout du contenu, puis remontée.
 * Permet à la vidéo de capturer l'intégralité de la page (pas juste le viewport initial).
 */
async function scrollFullPage(page: import('@playwright/test').Page) {
  // récupère la hauteur totale du document
  const totalHeight = await page.evaluate(() =>
    Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
  )
  const viewportHeight = await page.evaluate(() => window.innerHeight)
  const stepPx = Math.round(viewportHeight * 0.7) // 70 % du viewport pour que le regard suive
  let current = 0
  while (current < totalHeight - viewportHeight) {
    current = Math.min(current + stepPx, totalHeight - viewportHeight)
    await page.evaluate((y) => window.scrollTo({ top: y, behavior: 'smooth' }), current)
    await page.waitForTimeout(900)
  }
  await page.waitForTimeout(700)
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
  await page.waitForTimeout(900)
}

test.describe('Démo Splendid Events — devis vivant + retour litigieux', () => {
  test('parcours bout-en-bout', async ({ page }) => {
    // ── Acte 0 : Login ──────────────────────────────────────────────────────
    await page.goto('login')
    await pause(page, 800)

    await page.locator('input[type="email"]').fill(EMAIL)
    await page.locator('input[type="password"]').fill(PWD)
    await pause(page, 500)
    await page.locator('button[type="submit"]').click()

    await page.waitForURL(/\/dashboard/, { timeout: 15000 })
    // Laisser voir le dashboard (KPIs, raccourci Nouveau devis)
    await pause(page, 3000)

    // ── Acte 1 : Wizard devis ───────────────────────────────────────────────
    await page.goto('devis/new?step=1')
    await pause(page, 1500)

    // Étape 1 — client
    const clientSearch = page.locator('input[placeholder*="client"]').first()
    await clientSearch.fill('Demo')
    await pause(page, 800)
    await page.getByRole('button', { name: /Demo Client/ }).first().click()
    await pause(page, 600)

    // lieu
    await page.locator('input[placeholder*="Adresse"]').fill('Domaine du Mas - Aix-en-Provence')
    await pause(page, 500)
    await page.getByRole('button', { name: 'Suivant' }).click()
    await pause(page, 1200)

    // Étape 2 — articles : ajouter chaque produit puis bumper qty
    for (const product of PRODUCTS) {
      const search = page.locator('input[placeholder="Rechercher..."]')
      await search.fill(product.name)
      await pause(page, 700)
      const card = page.getByRole('button').filter({ hasText: product.name }).first()
      await card.click()
      await pause(page, 350)
    }

    // Fermer toute popup parasite (menu user, dropdown recherche)
    await page.keyboard.press('Escape')
    await pause(page, 500)
    await page.evaluate(() => document.body.click())
    await pause(page, 600)

    // Bumper les quantités via Playwright natif : click force sur "+", en
    // re-localisant à chaque iteration (React re-render invalide les refs JS).
    for (const product of PRODUCTS) {
      if (product.qty <= 1) continue
      for (let i = 1; i < product.qty; i++) {
        const ok = await page.evaluate((pname) => {
          const rows = [...document.querySelectorAll('div')].filter((d) => {
            const t = (d as HTMLElement).innerText || ''
            return /^[A-Z][^\n]+\n\s*\d/.test(t)
              && t.includes('€ / unite')
              && t.split('€ / unite').length === 2
          })
          const row = rows.find((r) => (r as HTMLElement).innerText.startsWith(pname))
          if (!row) return false
          const plus = row.querySelectorAll('button')[1] as HTMLButtonElement | undefined
          if (!plus) return false
          // Dispatch un vrai click event React-friendly
          plus.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }))
          return true
        }, product.name)
        if (!ok) break
      }
    }
    // Laisser voir le panier final avant de continuer
    await pause(page, 1500)

    // Étape 3 — Livraison Retrait client
    await page.getByRole('button', { name: 'Livraison' }).click()
    await pause(page, 1000)
    await page.getByRole('button', { name: /Retrait client/ }).click()
    await pause(page, 600)

    // Étape 4 — Options
    await page.getByRole('button', { name: 'Options' }).click()
    await pause(page, 1000)

    // Étape 5 — Récap
    await page.getByRole('button', { name: 'Recapitulatif' }).click()
    await pause(page, 2500)

    // Scroll complet du récap (8 articles + totaux + livraison) : c'est le
    // money shot qui montre la valeur métier. Lent volontairement.
    await scrollFullPage(page)
    await pause(page, 1500)

    await page.getByRole('button', { name: 'Creer et envoyer' }).click()
    await pause(page, 2500)

    // Modale d'envoi auto-ouverte — laisser voir le message "marqué comme Envoyé"
    const sendDialog = page.locator('[role="dialog"]').filter({ hasText: 'Envoyer le devis' })
    await pause(page, 1800)
    await sendDialog.locator('button', { hasText: /^Envoyer$/ }).click()
    await pause(page, 2200)

    // ── Acte 2 : Accept + Convert ───────────────────────────────────────────
    await page.getByRole('button', { name: 'Accepter' }).click()
    await pause(page, 2500) // statut bascule sent -> accepted

    await page.getByRole('button', { name: 'Convertir' }).click()
    await pause(page, 2000)

    // La modale a maintenant les dates pré-déduites J-1/J/J+1 — fix appliqué
    const convertDialog = page.locator('[role="dialog"]').filter({ hasText: 'Convertir en reservation' })
    await pause(page, 2000) // laisser voir les dates auto-remplies (différenciateur)
    await convertDialog.locator('button', { hasText: 'Convertir' }).click()
    await pause(page, 2800)

    await page.waitForURL(/\/reservations\/\d+/, { timeout: 15000 })
    await pause(page, 2500)

    // ── Acte 3 : Vue résa + modale avenant teaser ───────────────────────────
    // Scroll complet de la fiche résa : 8 lignes + total + boutons
    await scrollFullPage(page)

    // Ouvrir la modale Avenant (pour le teasing — différenciateur Lokki)
    await page.getByRole('button', { name: /Modifier le périmètre/ }).click()
    await pause(page, 3000) // lire le texte explicatif "version du devis tracée"
    await page.keyboard.press('Escape')
    await pause(page, 1200)

    // Récup id résa pour les forcages SQL successifs
    const resaUrl = page.url()
    const resaId = parseInt(resaUrl.match(/reservations\/(\d+)/)?.[1] ?? '0', 10)
    if (!Number.isFinite(resaId) || resaId <= 0) {
      throw new Error(`Invalid resa id parsed from URL: ${resaUrl}`)
    }

    function forceStatus(status: string) {
      execFileSync(
        'docker',
        [
          'compose', 'exec', '-T', 'db',
          'psql', '-U', 'caro', '-d', 'CaroCorp',
          '-c', `UPDATE reservations SET status='${status}' WHERE id=${resaId};`,
        ],
        { cwd: '..', stdio: 'pipe' },
      )
    }

    // ── Phase legal (cautions + signature + pre-check + documents) ──────────
    // Différenciateur Lokki : dashboard contractuel consolidé.
    forceStatus('confirmed')
    await page.goto(`reservations/${resaId}/legal`)
    await pause(page, 3500)
    await scrollFullPage(page)
    await pause(page, 1500)

    // ── Page signature contrat ──────────────────────────────────────────────
    // Le route guard redirige /signature vers /legal si on y va direct ;
    // on doit passer par le bouton "Signer le contrat maintenant".
    await page.getByRole('button', { name: /Signer le contrat maintenant/ }).click()
    await page.waitForURL(/\/signature/, { timeout: 10000 })
    await pause(page, 3500) // afficher canvas + instructions
    await scrollFullPage(page)
    await pause(page, 1500)

    // ── Operations departure : scan + check item-par-item + signature ───────
    // Différenciateur opérationnel : workflow terrain mobile-ready.
    await page.goto(`operations/departure/${resaId}`)
    await pause(page, 3500)
    await scrollFullPage(page)
    await pause(page, 1500)

    // Forcer livraison effective pour pouvoir constater le retour
    forceStatus('delivered')

    // Phase en-cours : countdown live + facture auto + équipe assignée
    await page.goto(`reservations/${resaId}/en-cours`)
    await pause(page, 3000)

    // Scroll complet : countdown live + timeline + facture auto + responsable
    await scrollFullPage(page)
    await pause(page, 1500)

    // ── Acte 4 : Constat retour ─────────────────────────────────────────────
    await page.getByRole('button', { name: 'Constater le retour' }).click()
    await pause(page, 2500) // laisser voir la modale 8 lignes pré-remplies

    // Saisie via JS direct dans la modale (8 inputs × 7 = 56 inputs — trop fastidieux click-by-click)
    await page.evaluate(() => {
      const fixed = [...document.querySelectorAll('div')].find(d => {
        const cs = getComputedStyle(d)
        return cs.position === 'fixed' && parseInt(cs.zIndex) === 50
      })
      if (!fixed) return
      const cards = [...fixed.querySelectorAll('input[type="text"][placeholder="Libellé article"]')]
        .map(el => (el as HTMLElement).closest('div')?.parentElement?.parentElement)
      const setI = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!
      const setS = Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value')!.set!

      // item 0 : 100 chaises -> 97 retournées, 3 endommagées, 75€
      const card0 = cards[0]
      if (card0) {
        const nums = [...card0.querySelectorAll('input[type="number"]')] as HTMLInputElement[]
        setI.call(nums[1], '97'); nums[1].dispatchEvent(new Event('input', { bubbles: true }))
        setI.call(nums[2], '3'); nums[2].dispatchEvent(new Event('input', { bubbles: true }))
        const sel = card0.querySelector('select') as HTMLSelectElement
        setS.call(sel, 'damaged'); sel.dispatchEvent(new Event('change', { bubbles: true }))
        const money = card0.querySelector('input[placeholder="0,00"]') as HTMLInputElement
        setI.call(money, '75,00'); money.dispatchEvent(new Event('input', { bubbles: true }))
      }
      // item 5 : Colonne gold qty 4 -> 3 retournées, 1 manquante, 50€
      const card5 = cards[5]
      if (card5) {
        const nums = [...card5.querySelectorAll('input[type="number"]')] as HTMLInputElement[]
        setI.call(nums[1], '3'); nums[1].dispatchEvent(new Event('input', { bubbles: true }))
        setI.call(nums[3], '1'); nums[3].dispatchEvent(new Event('input', { bubbles: true }))
        const sel = card5.querySelector('select') as HTMLSelectElement
        setS.call(sel, 'missing'); sel.dispatchEvent(new Event('change', { bubbles: true }))
        const money = card5.querySelector('input[placeholder="0,00"]') as HTMLInputElement
        setI.call(money, '50,00'); money.dispatchEvent(new Event('input', { bubbles: true }))
      }
    })
    // Laisser voir l'alerte "Total à imputer 125 €. La résa basculera en litige."
    // — c'est le moment fort de l'Acte 4. Long volontairement.
    await pause(page, 4000)

    await page.getByRole('button', { name: 'Valider le constat' }).click()
    await pause(page, 3500)

    // Bascule auto en /litige — on attend + on laisse voir le statut
    // "Retournée (litige)" + l'entrée auto dans le journal.
    await page.waitForURL(/\/litige/, { timeout: 10000 })
    await pause(page, 3500)

    // Scroll complet de la phase litige : alert + journal + lignes + caution
    await scrollFullPage(page)
    await pause(page, 1500)

    // Ajouter une note au journal — montre le caractère append-only
    const ta = page.locator('textarea').filter({ hasText: '' }).last()
    await ta.fill('Client appelé : conteste les rayures, propose 70€')
    await pause(page, 1500)
    await page.getByRole('button', { name: 'Ajouter au journal' }).click()
    await pause(page, 2800)

    // Clôturer
    await page.getByRole('button', { name: 'Clore le litige' }).click()
    await pause(page, 1800)
    const closeDlg = page.locator('[role="dialog"]').filter({ hasText: 'Clore le litige' })
    await closeDlg.locator('textarea').fill('Accord trouvé à 80€. Caution reversée pour 6 580€.')
    await pause(page, 1500)
    await closeDlg.locator('button', { hasText: 'Clore le litige' }).click()
    await pause(page, 3500)

    // Final : vue Retournée — scroll complet pour le money shot
    await scrollFullPage(page)
    await pause(page, 2500)

    expect(page.url()).toMatch(/\/(retournee|litige)/)
  })
})
