#!/usr/bin/env node
import fs from 'fs'
import path from 'path'

const root = process.cwd()
const srcRoot = path.join(root, 'src')
const allowPath = path.join(root, 'config', 'api-access-allowlist.json')

if (!fs.existsSync(srcRoot)) {
  console.error('Expected to run from frontend/ directory')
  process.exit(2)
}
if (!fs.existsSync(allowPath)) {
  console.error(`Missing allowlist: ${allowPath}`)
  process.exit(2)
}

const allow = JSON.parse(fs.readFileSync(allowPath, 'utf8'))
const allowset = new Set((allow.allowlist || []).map((p) => p.replace(/\\/g, '/')))
const budget = allow.budget || {}

const allowedDirs = ['src/api/', 'src/api/queries/']
const exts = new Set(['.ts', '.tsx'])
const apiImportRe = /from\s+['\"](@\/api\/[^'\"]+|\.\.\/api\/[^'\"]+|\.\/api\/[^'\"]+)['\"]/g

function walk(dir) {
  const out = []
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (['node_modules', 'dist', '.tanstack', '.vite', 'coverage'].includes(ent.name)) continue
    const p = path.join(dir, ent.name)
    if (ent.isDirectory()) out.push(...walk(p))
    else if (exts.has(path.extname(ent.name))) out.push(p)
  }
  return out
}

function isAllowedLocation(rel) {
  return allowedDirs.some((d) => rel.startsWith(d))
}

function isNonRuntimeFile(rel) {
  return rel.includes('/__tests__/') || /\.(test|spec)\.(ts|tsx)$/.test(rel)
}

const blockingViolations = []
const allowlistedViolations = []
for (const file of walk(srcRoot)) {
  const rel = path.relative(root, file).replace(/\\/g, '/')
  if (isAllowedLocation(rel) || isNonRuntimeFile(rel)) continue

  const text = fs.readFileSync(file, 'utf8')
  const imports = [...text.matchAll(apiImportRe)]
    .map((m) => m[1])
    .filter((imp) => !imp.includes('/api/queries'))
  if (!imports.length) continue

  const entry = { file: rel, imports: [...new Set(imports)] }
  if (allowset.has(rel)) {
    allowlistedViolations.push(entry)
  } else {
    blockingViolations.push(entry)
  }
}

const activeAllowlistedFiles = new Set(allowlistedViolations.map((v) => v.file))
const staleAllowlistEntries = [...allowset].filter((p) => !activeAllowlistedFiles.has(p))

const budgetErrors = []
if (Number.isInteger(budget.max_allowlist_entries) && allowset.size > budget.max_allowlist_entries) {
  budgetErrors.push(
    `Allowlist entries ${allowset.size} > budget ${budget.max_allowlist_entries}`
  )
}
if (
  Number.isInteger(budget.max_active_allowlisted_files) &&
  allowlistedViolations.length > budget.max_active_allowlisted_files
) {
  budgetErrors.push(
    `Active allowlisted files ${allowlistedViolations.length} > budget ${budget.max_active_allowlisted_files}`
  )
}

if (!blockingViolations.length && !budgetErrors.length) {
  console.log('API access check passed: no new direct api imports outside allowed layers.')
  console.log(
    `Allowlist status: active=${allowlistedViolations.length}, entries=${allowset.size}, stale=${staleAllowlistEntries.length}`
  )
  if (staleAllowlistEntries.length) {
    console.log('Stale allowlist entries (cleanup suggested):')
    for (const p of staleAllowlistEntries) console.log(`- ${p}`)
  }
  process.exit(0)
}

console.error('API access check failed.')
if (blockingViolations.length) {
  console.error('New direct api imports detected outside src/api and src/api/queries:')
  for (const v of blockingViolations) {
    console.error(`- ${v.file}`)
    for (const i of v.imports) {
      console.error(`  - ${i}`)
    }
  }
}

if (budgetErrors.length) {
  console.error('Allowlist budget violations:')
  for (const msg of budgetErrors) {
    console.error(`- ${msg}`)
  }
}

if (staleAllowlistEntries.length) {
  console.error('Stale allowlist entries:')
  for (const p of staleAllowlistEntries) {
    console.error(`- ${p}`)
  }
}
process.exit(1)
