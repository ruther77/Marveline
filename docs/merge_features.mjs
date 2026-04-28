/**
 * merge_features.mjs — Fusionne les snapshots docs/feature-map/*.json
 * en un arbre global docs/feature-map/_merged.json
 *
 * Usage :
 *   node docs/merge_features.mjs
 *   node docs/merge_features.mjs --stats    Affiche les statistiques détaillées
 *
 * La fusion effectue deux passes :
 *   1. Indexation de tous les nœuds par leur id
 *   2. Résolution des références croisées (target_id → node inline)
 *
 * Le fichier _merged.json contient :
 *   - Un index plat de tous les nœuds (nodeIndex)
 *   - L'arbre groupé par domaine fonctionnel (groups)
 *   - Des statistiques globales
 */

import { readdirSync, readFileSync, writeFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const MAP_DIR   = resolve(__dirname, 'feature-map')

// ── Résolution récursive des références croisées ───────────────────────────

/**
 * Parcourt un nœud récursivement et remplace les {node: null, target_id: X}
 * par le nœud correspondant s'il existe dans l'index.
 * On évite les cycles en passant un Set de target_id déjà résolus sur la branche.
 *
 * @param {object} node
 * @param {Record<string,object>} index
 * @param {Set<string>} resolving - ids en cours de résolution sur cette branche (anti-cycle)
 * @returns {object}
 */
function resolveNode(node, index, resolving = new Set()) {
  if (!node || !node.children) return node

  node.children = node.children.map(edge => {
    if (edge.node === null && edge.target_id) {
      const target = index[edge.target_id]
      if (target && !resolving.has(edge.target_id)) {
        // On crée un snapshot superficiel pour éviter les références circulaires :
        // on inclut le nœud cible mais sans résoudre ses propres enfants ici
        // (ils seront accessibles via l'index plat dans _merged.json)
        edge.node = {
          id:          target.id,
          type:        target.type,
          name:        target.name,
          description: target.description,
          route:       target.route ?? null,
          attributes:  target.attributes ?? {},
          params:      target.params ?? {},
          features:    target.features ?? [],
          // On ne répète pas les enfants pour éviter l'explosion du fichier
          // — utiliser l'index plat pour naviguer
          children:    `[→ voir nodeIndex["${target.id}"] pour les ${target.children?.length ?? 0} enfants]`,
        }
      }
    }
    if (edge.node && typeof edge.node === 'object' && Array.isArray(edge.node.children)) {
      const nextResolving = new Set([...resolving, edge.target_id].filter(Boolean))
      edge.node = resolveNode(edge.node, index, nextResolving)
    }
    return edge
  })

  return node
}

// ── Statistiques ───────────────────────────────────────────────────────────

function computeStats(nodes) {
  let totalEdges     = 0
  let modalEdges     = 0
  let navEdges       = 0
  let actionEdges    = 0
  let tabEdges       = 0
  let formSubmitEdges = 0
  let placeholder    = 0
  let withForm       = 0

  for (const node of nodes) {
    if (!node.children) continue
    totalEdges += node.children.length
    for (const edge of node.children) {
      if (edge.link_type === 'modal_open')   modalEdges++
      if (edge.link_type === 'navigate')     navEdges++
      if (edge.link_type === 'action')       actionEdges++
      if (edge.link_type === 'tab_switch')   tabEdges++
      if (edge.link_type === 'form_submit')  formSubmitEdges++
      if (edge.node?.attributes?.scan_status === 'placeholder') placeholder++
    }
    if (node.type === 'form') withForm++
  }

  return {
    totalNodes:       nodes.length,
    totalEdges,
    byLinkType: {
      navigate:    navEdges,
      modal_open:  modalEdges,
      tab_switch:  tabEdges,
      action:      actionEdges,
      form_submit: formSubmitEdges,
    },
    modalPlaceholders: placeholder,
    formNodes:         withForm,
  }
}

// ── Main ───────────────────────────────────────────────────────────────────

function main() {
  const args      = process.argv.slice(2)
  const showStats = args.includes('--stats')

  // Lire tous les JSON sauf _merged.json lui-même
  const files = readdirSync(MAP_DIR)
    .filter(f => f.endsWith('.json') && !f.startsWith('_'))
    .sort()

  if (files.length === 0) {
    console.error(`Aucun fichier JSON trouvé dans ${MAP_DIR}.`)
    console.error('Lancez d\'abord :  node docs/map_features.mjs --page <id>')
    process.exit(1)
  }

  console.log(`\n── FUSION ${files.length} snapshots ──\n`)

  // Passe 1 : chargement et indexation
  const index    = {}   // id → nœud
  const nodes    = []   // liste ordonnée
  const failures = []

  for (const file of files) {
    try {
      const raw  = readFileSync(resolve(MAP_DIR, file), 'utf-8')
      const node = JSON.parse(raw)
      if (!node.id) throw new Error('Nœud sans id')
      index[node.id] = node
      nodes.push(node)

      // Indexer aussi les modals enfants (profondeur 1) pour la résolution croisée
      if (node.children) {
        for (const edge of node.children) {
          if (edge.node?.id) {
            index[edge.node.id] = edge.node
            // Modals imbriquées (profondeur 2+)
            if (edge.node.children) {
              for (const subEdge of edge.node.children) {
                if (subEdge.node?.id) index[subEdge.node.id] = subEdge.node
              }
            }
          }
        }
      }

      console.log(`  ✓ ${file.padEnd(35)} → ${node.id}  (${node.children?.length ?? 0} enfants)`)
    } catch (e) {
      console.error(`  ✗ ${file}: ${e.message}`)
      failures.push(file)
    }
  }

  // Passe 2 : résolution des références croisées
  console.log('\n  Résolution des références croisées…')
  for (const node of nodes) {
    resolveNode(node, index)
  }

  // Groupement par domaine fonctionnel
  const groups = {}
  for (const node of nodes) {
    const group = node.attributes?.group || 'Autre'
    ;(groups[group] = groups[group] || []).push({
      id:       node.id,
      name:     node.name,
      route:    node.route ?? null,
      type:     node.type,
      roles:    node.attributes?.roles ?? [],
      children: node.children?.length ?? 0,
    })
  }

  const stats = computeStats(nodes)

  // Document final
  const merged = {
    id:            'root',
    type:          'app',
    name:          'Marveline',
    description:   'Arbre de features complet de l\'application Marveline, généré automatiquement.',
    generatedAt:   new Date().toISOString(),
    snapshots:     files.length,
    failures:      failures.length,
    stats,
    // Index plat : id → résumé du nœud (sans enfants pour garder le fichier lisible)
    nodeIndex: Object.fromEntries(
      Object.entries(index).map(([k, v]) => [
        k,
        {
          id:          v.id,
          type:        v.type,
          name:        v.name,
          route:       v.route ?? null,
          group:       v.attributes?.group ?? null,
          roles:       v.attributes?.roles ?? [],
          params:      Object.keys(v.params ?? {}),
          features:    v.features ?? [],
          childrenIds: (v.children ?? []).map(e => e.target_id ?? e.node?.id ?? null).filter(Boolean),
        },
      ])
    ),
    // Arbre groupé (résumé par page, sans enfants inline)
    groups: Object.entries(groups).map(([name, pages]) => ({ name, pages })),
    // Arbre complet avec edges résolus (les enfants de premier niveau ont leur nœud inline)
    tree: nodes,
  }

  const outPath = resolve(MAP_DIR, '_merged.json')
  writeFileSync(outPath, JSON.stringify(merged, null, 2))

  // Rapport
  console.log(`\n✅ ${stats.totalNodes} pages/modals indexées`)
  console.log(`   ${stats.totalEdges} liens totaux`)

  if (showStats) {
    console.log('\n── Détail des liens ──')
    for (const [type, count] of Object.entries(stats.byLinkType)) {
      if (count > 0) console.log(`   ${type.padEnd(15)} ${count}`)
    }
    if (stats.modalPlaceholders > 0) {
      console.log(`\n⚠  ${stats.modalPlaceholders} modals non extraites (placeholder) — relancer avec --depth 2`)
    }
  }

  if (failures.length > 0) {
    console.log(`\n⚠  ${failures.length} fichier(s) en erreur : ${failures.join(', ')}`)
  }

  console.log(`\n📄 ${outPath}`)
  console.log(`   (${Math.round(JSON.stringify(merged).length / 1024)} Ko)`)
}

main()
