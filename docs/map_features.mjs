/**
 * map_features.mjs — Marveline Feature Map
 * Cartographie récursive de l'arbre de features de chaque page en JSON.
 *
 * Usage:
 *   node docs/map_features.mjs --page dashboard
 *   node docs/map_features.mjs --page customers
 *   node docs/map_features.mjs --all
 *   node docs/map_features.mjs --all --depth 1
 *   node docs/map_features.mjs --list
 *
 * Output: docs/feature-map/<page-id>.json
 *
 * Structure d'un nœud:
 *   { id, type, name, description, route?, attributes, params, features[], children[] }
 *
 * Structure d'un lien (edge):
 *   { link_type, label, trigger, target_id?, node? }
 *   link_type: "navigate" | "modal_open" | "panel_open" | "tab_switch" | "action" | "form_submit"
 */

import { chromium } from '/home/ruuuzer/Documents/CaroCorp_new/frontend/node_modules/playwright/index.mjs'
import { mkdirSync, writeFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const BASE_URL   = 'http://localhost:3002'
const OUT_DIR    = resolve(__dirname, 'feature-map')
mkdirSync(OUT_DIR, { recursive: true })

const EMAIL    = 'admin@marveline.fr'
const PASSWORD = 'Admin123!'

// ── Catalogue complet des pages ────────────────────────────────────────────
/** @type {Array<{id:string, route:string, label:string, group:string, auth:boolean, roles:string[]}>} */
const PAGES = [
  // Auth
  { id: 'login',                route: '/login',                     label: 'Connexion',                  group: 'Auth',        auth: false, roles: ['*'] },
  { id: 'forgot-password',      route: '/forgot-password',           label: 'Mot de passe oublié',        group: 'Auth',        auth: false, roles: ['*'] },
  { id: 'reset-password',       route: '/reset-password',            label: 'Réinitialiser mot de passe', group: 'Auth',        auth: false, roles: ['*'] },
  { id: 'mfa-verify',           route: '/mfa/verify',                label: 'Vérification MFA',           group: 'Auth',        auth: false, roles: ['*'] },
  // Home
  { id: 'dashboard',            route: '/dashboard',                 label: 'Dashboard',                  group: 'Home',        auth: true,  roles: ['staff','manager','admin'] },
  { id: 'finances',             route: '/finances',                  label: 'Finances',                   group: 'Home',        auth: true,  roles: ['manager','admin'] },
  { id: 'notifications',        route: '/notifications',             label: 'Notifications',              group: 'Home',        auth: true,  roles: ['staff','manager','admin'] },
  { id: 'search',               route: '/search',                    label: 'Recherche globale',          group: 'Home',        auth: true,  roles: ['staff','manager','admin'] },
  { id: 'more',                 route: '/more',                      label: 'Plus',                       group: 'Home',        auth: true,  roles: ['staff','manager','admin'] },
  // Planning
  { id: 'agenda',               route: '/agenda',                    label: 'Agenda',                     group: 'Planning',    auth: true,  roles: ['staff','manager','admin'] },
  { id: 'agenda-mobile',        route: '/agenda/mobile',             label: 'Agenda mobile',              group: 'Planning',    auth: true,  roles: ['staff','manager','admin'] },
  { id: 'planning-today',       route: '/planning/today',            label: "Planning — Aujourd'hui",     group: 'Planning',    auth: true,  roles: ['staff','manager','admin'] },
  { id: 'planning-week',        route: '/planning/week',             label: 'Planning — Semaine',         group: 'Planning',    auth: true,  roles: ['staff','manager','admin'] },
  { id: 'planning-month',       route: '/planning/month',            label: 'Planning — Mois',            group: 'Planning',    auth: true,  roles: ['staff','manager','admin'] },
  { id: 'planning-day',         route: '/planning/day',              label: 'Planning — Jour',            group: 'Planning',    auth: true,  roles: ['staff','manager','admin'] },
  { id: 'planning-resources',   route: '/planning/resources',        label: 'Planning — Ressources',      group: 'Planning',    auth: true,  roles: ['staff','manager','admin'] },
  { id: 'planning-affectation', route: '/planning/affectation',      label: 'Planning — Affectation',     group: 'Planning',    auth: true,  roles: ['manager','admin'] },
  // Événements / Réservations
  { id: 'events',               route: '/events',                    label: 'Réservations',               group: 'Événements',  auth: true,  roles: ['staff','manager','admin'] },
  { id: 'events-new',           route: '/events/new',                label: 'Nouvelle réservation',       group: 'Événements',  auth: true,  roles: ['staff','manager','admin'] },
  { id: 'evenements',           route: '/evenements',                label: 'Événements',                 group: 'Événements',  auth: true,  roles: ['staff','manager','admin'] },
  // Ventes / Devis
  { id: 'devis',                route: '/devis',                     label: 'Devis',                      group: 'Ventes',      auth: true,  roles: ['staff','manager','admin'] },
  { id: 'devis-new',            route: '/devis/new',                 label: 'Nouveau devis',              group: 'Ventes',      auth: true,  roles: ['staff','manager','admin'] },
  { id: 'ventes',               route: '/ventes',                    label: 'Ventes',                     group: 'Ventes',      auth: true,  roles: ['staff','manager','admin'] },
  { id: 'ventes-new',           route: '/ventes/new',                label: 'Nouvelle vente',             group: 'Ventes',      auth: true,  roles: ['staff','manager','admin'] },
  { id: 'tarification',         route: '/tarification',              label: 'Tarification',               group: 'Ventes',      auth: true,  roles: ['manager','admin'] },
  // Clients
  { id: 'customers',            route: '/customers',                 label: 'Clients',                    group: 'Clients',     auth: true,  roles: ['staff','manager','admin'] },
  { id: 'customers-rfm',        route: '/customers/rfm',             label: 'Clients — Analyse RFM',      group: 'Clients',     auth: true,  roles: ['manager','admin'] },
  { id: 'customers-relances',   route: '/customers/relances',        label: 'Clients — Relances',         group: 'Clients',     auth: true,  roles: ['staff','manager','admin'] },
  { id: 'relances',             route: '/relances',                  label: 'Relances',                   group: 'Clients',     auth: true,  roles: ['staff','manager','admin'] },
  // Facturation
  { id: 'invoices',             route: '/invoices',                  label: 'Factures',                   group: 'Facturation', auth: true,  roles: ['staff','manager','admin'] },
  { id: 'invoices-new',         route: '/invoices/new',              label: 'Nouvelle facture',           group: 'Facturation', auth: true,  roles: ['manager','admin'] },
  { id: 'invoices-cautions',    route: '/invoices/cautions',         label: 'Cautions',                   group: 'Facturation', auth: true,  roles: ['staff','manager','admin'] },
  { id: 'invoices-tva',         route: '/invoices/tva-report',       label: 'Rapport TVA',                group: 'Facturation', auth: true,  roles: ['manager','admin'] },
  { id: 'invoices-rapprochement', route: '/invoices/rapprochement',  label: 'Rapprochement',              group: 'Facturation', auth: true,  roles: ['manager','admin'] },
  { id: 'invoices-rapport',     route: '/invoices/rapport-mensuel',  label: 'Rapport mensuel',            group: 'Facturation', auth: true,  roles: ['manager','admin'] },
  { id: 'tresorerie',           route: '/tresorerie',                label: 'Trésorerie',                 group: 'Facturation', auth: true,  roles: ['manager','admin'] },
  // Catalogue produits
  { id: 'products',             route: '/products',                  label: 'Produits',                   group: 'Catalogue',   auth: true,  roles: ['staff','manager','admin'] },
  { id: 'categories',           route: '/products/categories',       label: 'Catégories',                 group: 'Catalogue',   auth: true,  roles: ['staff','manager','admin'] },
  { id: 'bundles',              route: '/products/bundles',          label: 'Packs',                      group: 'Catalogue',   auth: true,  roles: ['staff','manager','admin'] },
  { id: 'collections',          route: '/products/collections',      label: 'Collections',                group: 'Catalogue',   auth: true,  roles: ['staff','manager','admin'] },
  { id: 'delivery-zones',       route: '/products/delivery-zones',   label: 'Zones de livraison',         group: 'Catalogue',   auth: true,  roles: ['manager','admin'] },
  { id: 'formulas',             route: '/products/formulas',         label: 'Formules',                   group: 'Catalogue',   auth: true,  roles: ['manager','admin'] },
  { id: 'suppliers',            route: '/products/suppliers',        label: 'Fournisseurs',               group: 'Catalogue',   auth: true,  roles: ['manager','admin'] },
  { id: 'supplier-orders',      route: '/products/supplier-orders',  label: 'Commandes fournisseurs',     group: 'Catalogue',   auth: true,  roles: ['manager','admin'] },
  { id: 'products-availability',route: '/products/availability',     label: 'Disponibilités',             group: 'Catalogue',   auth: true,  roles: ['staff','manager','admin'] },
  { id: 'products-pilotage',    route: '/products/pilotage',         label: 'Pilotage catalogue',         group: 'Catalogue',   auth: true,  roles: ['manager','admin'] },
  { id: 'products-comparateur', route: '/products/comparateur',      label: 'Comparateur',                group: 'Catalogue',   auth: true,  roles: ['staff','manager','admin'] },
  { id: 'products-tools',       route: '/products/tools',            label: 'Outils produits',            group: 'Catalogue',   auth: true,  roles: ['manager','admin'] },
  { id: 'products-import',      route: '/products/import',           label: 'Import produits',            group: 'Catalogue',   auth: true,  roles: ['admin'] },
  { id: 'products-qr',          route: '/products/qr',               label: 'QR Codes',                   group: 'Catalogue',   auth: true,  roles: ['staff','manager','admin'] },
  { id: 'products-media',       route: '/products/media',            label: 'Médiathèque',                group: 'Catalogue',   auth: true,  roles: ['manager','admin'] },
  { id: 'catalogue-builder',    route: '/catalogue/builder',         label: 'Catalogue Builder',          group: 'Catalogue',   auth: true,  roles: ['manager','admin'] },
  // Inventaire
  { id: 'inventory-stock',      route: '/inventory/stock',           label: 'Stock',                      group: 'Inventaire',  auth: true,  roles: ['staff','manager','admin'] },
  { id: 'inventory-movements',  route: '/inventory/movements',       label: 'Mouvements',                 group: 'Inventaire',  auth: true,  roles: ['staff','manager','admin'] },
  { id: 'inventory-inventaire', route: '/inventory/inventaire',      label: 'Inventaire physique',        group: 'Inventaire',  auth: true,  roles: ['manager','admin'] },
  { id: 'inventory-adjustments',route: '/inventory/adjustments',     label: 'Ajustements de stock',       group: 'Inventaire',  auth: true,  roles: ['manager','admin'] },
  { id: 'inventory-reorder',    route: '/inventory/reorder',         label: 'Réapprovisionnement',        group: 'Inventaire',  auth: true,  roles: ['manager','admin'] },
  { id: 'inventory-coverage',   route: '/inventory/coverage',        label: 'Couverture stock',           group: 'Inventaire',  auth: true,  roles: ['manager','admin'] },
  { id: 'inventory-damage',     route: '/inventory/damage-types',    label: 'Types de dommages',          group: 'Inventaire',  auth: true,  roles: ['manager','admin'] },
  // Opérations
  { id: 'operations',           route: '/operations',                label: 'Opérations',                 group: 'Opérations',  auth: true,  roles: ['staff','manager','admin'] },
  { id: 'operations-scan',      route: '/operations/scan',           label: 'Scan QR',                    group: 'Opérations',  auth: true,  roles: ['staff','manager','admin'] },
  // Profil
  { id: 'profile',              route: '/profile',                   label: 'Profil',                     group: 'Compte',      auth: true,  roles: ['staff','manager','admin'] },
  { id: 'profile-security',     route: '/profile/security',          label: 'Sécurité',                   group: 'Compte',      auth: true,  roles: ['staff','manager','admin'] },
  { id: 'profile-mfa',          route: '/profile/mfa',               label: 'Configuration MFA',          group: 'Compte',      auth: true,  roles: ['staff','manager','admin'] },
  // Admin
  { id: 'admin-users',          route: '/admin/users',               label: 'Utilisateurs',               group: 'Admin',       auth: true,  roles: ['admin'] },
  { id: 'admin-sessions',       route: '/admin/sessions',            label: 'Sessions actives',           group: 'Admin',       auth: true,  roles: ['admin'] },
  { id: 'admin-audit',          route: '/admin/audit-logs',          label: "Logs d'audit",               group: 'Admin',       auth: true,  roles: ['admin'] },
  { id: 'admin-api-keys',       route: '/admin/api-keys',            label: 'API Keys',                   group: 'Admin',       auth: true,  roles: ['admin'] },
  { id: 'admin-features',       route: '/admin/features',            label: 'Feature Flags',              group: 'Admin',       auth: true,  roles: ['admin'] },
  { id: 'admin-vpn',            route: '/admin/vpn',                 label: 'VPN',                        group: 'Admin',       auth: true,  roles: ['admin'] },
  { id: 'admin-settings',       route: '/admin/settings',            label: 'Paramètres tenant',          group: 'Admin',       auth: true,  roles: ['admin'] },
]

// ── Utilitaires ────────────────────────────────────────────────────────────

function slugify(text) {
  return String(text)
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .substring(0, 60)
}

/**
 * Classifie le type de lien d'un bouton à partir de son texte / aria-label.
 * @param {string} text
 * @returns {'modal_open'|'action'|'form_submit'|'panel_open'}
 */
function classifyButton(text) {
  const t = text.toLowerCase()
  if (/^(nouveau|nouvelle|ajouter|new\b|add\b)/.test(t))                       return 'modal_open'
  if (/modifier|éditer|editer|edit\b|update\b|changer/i.test(t))              return 'modal_open'
  if (/voir|détail|detail|ouvrir|consulter|open\b|show\b/i.test(t))           return 'modal_open'
  if (/dupliquer|dupliquer|duplicate|copier|copy\b/i.test(t))                 return 'action'
  if (/supprimer|archiver|désactiver|delete\b|remove\b|disable\b/i.test(t))   return 'action'
  if (/envoyer|send\b|publier|publish\b/i.test(t))                            return 'action'
  if (/exporter|télécharger|export\b|download\b/i.test(t))                    return 'action'
  if (/imprimer|print\b/i.test(t))                                            return 'action'
  if (/sauvegarder|confirmer|valider|soumettre|save\b|confirm\b|submit\b|créer$|creer$|create$/i.test(t)) return 'form_submit'
  if (/annuler|fermer|cancel\b|close\b/i.test(t))                             return 'action'
  if (/filtrer|filter\b|rechercher|search\b/i.test(t))                        return 'action'
  if (/paramètre|parametre|setting|configuration|config\b/i.test(t))          return 'panel_open'
  return 'action'
}

/**
 * Génère une description longue à partir du type, du nom et des features visibles.
 */
function buildDescription(type, name, features, params) {
  const typeLabels = {
    page:    'Page principale',
    modal:   'Fenêtre modale',
    form:    'Formulaire',
    section: 'Section de page',
    list:    'Liste / tableau de données',
    card:    'Carte de détail',
  }
  const typeLabel = typeLabels[type] || 'Composant'
  const featSummary = features.length
    ? `Contient : ${features.slice(0, 6).join(', ')}.`
    : 'Contenu non détecté automatiquement.'
  const paramSummary = Object.keys(params).length
    ? ` Paramètres : ${Object.keys(params).join(', ')}.`
    : ''
  return `${typeLabel} "${name}". ${featSummary}${paramSummary}`
}

// ── Extraction DOM ─────────────────────────────────────────────────────────

/**
 * Extrait les métadonnées sémantiques de la page courante.
 */
async function extractPageMeta(page) {
  return page.evaluate(() => {
    const getText = sel => document.querySelector(sel)?.innerText?.trim() ?? ''
    const title      = getText('h1') || document.title || ''
    const subtitles  = Array.from(document.querySelectorAll('h2, h3'))
      .map(el => el.innerText?.trim())
      .filter(Boolean)
      .slice(0, 8)
    const navLinks   = Array.from(document.querySelectorAll('nav a[href], [role="navigation"] a[href]'))
      .map(el => ({ label: el.innerText?.trim(), href: el.getAttribute('href') }))
      .filter(l => l.label && l.href && l.href !== '#')
    const tabs       = Array.from(document.querySelectorAll('[role="tab"]'))
      .map(el => ({ text: el.innerText?.trim(), selected: el.getAttribute('aria-selected') === 'true' }))
      .filter(t => t.text)
    const badges     = Array.from(document.querySelectorAll('[class*="badge"], [class*="chip"], [class*="tag"], [class*="status"]'))
      .map(el => el.innerText?.trim())
      .filter(Boolean)
      .slice(0, 6)
    return { title, subtitles, navLinks, tabs, badges }
  })
}

/**
 * Extrait tous les éléments interactifs.
 * Si une ou plusieurs modals/dialogs sont ouvertes, scope l'extraction à la plus imbriquée.
 * Sinon, extrait depuis tout le document.
 */
async function extractInteractiveElements(page) {
  return page.evaluate(() => {
    // Scope : dialog le plus imbriqué si présent (last), sinon document entier
    const dialogs = Array.from(document.querySelectorAll('[role="dialog"]:not([hidden]), [class*="modal"]:not([hidden]), [class*="Modal"]:not([hidden])'))
    const scope = dialogs.length ? dialogs[dialogs.length - 1] : document

    const results = []

    // Boutons
    scope.querySelectorAll('button:not([disabled])').forEach(el => {
      const text      = el.innerText?.trim() || ''
      const ariaLabel = el.getAttribute('aria-label') || ''
      const label     = text || ariaLabel
      if (!label || label.length > 80) return
      // Ignorer les boutons de pagination pure (chiffres, flèches)
      if (/^(\d+|[<>«»‹›↑↓←→▸▾])$/.test(label)) return
      results.push({
        kind:         'button',
        text:         label,
        type:         el.getAttribute('type') || 'button',
        ariaExpanded: el.getAttribute('aria-expanded'),
        ariaHaspopup: el.getAttribute('aria-haspopup'),
        dataTestId:   el.getAttribute('data-testid') || '',
        classHint:    (el.className || '').substring(0, 120),
      })
    })

    // Liens de navigation interne
    scope.querySelectorAll('a[href]').forEach(el => {
      const href  = el.getAttribute('href')
      const label = el.innerText?.trim() || el.getAttribute('aria-label') || ''
      if (!label || label.length > 80 || !href || href === '#' || href.startsWith('http')) return
      results.push({ kind: 'link', text: label, href })
    })

    // Tabs
    scope.querySelectorAll('[role="tab"]').forEach(el => {
      const text = el.innerText?.trim()
      if (!text) return
      results.push({ kind: 'tab', text, selected: el.getAttribute('aria-selected') === 'true' })
    })

    // Champs de formulaire (inputs, selects, textareas)
    scope.querySelectorAll('input:not([type="hidden"]):not([type="submit"]), select, textarea').forEach(el => {
      const label = el.getAttribute('placeholder')
        || el.getAttribute('aria-label')
        || document.querySelector(`label[for="${el.id}"]`)?.innerText?.trim()
        || el.getAttribute('name')
        || ''
      const type = el.tagName.toLowerCase() === 'input'
        ? (el.getAttribute('type') || 'text')
        : el.tagName.toLowerCase()
      if (!label) return
      results.push({
        kind:     'input',
        label:    label.trim().substring(0, 60),
        type,
        name:     el.getAttribute('name') || el.getAttribute('id') || '',
        required: el.hasAttribute('required'),
      })
    })

    return results
  })
}

// ── Scan récursif d'une modal ──────────────────────────────────────────────

/**
 * Scanne la modal la plus imbriquée actuellement ouverte dans la page.
 * Tente de cliquer les boutons modal_open pour descendre jusqu'à maxDepth.
 *
 * @param {import('playwright').Page} page
 * @param {number} depth    - profondeur courante (1-based depuis la page)
 * @param {number} maxDepth - profondeur maximale autorisée
 * @returns {Promise<object>} nœud FeatureNode de type modal/form
 */
async function scanOpenModal(page, depth, maxDepth, visitedIds = new Set()) {
  // Lire le titre du dialog le plus imbriqué
  const dialogText = await page.evaluate(() => {
    const dialogs = Array.from(document.querySelectorAll('[role="dialog"]:not([hidden]), [class*="modal"]:not([hidden]), [class*="Modal"]:not([hidden])'))
    const dialog  = dialogs.length ? dialogs[dialogs.length - 1] : null
    if (!dialog) return null
    const title       = dialog.querySelector('h1, h2, h3, [class*="title"], [class*="Title"]')?.innerText?.trim() || ''
    const description = dialog.querySelector('p, [class*="description"], [class*="subtitle"]')?.innerText?.trim() || ''
    return { title, description }
  })

  const elems = await extractInteractiveElements(page)

  // Déduplication
  const seen   = new Set()
  const unique = elems.filter(e => {
    const k = `${e.kind}:${e.text || e.label || e.href}`
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })

  const inputs  = unique.filter(e => e.kind === 'input')
  const buttons = unique.filter(e => e.kind === 'button')
  const hasForm = inputs.length > 0
  const name    = dialogText?.title || 'Modal'
  const id      = `modal:${slugify(name)}`

  const params = {}
  for (const inp of inputs) {
    const key = slugify(inp.name || inp.label)
    if (key) params[key] = `${inp.type}${inp.required ? ' (requis)' : ''}`
  }

  const features = [
    ...(dialogText?.description ? [dialogText.description.substring(0, 100)] : []),
    ...inputs.slice(0, 8).map(i => `Champ : ${i.label}`),
    ...buttons.slice(0, 6).map(b => b.text),
  ].filter(Boolean)

  // ── Construire les enfants avec récursion sur les sous-modals ──────────
  const children   = []
  const triedSubs  = new Set()

  for (const btn of buttons) {
    const label    = btn.text
    const linkType = classifyButton(label)

    if ((linkType === 'modal_open' || btn.ariaHaspopup) && depth < maxDepth) {
      const subKey = slugify(label)
      const subId  = `modal:${subKey}`

      // Éviter les cycles (même modal déjà tentée sur cette branche)
      if (triedSubs.has(subKey) || visitedIds.has(subId)) {
        children.push({ link_type: 'modal_open', label, trigger: 'click', target_id: subId, node: null })
        continue
      }
      triedSubs.add(subKey)

      let subNode = null
      // On ajoute subId AVANT de descendre pour couper les auto-références
      const nextVisited = new Set([...visitedIds, subId])
      try {
        // Chercher le bouton dans le dialog le plus imbriqué courant
        const locator = page.locator(
          '[role="dialog"] button, [class*="modal"] button, [class*="Modal"] button',
          { hasText: new RegExp('^' + escapeRe(label) + '$', 'i') }
        ).last()

        if (await locator.count() > 0) {
          await locator.click({ timeout: 4000 })
          const appeared = await page
            .waitForSelector('[role="dialog"], [class*="modal"], [class*="Modal"]', { timeout: 3000 })
            .then(() => true)
            .catch(() => false)

          if (appeared) {
            await page.waitForTimeout(400)
            subNode = await scanOpenModal(page, depth + 1, maxDepth, nextVisited)
            // Fermer la sous-modal
            await page.keyboard.press('Escape').catch(() => {})
            await page.waitForTimeout(400)
          }
        }
      } catch (_) { /* non-interactif → placeholder */ }

      children.push({
        link_type: 'modal_open',
        label,
        trigger:   'click',
        target_id: subId,
        node: subNode ?? {
          id:          `modal:${subKey}`,
          type:        'modal',
          name:        label,
          description: `Sous-modal ouverte par "${label}" (profondeur ${depth + 1}). Non extraite automatiquement.`,
          attributes:  { scan_status: 'placeholder', depth: depth + 1 },
          params:      {},
          features:    [],
          children:    [],
        },
      })

    } else {
      children.push({
        link_type: linkType,
        label,
        trigger:   'click',
        target_id: null,
        node:      null,
      })
    }
  }

  return {
    id,
    type:        hasForm ? 'form' : 'modal',
    name,
    description: buildDescription(hasForm ? 'form' : 'modal', name, features, params),
    attributes:  { depth, opened_from_depth: depth - 1 },
    params,
    features,
    children,
  }
}

// ── Scan récursif d'une page ───────────────────────────────────────────────

/**
 * Scan complet d'une page : extrait les métadonnées, les éléments interactifs,
 * et tente d'ouvrir récursivement les modals pour les scanner aussi.
 *
 * @param {import('playwright').Page} page - page Playwright déjà chargée
 * @param {object} pageInfo - entrée du catalogue PAGES
 * @param {number} maxDepth - profondeur maximale de récursion (défaut 2)
 * @returns {Promise<object>} nœud FeatureNode racine
 */
async function scanPage(page, pageInfo, maxDepth = 4) {
  const meta  = await extractPageMeta(page)
  const elems = await extractInteractiveElements(page)

  // Déduplication sur (kind, texte/href)
  const seen   = new Set()
  const unique = elems.filter(e => {
    const k = `${e.kind}:${e.text || e.label || e.href}`
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })

  const buttons = unique.filter(e => e.kind === 'button')
  const links   = unique.filter(e => e.kind === 'link')
  const tabs    = unique.filter(e => e.kind === 'tab')
  const inputs  = unique.filter(e => e.kind === 'input')

  // Paramètres de la page (query params ou champs de filtrage/recherche)
  const params = {}
  for (const inp of inputs.slice(0, 10)) {
    const k = slugify(inp.name || inp.label)
    if (k) params[k] = `${inp.type}${inp.required ? ' (requis)' : ''}`
  }

  const features = [
    ...meta.subtitles,
    ...meta.badges,
    ...tabs.map(t => `Onglet : ${t.text}`),
    ...inputs.slice(0, 6).map(i => `Champ : ${i.label}`),
  ].filter(Boolean)

  const node = {
    id:          `page:${pageInfo.id}`,
    type:        'page',
    name:        pageInfo.label,
    description: '', // rempli en fin de fonction
    route:       pageInfo.route,
    attributes:  {
      auth_required: pageInfo.auth,
      roles:         pageInfo.roles,
      group:         pageInfo.group,
      dom_h1:        meta.title || null,
    },
    params,
    features,
    children:    [],
  }

  // ── 1. Liens de navigation (SubNav, breadcrumb, liens internes) ──────────
  const addedNavTargets = new Set()
  for (const link of links) {
    if (!link.href || link.href === pageInfo.route) continue
    // Résoudre la page cible si connue
    const target = PAGES.find(p => p.route === link.href || link.href.startsWith(p.route + '/'))
    const targetId = target ? `page:${target.id}` : `page:external:${slugify(link.href)}`
    if (addedNavTargets.has(targetId)) continue
    addedNavTargets.add(targetId)
    node.children.push({
      link_type: 'navigate',
      label:     link.text,
      trigger:   'click',
      target_id: targetId,
      node:      null, // sera résolu lors de la fusion
    })
  }

  // ── 2. Onglets (tab_switch) ──────────────────────────────────────────────
  for (const tab of tabs) {
    node.children.push({
      link_type: 'tab_switch',
      label:     tab.text,
      trigger:   'click',
      target_id: null,
      node: {
        id:          `section:${pageInfo.id}:${slugify(tab.text)}`,
        type:        'section',
        name:        tab.text,
        description: `Onglet "${tab.text}" dans la page ${pageInfo.label}.`,
        attributes:  { parent_page: pageInfo.id, active_by_default: tab.selected },
        params:      {},
        features:    [],
        children:    [],
      },
    })
  }

  // ── 3. Boutons ───────────────────────────────────────────────────────────
  // Suivi des modals déjà tentées sur cette page pour éviter les doublons
  const triedModals = new Set()

  for (const btn of buttons) {
    const label    = btn.text
    const linkType = classifyButton(label)

    // Si c'est un bouton d'ouverture de modal ET qu'on n'a pas atteint la limite de profondeur
    if ((linkType === 'modal_open' || btn.ariaHaspopup) && maxDepth > 0) {
      const modalKey = slugify(label)
      if (triedModals.has(modalKey)) {
        // Doublon — on pointe vers la même modal déjà explorée
        node.children.push({
          link_type: 'modal_open',
          label,
          trigger:   'click',
          target_id: `modal:${modalKey}`,
          node:      null,
        })
        continue
      }
      triedModals.add(modalKey)

      let modalNode = null
      try {
        // Tenter de cliquer le bouton et attendre l'apparition d'un dialog
        const locator = page
          .locator('button', { hasText: new RegExp('^' + escapeRe(label) + '$', 'i') })
          .first()

        if (await locator.count() > 0) {
          await locator.click({ timeout: 4000 })
          const appeared = await page
            .waitForSelector('[role="dialog"], [class*="modal"], [class*="Modal"], [class*="sheet"], [class*="Sheet"]', { timeout: 3000 })
            .then(() => true)
            .catch(() => false)

          if (appeared) {
            // Passer le slug du bouton comme id visité pour couper les auto-références
            modalNode = await scanOpenModal(page, 1, maxDepth, new Set([`modal:${modalKey}`]))
            // Fermeture propre
            await page.keyboard.press('Escape').catch(() => {})
            await page.waitForTimeout(400)
          }
        }
      } catch (_) {
        // Impossible d'interagir — on crée un nœud placeholder
      }

      node.children.push({
        link_type: 'modal_open',
        label,
        trigger:   'click',
        target_id: `modal:${slugify(label)}`,
        node: modalNode ?? {
          id:          `modal:${slugify(label)}`,
          type:        'modal',
          name:        label,
          description: `Modal/panneau ouvert(e) par le bouton "${label}" sur la page ${pageInfo.label}. Non extrait automatiquement.`,
          attributes:  { scan_status: 'placeholder' },
          params:      {},
          features:    [],
          children:    [],
        },
      })

    } else {
      // Action simple ou soumission de formulaire
      node.children.push({
        link_type: linkType,
        label,
        trigger:   'click',
        target_id: null,
        node:      null,
      })
    }
  }

  // Description finale
  node.description = buildDescription('page', pageInfo.label, features, params)

  return node
}

// ── Helpers ────────────────────────────────────────────────────────────────

function escapeRe(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

async function login(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 20000 })
  await page.waitForSelector('#email', { timeout: 15000 })
  await page.fill('#email', EMAIL)
  await page.fill('#password', PASSWORD)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL(/dashboard/, { timeout: 60000 })
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.waitForTimeout(1000)
}

/**
 * Navigue vers une route en restant dans la SPA (pas de rechargement full-page).
 * Nécessaire car l'access_token est en mémoire Zustand — un page.goto() le perd.
 * TanStack Router intercepte les appels history.pushState.
 */
async function spaNavigate(page, route) {
  await page.evaluate(r => window.history.pushState({}, '', r), route)
  // Laisser le router et React re-render
  await page.waitForTimeout(1200)
  // Vérifier qu'on n'a pas été redirigé vers login
  const current = page.url()
  if (current.includes('/login')) {
    throw new Error(`Redirection vers login après navigate vers ${route} — session expirée`)
  }
}

// ── Scan d'une entrée de catalogue ─────────────────────────────────────────

async function runPageScan(pageId, browser, maxDepth) {
  const pageInfo = PAGES.find(p => p.id === pageId)
  if (!pageInfo) {
    console.error(`  ✗ Page inconnue : "${pageId}". Utilisez --list pour voir les pages disponibles.`)
    return null
  }

  const ctx  = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()

  try {
    if (pageInfo.auth) {
      await login(page)
      await spaNavigate(page, pageInfo.route)
    } else {
      await page.goto(`${BASE_URL}${pageInfo.route}`, { waitUntil: 'domcontentloaded', timeout: 15000 })
      await page.waitForTimeout(1000)
    }

    const node     = await scanPage(page, pageInfo, maxDepth)
    const outPath  = resolve(OUT_DIR, `${pageId}.json`)
    writeFileSync(outPath, JSON.stringify(node, null, 2))

    const modalCount = node.children.filter(e => e.link_type === 'modal_open').length
    const navCount   = node.children.filter(e => e.link_type === 'navigate').length
    console.log(
      `  ✓ ${pageId.padEnd(28)}` +
      `  ${String(node.children.length).padStart(3)} enfants` +
      `  (modals: ${modalCount}, nav: ${navCount}, features: ${node.features.length})`
    )
    return node
  } catch (e) {
    console.error(`  ✗ ${pageId}: ${e.message.slice(0, 100)}`)
    return null
  } finally {
    await ctx.close()
  }
}

// ── CLI ────────────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2)

  if (args.includes('--list')) {
    console.log('\nPages disponibles :\n')
    const groups = {}
    for (const p of PAGES) {
      ;(groups[p.group] = groups[p.group] || []).push(p)
    }
    for (const [group, pages] of Object.entries(groups)) {
      console.log(`  ${group}`)
      for (const p of pages) {
        console.log(`    --page ${p.id.padEnd(30)} ${p.label.padEnd(40)} ${p.route}`)
      }
    }
    console.log()
    return
  }

  const isAll       = args.includes('--all')
  const pageIdx     = args.indexOf('--page')
  const depthIdx    = args.indexOf('--depth')
  const maxDepth    = depthIdx !== -1 ? parseInt(args[depthIdx + 1], 10) : 4
  const groupIdx    = args.indexOf('--group')
  const groupFilter = groupIdx !== -1 ? args[groupIdx + 1] : null

  if (!isAll && pageIdx === -1) {
    console.log(`
Usage :
  node docs/map_features.mjs --page <id>              Scanne une page spécifique
  node docs/map_features.mjs --all                    Scanne toutes les pages
  node docs/map_features.mjs --all --group Catalogue  Scanne un groupe de pages
  node docs/map_features.mjs --all --depth 1          Profondeur 1 (sans récursion dans les modals)
 *   node docs/map_features.mjs --all --depth 4          Profondeur 4 (défaut)
  node docs/map_features.mjs --list                   Liste toutes les pages disponibles

Options :
  --depth <n>    Profondeur de récursion maximale (défaut : 2)
  --group <nom>  Restreindre à un groupe (Auth, Home, Planning, Événements, …)

Exemples :
  node docs/map_features.mjs --page dashboard
  node docs/map_features.mjs --page customers --depth 3
  node docs/map_features.mjs --all --group Admin
  node docs/map_features.mjs --all

Output : docs/feature-map/<page-id>.json
Fusion : node docs/merge_features.mjs
`)
    return
  }

  const browser = await chromium.launch({ headless: true })
  const t0 = Date.now()

  try {
    if (isAll) {
      const targets = groupFilter
        ? PAGES.filter(p => p.group.toLowerCase() === groupFilter.toLowerCase())
        : PAGES

      console.log(`\n── SCAN ${targets.length} page(s) (profondeur ${maxDepth})${groupFilter ? ` — groupe : ${groupFilter}` : ''} ──\n`)

      let ok = 0, ko = 0
      for (const p of targets) {
        const result = await runPageScan(p.id, browser, maxDepth)
        result ? ok++ : ko++
      }

      const elapsed = ((Date.now() - t0) / 1000).toFixed(1)
      console.log(`\n✅ ${ok} pages scannées, ${ko} erreurs — ${elapsed}s`)
      console.log(`📁 ${OUT_DIR}`)
      console.log('\nPour fusionner en arbre global :')
      console.log('  node docs/merge_features.mjs')

    } else {
      const pageId = args[pageIdx + 1]
      console.log(`\n── SCAN : ${pageId} (profondeur ${maxDepth}) ──\n`)
      await runPageScan(pageId, browser, maxDepth)
      console.log(`\n📁 ${OUT_DIR}/${pageId}.json`)
    }
  } finally {
    await browser.close()
  }
}

main().catch(e => { console.error(e); process.exit(1) })
