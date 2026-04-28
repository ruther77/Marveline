#!/usr/bin/env node
import fs from 'fs'
import path from 'path'
import { ESLint } from 'eslint'

const root = process.cwd()
const budgetPath = path.join(root, 'config', 'lint-warning-budget.json')

if (!fs.existsSync(budgetPath)) {
  console.error(`Missing lint warning budget: ${budgetPath}`)
  process.exit(2)
}

const budget = JSON.parse(fs.readFileSync(budgetPath, 'utf8'))

const eslint = new ESLint({
  cwd: root,
  extensions: ['.ts', '.tsx'],
  errorOnUnmatchedPattern: false,
})

const report = await eslint.lintFiles(['.'])

let errors = 0
let warnings = 0
const byRule = {}

for (const file of report) {
  for (const msg of file.messages || []) {
    const rule = msg.ruleId || 'unknown'
    if (msg.severity === 2) {
      errors += 1
    } else if (msg.severity === 1) {
      warnings += 1
      byRule[rule] = (byRule[rule] || 0) + 1
    }
  }
}

if (errors > 0) {
  console.error(`Lint errors detected: ${errors}. Fix errors before warning budget check.`)
  process.exit(1)
}

const maxTotal = budget.max_total_warnings
const maxByRule = budget.max_by_rule || {}
const failures = []

if (typeof maxTotal === 'number' && warnings > maxTotal) {
  failures.push(`Total warnings ${warnings} > budget ${maxTotal}`)
}

for (const [rule, count] of Object.entries(byRule)) {
  if (!(rule in maxByRule)) {
    failures.push(`Unbudgeted warning rule '${rule}' detected (${count})`)
    continue
  }
  if (count > maxByRule[rule]) {
    failures.push(`Rule '${rule}' warnings ${count} > budget ${maxByRule[rule]}`)
  }
}

if (failures.length) {
  console.error('Lint warning budget check failed:')
  for (const line of failures) console.error(`- ${line}`)
  console.error('Current warning counts by rule:')
  for (const [rule, count] of Object.entries(byRule).sort()) {
    console.error(`- ${rule}: ${count}`)
  }
  process.exit(1)
}

console.log('Lint warning budget check passed.')
console.log(`Warnings: ${warnings}/${maxTotal}`)
for (const [rule, count] of Object.entries(byRule).sort()) {
  const limit = maxByRule[rule]
  console.log(`- ${rule}: ${count}/${limit}`)
}
