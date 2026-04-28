#!/usr/bin/env node
/**
 * Migration automatique : remplace les <h1> manuels par <PageHeader> auto-connecté.
 *
 * Usage : node scripts/migrate-pageheader.mjs [--dry-run]
 *
 * Patterns reconnus :
 * 1. <h1 className="...">Titre</h1>  seul
 * 2. <h1>...</h1> + <p>subtitle</p> dans un <div> wrapper
 * 3. Import existant de PageHeader depuis @shared → remplacé par @/components/PageHeader
 */
import { readFileSync, writeFileSync, readdirSync, statSync } from 'fs'
import { join, relative } from 'path'

const DRY_RUN = process.argv.includes('--dry-run')
const PAGES_DIR = join(import.meta.dirname, '../apps/marveline/src/pages')

// Pages à exclure (cas spéciaux, layouts, ou déjà migrées correctement)
const EXCLUDE = new Set([
  'errors/NotFoundPage.tsx',      // 404 page — pas de crossfade
  'landing/AppSelectorPage.tsx',  // landing — pas dans le layout
])

let stats = { scanned: 0, migrated: 0, skipped: 0, errors: [] }

function findTsxFiles(dir) {
  const files = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory() && entry.name !== 'components' && entry.name !== '__tests__') {
      files.push(...findTsxFiles(full))
    } else if (entry.isFile() && entry.name.endsWith('.tsx') && !entry.name.includes('.test.')) {
      files.push(full)
    }
  }
  return files
}

function migrateFile(filePath) {
  const rel = relative(PAGES_DIR, filePath)
  if (EXCLUDE.has(rel)) { stats.skipped++; return }

  let content = readFileSync(filePath, 'utf-8')
  stats.scanned++

  // Skip si déjà importé depuis @/components/PageHeader
  if (content.includes("from '@/components/PageHeader'")) {
    stats.skipped++
    return
  }

  // Check si le fichier a un <h1
  if (!content.includes('<h1')) {
    stats.skipped++
    return
  }

  let modified = false
  let newContent = content

  // 1. Remplacer import existant de PageHeader depuis @shared
  if (newContent.includes("PageHeader") && newContent.includes("@shared")) {
    // Cas: import { PageHeader } from '@shared/components/ui/Breadcrumb'
    newContent = newContent.replace(
      /import\s*\{[^}]*PageHeader[^}]*\}\s*from\s*'@shared\/components\/ui(?:\/Breadcrumb)?';?\n?/,
      "import { PageHeader } from '@/components/PageHeader'\n"
    )
    // Aussi supprimer le type import si présent
    newContent = newContent.replace(
      /import\s+type\s*\{[^}]*PageHeaderProps[^}]*\}\s*from\s*'@shared\/components\/ui(?:\/Breadcrumb)?';?\n?/,
      ''
    )
    modified = newContent !== content
  }

  // 2. Remplacer import depuis @shared/components/ui barrel
  if (newContent.match(/import\s*\{[^}]*PageHeader[^}]*\}\s*from\s*'@shared\/components\/ui'/)) {
    // Remove PageHeader from the barrel import
    newContent = newContent.replace(
      /import\s*\{([^}]*)\bPageHeader\b,?\s*([^}]*)\}\s*from\s*'@shared\/components\/ui'/,
      (match, before, after) => {
        const remaining = (before + after).replace(/,\s*,/g, ',').replace(/^[,\s]+|[,\s]+$/g, '').trim()
        const pageHeaderImport = "import { PageHeader } from '@/components/PageHeader'"
        if (!remaining) return pageHeaderImport
        return `import { ${remaining} } from '@shared/components/ui'\n${pageHeaderImport}`
      }
    )
    modified = true
  }

  // 3. Supprimer le câblage useHeaderTitle si présent
  if (newContent.includes('useHeaderTitle')) {
    newContent = newContent.replace(/import\s*\{[^}]*useHeaderTitle[^}]*\}\s*from\s*'@\/layout\/HeaderTitleContext';?\n?/, '')
    newContent = newContent.replace(/\s*const\s*\{[^}]*setTitle[^}]*setProgress[^}]*\}\s*=\s*useHeaderTitle\(\)\s*\n?/, '\n')
    newContent = newContent.replace(/\s*const\s+onTitleChange\s*=\s*useCallback\([^)]*\)\s*\n?/, '\n')
    newContent = newContent.replace(/\s*const\s+onProgressChange\s*=\s*useCallback\([^)]*\)\s*\n?/, '\n')
    // Supprimer les props onTitleChange/onProgressChange du JSX
    newContent = newContent.replace(/\s+onTitleChange=\{onTitleChange\}/g, '')
    newContent = newContent.replace(/\s+onProgressChange=\{onProgressChange\}/g, '')
    modified = true
  }

  // 4. Si pas encore d'import PageHeader, l'ajouter + remplacer les h1 simples
  if (!newContent.includes("PageHeader")) {
    // Pattern: <h1 className="...">Texte statique</h1> seul (pas de JSX complexe)
    const h1SimpleRegex = /^(\s*)<h1[^>]*>([^<{]+)<\/h1>\s*$/m
    const match = newContent.match(h1SimpleRegex)
    if (match) {
      const indent = match[1]
      const title = match[2].trim()

      // Check si il y a un <p> subtitle juste après
      const afterH1 = newContent.slice(newContent.indexOf(match[0]) + match[0].length)
      const subtitleMatch = afterH1.match(/^\s*<p[^>]*>([^<]+)<\/p>\s*$/m)

      let replacement
      if (subtitleMatch && afterH1.indexOf(subtitleMatch[0]) < 100) {
        const subtitle = subtitleMatch[1].trim()
        replacement = `${indent}<PageHeader title="${title}" subtitle="${subtitle}" />`
        // Supprimer aussi le <p> subtitle
        newContent = newContent.replace(subtitleMatch[0], '')
      } else {
        replacement = `${indent}<PageHeader title="${title}" />`
      }

      newContent = newContent.replace(match[0], replacement)

      // Ajouter l'import après le premier import
      const firstImport = newContent.match(/^import\s/m)
      if (firstImport) {
        const idx = newContent.indexOf(firstImport[0])
        newContent = newContent.slice(0, idx) + "import { PageHeader } from '@/components/PageHeader'\n" + newContent.slice(idx)
      }

      // Supprimer le <div> wrapper s'il ne contient plus que le PageHeader
      // Pattern: <div>\n  <PageHeader ... />\n</div>
      newContent = newContent.replace(
        /(\s*)<div>\s*\n\s*(<PageHeader[^/]*\/>)\s*\n\s*<\/div>/g,
        '$1$2'
      )

      modified = true
    }
  }

  if (modified && newContent !== content) {
    if (DRY_RUN) {
      console.log(`[DRY] ${rel}`)
    } else {
      writeFileSync(filePath, newContent, 'utf-8')
      console.log(`[OK]  ${rel}`)
    }
    stats.migrated++
  }
}

// Run
const files = findTsxFiles(PAGES_DIR)
console.log(`Scanning ${files.length} files in pages/...\n`)

for (const f of files) {
  try {
    migrateFile(f)
  } catch (err) {
    stats.errors.push({ file: relative(PAGES_DIR, f), error: err.message })
  }
}

console.log(`\n--- Results ---`)
console.log(`Scanned: ${stats.scanned}`)
console.log(`Migrated: ${stats.migrated}`)
console.log(`Skipped: ${stats.skipped}`)
if (stats.errors.length) {
  console.log(`Errors: ${stats.errors.length}`)
  stats.errors.forEach(e => console.log(`  ${e.file}: ${e.error}`))
}
if (DRY_RUN) console.log(`\n(dry run — aucun fichier modifié)`)
