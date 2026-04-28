/**
 * print_features.mjs — Affiche un snapshot feature-map en arbre ASCII
 *
 * Usage :
 *   node docs/print_features.mjs --page customers
 *   node docs/print_features.mjs --page events
 *   node docs/print_features.mjs --all
 */

import { readFileSync, readdirSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const MAP_DIR   = resolve(__dirname, 'feature-map')

// ── Labels ─────────────────────────────────────────────────────────────────

const LINK_ICONS = {
  navigate:    'navigate ',
  modal_open:  'modal    ',
  panel_open:  'panel    ',
  tab_switch:  'tab      ',
  action:      'action   ',
  form_submit: 'submit   ',
}

function linkLabel(link_type) {
  const icon = LINK_ICONS[link_type] ?? (link_type ?? '?').padEnd(9)
  return `[${icon}]`
}

// ── Affichage d'une liste d'edges en arbre ──────────────────────────────────

/**
 * Affiche une liste d'edges (children) en arbre ASCII.
 * @param {Array}  edges   - tableau d'edges (link_type, label, target_id, node)
 * @param {string} prefix  - chaîne d'indentation courante
 */
function printEdges(edges, prefix = '') {
  if (!edges?.length) return

  edges.forEach((edge, i) => {
    const last = i === edges.length - 1
    const conn = last ? '└─ ' : '├─ '
    const cont = last ? '     ' : '│    '

    const tgt = (edge.link_type === 'navigate' && edge.target_id)
      ? `  → ${edge.target_id}`
      : ''

    const hasSubTree = edge.node && Array.isArray(edge.node.children) && edge.node.children.length > 0
    const hasParams  = edge.node && (edge.node.type === 'modal' || edge.node.type === 'form')
                       && Object.keys(edge.node.params ?? {}).length > 0

    if (!edge.node || (!hasSubTree && !hasParams)) {
      // ── Feuille ──
      console.log(`${prefix}${conn}${linkLabel(edge.link_type)}  ${edge.label}${tgt}`)
    } else {
      // ── Nœud avec sous-arbre ou params ──
      console.log(`${prefix}${conn}${linkLabel(edge.link_type)}  ${edge.node.name ?? edge.label}${tgt}`)

      const childPfx = prefix + cont

      // Ligne params si modal/form
      if (hasParams) {
        const paramStr = Object.entries(edge.node.params)
          .map(([k, v]) => `${k}/${v}`)
          .join(', ')
        const paramCount = Object.keys(edge.node.params).length
        const subConn = hasSubTree ? '├─ ' : '└─ '
        console.log(`${childPfx}${subConn}${edge.node.type} (${paramCount} params: ${paramStr})`)
      }

      // Enfants récursifs
      if (hasSubTree) {
        printEdges(edge.node.children, childPfx)
      }
    }
  })
}

// ── Affichage d'une page racine ─────────────────────────────────────────────

function printPage(pageId) {
  const filePath = resolve(MAP_DIR, `${pageId}.json`)
  let node
  try {
    node = JSON.parse(readFileSync(filePath, 'utf-8'))
  } catch {
    console.error(`  ✗ Fichier introuvable : ${filePath}`)
    console.error('    Lancez d\'abord :  node docs/map_features.mjs --page ' + pageId)
    return
  }

  const roles = node.attributes?.roles?.join(', ') ?? '*'
  const route = node.route ? `  (${node.route})` : ''
  console.log(`\n  ${node.id}${route}`)
  console.log(`  roles: [${roles}]`)
  if (node.attributes?.dom_h1) {
    console.log(`  h1: "${node.attributes.dom_h1}"`)
  }
  if (Object.keys(node.params ?? {}).length) {
    const paramStr = Object.entries(node.params)
      .map(([k, v]) => `${k}: ${v}`)
      .join(', ')
    console.log(`  params: { ${paramStr} }`)
  }
  if (node.features?.length) {
    console.log(`  features: ${node.features.join(', ')}`)
  }

  printEdges(node.children ?? [], '  ')
  console.log()
}

// ── CLI ────────────────────────────────────────────────────────────────────

const args    = process.argv.slice(2)
const isAll   = args.includes('--all')
const pageIdx = args.indexOf('--page')

if (isAll) {
  const files = readdirSync(MAP_DIR)
    .filter(f => f.endsWith('.json') && !f.startsWith('_'))
    .sort()
  for (const f of files) {
    printPage(f.replace('.json', ''))
  }
} else if (pageIdx !== -1) {
  printPage(args[pageIdx + 1])
} else {
  console.log(`
Usage :
  node docs/print_features.mjs --page <id>    Affiche une page
  node docs/print_features.mjs --all          Affiche toutes les pages scannées

Exemples :
  node docs/print_features.mjs --page customers
  node docs/print_features.mjs --page events
  node docs/print_features.mjs --all
`)
}
