#!/usr/bin/env node
/**
 * migrate-lazy-routes.mjs
 *
 * Migrates TanStack Router v1 file-based routes from static createFileRoute
 * to lazy-loaded createLazyFileRoute by creating companion .lazy.tsx files.
 *
 * Convention:
 *   route.tsx      → keeps createFileRoute with validateSearch only (no component)
 *   route.lazy.tsx → new file, createLazyFileRoute with component only
 *
 * Skip rules:
 *   - Files containing <Outlet (layout files)
 *   - Files containing beforeLoad: (auth guards, redirects)
 *   - Files with no component: prop
 *   - __root.tsx, $.tsx (special files)
 *   - Files where component is not a named default import from @/pages/ or elsewhere
 *     (inline components defined in the same file)
 *
 * Usage: node scripts/migrate-lazy-routes.mjs [--dry-run]
 *
 * After running: cd frontend && npm run build  (regenerates routeTree.gen.ts)
 */

import { readFileSync, writeFileSync, existsSync, readdirSync } from 'fs'
import { join, dirname, basename } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROUTES_DIR = join(__dirname, '..', 'frontend', 'src', 'routes')
const DRY_RUN = process.argv.includes('--dry-run')

if (DRY_RUN) console.log('🔬 DRY RUN — no files will be written\n')

// ─── Stats ────────────────────────────────────────────────────────────────────

const stats = { migrated: 0, skipped: 0, errors: 0 }
const migrated = []
const skipped = []
const errors = []

// ─── Utilities ────────────────────────────────────────────────────────────────

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function walkRoutes(dir) {
  const files = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name)
    if (entry.isDirectory()) {
      files.push(...walkRoutes(fullPath))
    } else if (
      entry.name.endsWith('.tsx') &&
      !entry.name.endsWith('.lazy.tsx')
    ) {
      files.push(fullPath)
    }
  }
  return files
}

// ─── Analysis ─────────────────────────────────────────────────────────────────

function analyzeRoute(content, filePath) {
  const fileName = basename(filePath)

  if (fileName === '__root.tsx' || fileName === '$.tsx') {
    return { skip: true, reason: 'special file (__root / catch-all)' }
  }

  const lazyPath = filePath.replace(/\.tsx$/, '.lazy.tsx')
  if (existsSync(lazyPath)) {
    return { skip: true, reason: 'companion .lazy.tsx already exists' }
  }

  // Layout detection: contains <Outlet (with space, / or >)
  if (/<Outlet[\s/>]/.test(content)) {
    return { skip: true, reason: 'layout (contains <Outlet>)' }
  }

  // Auth guard / redirect detection
  if (/beforeLoad\s*:/.test(content)) {
    return { skip: true, reason: 'has beforeLoad' }
  }

  // Must have a component prop
  if (!/component\s*:/.test(content)) {
    return { skip: true, reason: 'no component prop' }
  }

  // Extract route path from createFileRoute('...')
  const pathMatch = content.match(/createFileRoute\('([^']+)'\)/)
  if (!pathMatch) {
    return { skip: true, reason: 'createFileRoute path not found' }
  }
  const routePath = pathMatch[1]

  // Extract component name from component: XxxPage
  const componentMatch = content.match(/component\s*:\s*(\w+)/)
  if (!componentMatch) {
    return { skip: true, reason: 'component value not parseable' }
  }
  const componentName = componentMatch[1]

  // Find the default import line for this component name
  // Pattern: import ComponentName from 'some/path'   (no "type", no braces)
  const importRegex = new RegExp(
    `^import\\s+${escapeRegex(componentName)}\\s+from\\s+['"]([^'"]+)['"]\\s*$`,
    'm'
  )
  const importMatch = content.match(importRegex)
  if (!importMatch) {
    return {
      skip: true,
      reason: `no default import found for '${componentName}' (likely inline component)`,
    }
  }
  const importPath = importMatch[1]
  const importLine = importMatch[0]

  const hasValidateSearch = /validateSearch\s*:/.test(content)

  return {
    skip: false,
    routePath,
    componentName,
    importPath,
    importLine,
    hasValidateSearch,
    lazyPath,
  }
}

// ─── Eager file transformation ────────────────────────────────────────────────

function transformEagerFile(content, analysis) {
  const { componentName, importLine } = analysis
  let out = content

  // 1. Remove the component's import line (with trailing newline)
  const importLineEscaped = escapeRegex(importLine)
  out = out.replace(new RegExp(importLineEscaped + '\\n?'), '')

  // 2a. Single-line options: ({ component: Name }) → ({})
  out = out.replace(
    new RegExp(`\\(\\{\\s*component\\s*:\\s*${escapeRegex(componentName)}\\s*\\}\\)`),
    '({})'
  )

  // 2b. Multi-line options: remove the component: Name, line
  //     \s* matches leading whitespace+newline; ,? matches optional trailing comma
  out = out.replace(
    new RegExp(`\\s*component\\s*:\\s*${escapeRegex(componentName)}\\s*,?\\n`),
    '\n'
  )

  // 3. Collapse now-empty multi-line options ({\n...\n}) → ({})
  out = out.replace(/\(\{\s*\n\s*\n?\s*\}\)/, '({})')

  // 4. Collapse 3+ consecutive blank lines to max 2
  out = out.replace(/\n{3,}/g, '\n\n')

  return out
}

// ─── Lazy file generation ─────────────────────────────────────────────────────

function generateLazyFile(analysis) {
  const { routePath, componentName, importPath } = analysis
  return (
    `import { createLazyFileRoute } from '@tanstack/react-router'\n` +
    `import ${componentName} from '${importPath}'\n` +
    `\n` +
    `export const Route = createLazyFileRoute('${routePath}')({\n` +
    `  component: ${componentName},\n` +
    `})\n`
  )
}

// ─── Process one file ─────────────────────────────────────────────────────────

function processFile(filePath) {
  const rel = filePath.replace(ROUTES_DIR + '/', '')
  let content

  try {
    content = readFileSync(filePath, 'utf8')
  } catch (err) {
    stats.errors++
    errors.push({ file: rel, error: `read error: ${err.message}` })
    return
  }

  const analysis = analyzeRoute(content, filePath)

  if (analysis.skip) {
    stats.skipped++
    skipped.push({ file: rel, reason: analysis.reason })
    return
  }

  try {
    const lazyContent = generateLazyFile(analysis)
    const eagerContent = transformEagerFile(content, analysis)

    if (!DRY_RUN) {
      writeFileSync(analysis.lazyPath, lazyContent, 'utf8')
      writeFileSync(filePath, eagerContent, 'utf8')
    }

    stats.migrated++
    migrated.push({
      file: rel,
      type: analysis.hasValidateSearch ? 'B' : 'A',
      component: analysis.componentName,
    })
  } catch (err) {
    stats.errors++
    errors.push({ file: rel, error: `transform error: ${err.message}` })
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────

console.log(`🔍 Scanning: ${ROUTES_DIR}\n`)

const files = walkRoutes(ROUTES_DIR)
console.log(`📁 Found ${files.length} candidate route files\n`)

for (const file of files) {
  processFile(file)
}

// ─── Report ───────────────────────────────────────────────────────────────────

const line = '─'.repeat(62)
console.log(line)
console.log('  MIGRATION REPORT')
console.log(line)
console.log(`  ✅ Migrated : ${stats.migrated} files`)
console.log(`      Type A (component only)        : ${migrated.filter(f => f.type === 'A').length}`)
console.log(`      Type B (component+validateSearch): ${migrated.filter(f => f.type === 'B').length}`)
console.log(`  ⏭️  Skipped  : ${stats.skipped} files`)
console.log(`  ❌ Errors   : ${stats.errors} files`)
console.log(line)

if (migrated.length > 0) {
  console.log('\n[MIGRATED]')
  for (const { file, type, component } of migrated) {
    console.log(`  [${type}] ${file}  →  ${component}`)
  }
}

// Group skipped by reason for readability
if (skipped.length > 0) {
  console.log('\n[SKIPPED]')
  const byReason = {}
  for (const { file, reason } of skipped) {
    ;(byReason[reason] = byReason[reason] || []).push(file)
  }
  for (const [reason, files] of Object.entries(byReason)) {
    console.log(`\n  Reason: ${reason}`)
    for (const f of files) console.log(`    ${f}`)
  }
}

if (errors.length > 0) {
  console.log('\n[ERRORS]')
  for (const { file, error } of errors) {
    console.log(`  ${file}: ${error}`)
  }
}

if (stats.errors > 0) {
  console.log('\n⚠️  Some files had errors — review above before building.')
  process.exit(1)
}

console.log('\n✨ Done!')
if (!DRY_RUN) {
  console.log('   Next: cd frontend && npm run build')
  console.log('         → routeTree.gen.ts will be regenerated automatically')
}
