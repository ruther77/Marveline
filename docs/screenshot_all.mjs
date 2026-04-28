/**
 * Capture tous les écrans (s-*) et modals (m-*) de LAYER.html
 * Viewport : iPhone 14 Pro (390×844)
 * Output   : docs/screenshots/{screens,modals}/
 */
import { chromium } from '/home/ruuuzer/Documents/CaroCorp_new/frontend/node_modules/playwright/index.mjs'
import { mkdirSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FILE = 'file://' + resolve(__dirname, 'LAYER.html')
const OUT_SCREENS = resolve(__dirname, 'screenshots/screens')
const OUT_MODALS  = resolve(__dirname, 'screenshots/modals')
mkdirSync(OUT_SCREENS, { recursive: true })
mkdirSync(OUT_MODALS,  { recursive: true })

const SCREENS = [
  's-home','s-planning-mois','s-planning-semaine','s-planning-jour','s-planning-ressources','s-planning-affectation',
  's-events-list','s-event-prevu','s-event-prevu-risque','s-event-en-cours','s-event-en-cours-incident',
  's-event-annule','s-event-retourne','s-event-retourne-casse','s-event-termine','s-event-action-plan',
  's-reservations','s-reservations-list','s-resa-create','s-resa-brouillon','s-resa-brouillon-incomplet',
  's-resa-confirmee-sans-caution','s-resa-confirmee-avec-caution','s-resa-confirmee-risque','s-resa-confirmee-prete',
  's-resa-precheck-legal','s-resa-en-cours','s-resa-en-cours-prolongee','s-resa-retournee','s-resa-retournee-litige',
  's-resa-terminee','s-resa-terminee-archive','s-resa-annulee',
  's-depart-inventaire','s-depart-from-resa','s-depart-bloque','s-retour-inventaire','s-dommage-declare','s-check-article',
  's-clients-list','s-client-detail','s-client-edit','s-client-nouveau','s-client-relance','s-relances-planifiees',
  's-catalogue-produit','s-catalogue-categorie','s-catalogue-packs','s-catalogue-variantes',
  's-catalogue-disponibilite','s-catalogue-collections','s-catalogue-builder','s-catalogue-comparateur',
  's-catalogue-audit','s-catalogue-fournisseurs','s-catalogue-qr','s-catalogue-upload','s-catalogue-etats',
  's-catalogue-outils','s-catalogue-outils-produit','s-catalogue-outils-media','s-catalogue-outils-pilotage',
  's-catalogue-photos','s-catalogue-recherche','s-catalogue-picker',
  's-stock','s-stock-faible','s-stock-reassort','s-stock-resolu','s-stock-historique','s-stock-item-detail','s-stock-etats',
  's-inventaire-physique','s-scan-qr','s-maintenance-produit','s-tarification','s-ligne-edit',
  's-factures','s-facture-brouillon','s-facture-detail','s-facture-emise','s-facture-payee','s-facture-retard',
  's-facture-create','s-facture-avoir','s-facture-casse','s-facture-audit',
  's-devis-list','s-devis-create','s-devis-detail','s-devis-brouillon','s-devis-expire','s-devis-refuse',
  's-devis-source','s-devis-couverture','s-devis-change-request','s-devis-phases','s-devis-module-socle',
  's-devis-module-stock','s-devis-module-facturation','s-devis-module-securite','s-devis-module-services',
  's-ventes','s-vente-brouillon','s-vente-acompte','s-vente-multi','s-vente-solde','s-vente-retard',
  's-finances','s-rapport-mensuel',
  's-notifications','s-recherche-globale','s-signature-contrat',
  's-profil','s-plus','s-parametres',
  's-admin-utilisateurs','s-admin-audit','s-admin-apikeys','s-admin-parametres',
]

const MODALS = [
  'm-creer-event','m-modifier-event','m-annuler-event','m-reprogrammer-event','m-cloturer-event',
  'm-remboursement-event','m-rapport-event','m-relancer-caution',
  'm-creer-resa','m-modifier-resa','m-confirmer-resa','m-supprimer-resa','m-prolonger-resa','m-archiver-resa',
  'm-bloquer-depart','m-valider-depart','m-valider-inventaire-sortie','m-valider-inventaire-retour',
  'm-cloturer-retour','m-clore-litige-resa','m-photo-depart','m-filter-reservations',
  'm-modifier-client','m-supprimer-client','m-filter-clients','m-relancer-client',
  'm-ajouter-produit','m-supprimer-produit','m-ajuster-stock','m-filter-stock','m-declarer-casse',
  'm-contact-fournisseur','m-lancer-reassort','m-cloturer-reassort','m-reception-reassort','m-maintenance-new',
  'm-inv-phys-count','m-inv-phys-ecart','m-scan-result','m-scan-manual',
  'm-sig-options','m-res-affecter',
  'm-ajouter-ligne-facture','m-supprimer-facture','m-envoyer-facture','m-marquer-payee',
  'm-relancer-facture','m-export-factures','m-avoir-facture','m-frais-supp','m-facturer-casse',
  'm-ajouter-paiement-multi','m-recu-paiement','m-facture-brouillon',
  'm-creer-devis','m-ajouter-ligne-devis','m-modifier-ligne-devis','m-envoyer-devis','m-accepter-devis',
  'm-refuser-devis','m-devis-refuse','m-dupliquer-devis','m-versionner-devis','m-renouveler-devis',
  'm-import-devis','m-export-devis','m-pdf-devis','m-pdf-document',
  'm-encaisser-caution','m-encaisser-solde','m-relancer-vente',
  'm-notif-detail','m-notif-facture-retard',
  'm-profil-nom','m-profil-email','m-profil-mdp','m-profil-theme','m-profil-deconnexion','m-changer-photo',
  'm-date-range',
  'm-admin-user','m-admin-inviter',
  'm-audit-detail','m-audit-export',
  'm-apikey-detail','m-apikey-create','m-apikey-new-reveal',
  'm-sys-param','m-sys-text','m-sys-confirm','m-sys-danger',
  'm-param-color','m-param-edit','m-param-text','m-tarif-edit',
  'm-rapport-export','m-relance-action',
  'm-plan-action-incident','m-verifier-retour-produit',
]

async function run() {
  const browser = await chromium.launch()
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
  })
  const page = await ctx.newPage()
  await page.goto(FILE, { waitUntil: 'domcontentloaded' })

  let ok = 0, skip = 0

  // ── ÉCRANS ──────────────────────────────────────────────
  console.log(`\n── ÉCRANS (${SCREENS.length}) ──`)
  for (const id of SCREENS) {
    const exists = await page.evaluate(id => !!document.getElementById(id), id)
    if (!exists) { console.log(`  SKIP ${id} (absent)`); skip++; continue }

    await page.evaluate(id => {
      // Fermer tous les modals
      document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'))
      // Activer l'écran
      document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'))
      const el = document.getElementById(id)
      if (el) el.classList.add('active')
    }, id)

    await page.waitForTimeout(120)
    await page.screenshot({ path: `${OUT_SCREENS}/${id}.png`, fullPage: false })
    process.stdout.write('.')
    ok++
  }

  // ── MODALS ──────────────────────────────────────────────
  console.log(`\n── MODALS (${MODALS.length}) ──`)

  // Mettre s-home actif comme fond
  await page.evaluate(() => {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'))
    const h = document.getElementById('s-home')
    if (h) h.classList.add('active')
  })

  for (const id of MODALS) {
    const exists = await page.evaluate(id => !!document.getElementById(id), id)
    if (!exists) { console.log(`  SKIP ${id} (absent)`); skip++; continue }

    await page.evaluate(id => {
      // Fermer tous les modals
      document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'))
      // Ouvrir ce modal
      const el = document.getElementById(id)
      if (el) el.classList.add('active')
    }, id)

    await page.waitForTimeout(100)
    await page.screenshot({ path: `${OUT_MODALS}/${id}.png`, fullPage: false })
    process.stdout.write('.')
    ok++
  }

  await browser.close()
  console.log(`\n\n✅ ${ok} captures — ${skip} skips`)
  console.log(`📁 ${OUT_SCREENS}`)
  console.log(`📁 ${OUT_MODALS}`)
}

run().catch(e => { console.error(e); process.exit(1) })
