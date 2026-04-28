/**
 * Démo commerciale Marveline — Scénario mobile iPhone 14 Pro
 *
 * 7 étapes, ~2 min 30 :
 *   1. Login
 *   2. Dashboard (KPIs)
 *   3. Agenda (calendrier + événement)
 *   4. Détail Réservation Dupont (mariage)
 *   5. Facture Moreau (frais dommage)
 *   6. Inventaire stock (badges + historique)
 *   7. Retour dashboard
 *
 * Pré-requis : seed_marveline_demo.py doit avoir été exécuté.
 */

import { test, expect } from '@playwright/test'

const DEMO_EMAIL = 'demo@marveline.fr'
const DEMO_PASSWORD = 'DemoMarveline2026!'

const TODAY = new Date()
const EVENT_DATE_DUPONT = new Date(TODAY)
EVENT_DATE_DUPONT.setDate(TODAY.getDate() + 7)
const DUPONT_DAY = EVENT_DATE_DUPONT.getDate().toString()

// ── Helpers ──────────────────────────────────────────────────────────────────

async function pause(page: import('@playwright/test').Page, ms: number) {
  await page.waitForTimeout(ms)
}

/** Attend qu'un sélecteur soit visible (sans planter si absent). */
async function waitForVisible(
  page: import('@playwright/test').Page,
  selector: string,
  timeout = 8000
): Promise<boolean> {
  try {
    await page.waitForSelector(selector, { state: 'visible', timeout })
    return true
  } catch {
    return false
  }
}

/** Scroll fluide sur la page (pas dans un modal). */
async function smoothScroll(page: import('@playwright/test').Page, dy: number, steps = 4) {
  const step = Math.round(dy / steps)
  for (let i = 0; i < steps; i++) {
    await page.evaluate((s) => window.scrollBy({ top: s, behavior: 'smooth' }), step)
    await page.waitForTimeout(400)
  }
}

/** Scroll à l'intérieur du modal ouvert. */
async function scrollInsideModal(page: import('@playwright/test').Page, dy: number) {
  const modal = page.locator('[role="dialog"]').first()
  if (await modal.isVisible({ timeout: 500 }).catch(() => false)) {
    await modal.evaluate((el, d) => el.scrollBy({ top: d, behavior: 'smooth' }), dy)
  } else {
    await page.evaluate((d) => window.scrollBy({ top: d, behavior: 'smooth' }), dy)
  }
  await page.waitForTimeout(400)
}

/** Ferme le modal ouvert (bouton Fermer ou Escape). */
async function closeModal(page: import('@playwright/test').Page) {
  const btn = page.locator('button[aria-label="Fermer"]').first()
  if (await btn.isVisible({ timeout: 1000 }).catch(() => false)) {
    await btn.click()
  } else {
    await page.keyboard.press('Escape')
  }
  // Attendre que le modal disparaisse
  await page.locator('[role="dialog"]').first().waitFor({ state: 'hidden', timeout: 3000 }).catch(() => null)
  await page.waitForTimeout(300)
}

/**
 * Ouvre le modal de détail via le bouton MoreVertical → "Voir details".
 * Utilise la référence (ex: DEMO-EV001) comme ancre stable (pas le nom client
 * qui peut être un <Link> de navigation).
 */
async function openDetailViaMenu(
  page: import('@playwright/test').Page,
  refText: string
): Promise<boolean> {
  // Attendre que la référence soit visible dans la liste
  const refLocator = page.locator(`text=${refText}`).first()
  if (!(await refLocator.isVisible({ timeout: 8000 }).catch(() => false))) {
    return false
  }

  // Remonter au conteneur flex parent (card mobile) ou à la ligne <tr> (desktop)
  const container = refLocator
    .locator('xpath=ancestor::*[contains(@class,"justify-between") or self::tr][1]')
    .first()

  const menuBtn = container.locator('button').last()
  if (!(await menuBtn.isVisible({ timeout: 2000 }).catch(() => false))) {
    return false
  }

  await menuBtn.click()
  await page.waitForTimeout(600)

  // Dropdown visible — cliquer "Voir details" (button:visible pour éviter mobile/desktop double)
  const viewBtn = page.locator('button:visible').filter({ hasText: /Voir d[eé]tail/i }).first()
  if (!(await viewBtn.isVisible({ timeout: 2000 }).catch(() => false))) {
    await page.keyboard.press('Escape')
    return false
  }

  await viewBtn.click()

  // Attendre que le modal s'ouvre réellement
  const opened = await waitForVisible(page, '[role="dialog"]', 5000)
  return opened
}

// ── Test principal ────────────────────────────────────────────────────────────

test('Démo Marveline — Scénario commercial mobile', async ({ page }) => {
  test.setTimeout(5 * 60 * 1000)

  // ══════════════════════════════════════════════════════════════
  // ÉTAPE 1 — Login
  // ══════════════════════════════════════════════════════════════
  await page.goto('/login')

  // Attendre le formulaire de login (pas juste networkidle)
  await waitForVisible(page, 'input[type="email"], input[name="email"]', 10000)
  await pause(page, 800)

  const emailInput = page.locator('input[type="email"], input[name="email"]').first()
  await emailInput.fill(DEMO_EMAIL)
  await pause(page, 600)

  const pwdInput = page.locator('input[type="password"], input[name="password"]').first()
  await pwdInput.fill(DEMO_PASSWORD)
  await pause(page, 600)

  await page.locator('button[type="submit"]').first().click()

  // Attendre la redirection post-login
  await page.waitForURL(/\/(dashboard|agenda|events)/, { timeout: 15000 })
  // Attendre qu'une vraie card de contenu soit visible (pas juste le shell)
  await waitForVisible(page, '.card, h1', 8000)
  await pause(page, 2000)

  // ══════════════════════════════════════════════════════════════
  // ÉTAPE 2 — Dashboard (KPIs)
  // ══════════════════════════════════════════════════════════════
  await page.goto('/dashboard')
  // Attendre les cartes KPI réelles
  await waitForVisible(page, '.card', 10000)
  await pause(page, 2000)

  // Scroll pour montrer toutes les rangées de KPIs
  await smoothScroll(page, 350)
  await pause(page, 1500)
  await smoothScroll(page, 350)
  await pause(page, 1500)

  // Remonter — pause finale sur le dashboard
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }))
  await pause(page, 3000)

  // ══════════════════════════════════════════════════════════════
  // ÉTAPE 3 — Agenda (calendrier)
  // ══════════════════════════════════════════════════════════════
  await page.goto('/agenda')
  // Attendre qu'un élément de calendrier soit visible
  await waitForVisible(page, '[data-day], .calendar-day, td, table, .card', 10000)
  await pause(page, 2000)

  // Cliquer le jour J+7 dans le calendrier
  const daySelectors = [
    `[data-day="${DUPONT_DAY}"]`,
    `.calendar-day:has-text("${DUPONT_DAY}")`,
    `td:has-text("${DUPONT_DAY}")`,
    `button:has-text("${DUPONT_DAY}")`,
  ]

  for (const sel of daySelectors) {
    const dayCell = page.locator(sel).first()
    if (await dayCell.isVisible({ timeout: 1000 }).catch(() => false)) {
      await dayCell.click()
      await pause(page, 1500)
      break
    }
  }

  // Sur l'agenda, chercher "Dupont" UNIQUEMENT dans les cards d'événement (pas un <Link>)
  // Les cards d'agenda sont des <div> cliquables, pas des <a>
  const dupontCard = page
    .locator('.card, [class*="event"], [class*="reservation"]')
    .filter({ hasText: /Dupont/i })
    .first()

  if (await dupontCard.isVisible({ timeout: 3000 }).catch(() => false)) {
    await dupontCard.click()
    await pause(page, 2000)
    // Fermer si un modal s'est ouvert
    if (await page.locator('[role="dialog"]').isVisible({ timeout: 1000 }).catch(() => false)) {
      await closeModal(page)
    }
  }

  await pause(page, 2000)

  // ══════════════════════════════════════════════════════════════
  // ÉTAPE 4 — Détail Réservation Dupont (mariage)
  // ══════════════════════════════════════════════════════════════
  await page.goto('/events')
  // Attendre que la liste des réservations soit chargée
  await waitForVisible(page, 'h1, table, [class*="border-b"]', 10000)
  await pause(page, 1500)

  const dupontOpened = await openDetailViaMenu(page, 'DEMO-EV001')

  if (dupontOpened) {
    await pause(page, 1500)

    // 1. Header — badge "Confirmée"
    await pause(page, 1200)

    // 2. Section client
    await scrollInsideModal(page, 160)
    await pause(page, 900)

    // 3. Section événement (Mariage · 180 invités)
    await scrollInsideModal(page, 160)
    await pause(page, 900)

    // 4. Section dates
    await scrollInsideModal(page, 160)
    await pause(page, 900)

    // 5. Section produits
    await scrollInsideModal(page, 200)
    await pause(page, 1200)

    // 6. Section caution — pause 2 sec
    await scrollInsideModal(page, 160)
    await pause(page, 2000)

    // 7. Section acompte
    await scrollInsideModal(page, 160)
    await pause(page, 1500)

    // Remonter en haut du modal
    const modal4 = page.locator('[role="dialog"]').first()
    if (await modal4.isVisible({ timeout: 500 }).catch(() => false)) {
      await modal4.evaluate((el) => el.scrollTo({ top: 0, behavior: 'smooth' }))
    }
    await pause(page, 1000)
    await closeModal(page)
  } else {
    // Fallback : scroller la liste
    await smoothScroll(page, 400)
    await pause(page, 2000)
    await page.evaluate(() => window.scrollTo(0, 0))
  }

  // ══════════════════════════════════════════════════════════════
  // ÉTAPE 5 — Facture Moreau (frais dommage)
  // ══════════════════════════════════════════════════════════════
  await page.goto('/invoices')
  // Attendre que la liste des factures soit chargée
  await waitForVisible(page, 'h1, table, [class*="border-b"]', 10000)
  await pause(page, 1500)

  const moreauOpened = await openDetailViaMenu(page, 'DEMO-INV003')

  if (moreauOpened) {
    await pause(page, 1500)

    // 1. En-tête + barre de progression 100%
    await pause(page, 1200)

    // 2. Scroll vers "Frais supplémentaires" (badge orange DOMMAGE)
    await scrollInsideModal(page, 220)
    await pause(page, 1500)
    await scrollInsideModal(page, 220)
    await pause(page, 2000) // Pause sur les frais

    // 3. Historique paiements
    await scrollInsideModal(page, 220)
    await pause(page, 1500)

    await closeModal(page)
  } else {
    await smoothScroll(page, 300)
    await pause(page, 2000)
  }

  // ══════════════════════════════════════════════════════════════
  // ÉTAPE 6 — Inventaire Stock (badges colorés)
  // ══════════════════════════════════════════════════════════════
  await page.goto('/inventory/stock')
  // Attendre que la page inventaire charge ses produits
  await waitForVisible(page, 'input[placeholder*="Recherche"], input[placeholder*="recherche"], input[placeholder*="Produit"], .card', 10000)
  await pause(page, 2000)

  // Chercher "Couvert" pour montrer les badges stock
  const searchInput = page
    .locator('input[placeholder*="Recherche"], input[placeholder*="recherche"], input[placeholder*="Produit"], input[type="search"]')
    .first()

  if (await searchInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await searchInput.fill('Couvert')
    await pause(page, 2000)
  }

  // Pause 3 sec sur les badges colorés (disponible / réservé / endommagé)
  await pause(page, 3000)

  // Cliquer "Hist." sur une unité pour montrer StockItemHistoryModal
  const histBtn = page
    .locator('button:visible')
    .filter({ hasText: /Hist/i })
    .first()

  if (await histBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await histBtn.click()
    await waitForVisible(page, '[role="dialog"]', 3000)
    await pause(page, 2000)
    await closeModal(page)
  }

  await pause(page, 1000)

  // ══════════════════════════════════════════════════════════════
  // ÉTAPE 7 — Retour Dashboard (fin)
  // ══════════════════════════════════════════════════════════════
  await page.goto('/dashboard')
  await waitForVisible(page, '.card, h1', 8000)
  await pause(page, 4000) // Pause finale 4 sec

  expect(page.url()).toContain('dashboard')
})
