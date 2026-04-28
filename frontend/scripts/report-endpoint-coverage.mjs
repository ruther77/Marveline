#!/usr/bin/env node
/* eslint-env node */
import fs from 'fs'
import path from 'path'
import ts from 'typescript'

const frontendRoot = process.cwd()
const repoRoot = path.resolve(frontendRoot, '..')

const apiDir = path.join(frontendRoot, 'src', 'api')
const queriesDir = path.join(apiDir, 'queries')
const backendDir = path.join(repoRoot, 'app', 'api', 'v1', 'endpoints')
const taxonomyCsv = path.join(repoRoot, 'docs', 'endpoint_taxonomy_v1.csv')
const SYSTEM_EXCEPTION_KEYS = new Set([
  'GET /.well-known/jwks.json',
])

if (!fs.existsSync(apiDir) || !fs.existsSync(backendDir) || !fs.existsSync(taxonomyCsv)) {
  console.error('Expected to run from frontend/ with ../app and ../docs available.')
  process.exit(2)
}

function walk(dir, out = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ent.name === 'node_modules' || ent.name.startsWith('.')) continue
    const abs = path.join(dir, ent.name)
    if (ent.isDirectory()) walk(abs, out)
    else out.push(abs)
  }
  return out
}

function normalizePath(raw) {
  let s = String(raw ?? '').trim()
  if (!s) return ''
  if (!s.startsWith('/')) s = `/${s}`
  s = s.replace(/\$\{[^}]+\}/g, '{}')
  if (s.endsWith('{}') && !s.endsWith('/{}')) s = s.slice(0, -2)
  s = s.split('?')[0]
  s = s.replace(/\{[^}]+\}/g, '{}')
  s = s.replace(/\/\d+(?=\/|$)/g, '/{}')
  s = s.replace(/\/+/g, '/')
  if (s.length > 1 && s.endsWith('/')) s = s.slice(0, -1)
  return s
}

function parseCsvLine(line) {
  const out = []
  let cur = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i]
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"'
        i += 1
      } else {
        inQuotes = !inQuotes
      }
    } else if (ch === ',' && !inQuotes) {
      out.push(cur)
      cur = ''
    } else {
      cur += ch
    }
  }
  out.push(cur)
  return out
}

function parseTaxonomy() {
  const lines = fs.readFileSync(taxonomyCsv, 'utf8').split(/\r?\n/).filter(Boolean)
  const header = parseCsvLine(lines[0])
  const iMethod = header.indexOf('method')
  const iPath = header.indexOf('path')
  const iCategory = header.indexOf('category')

  const map = new Map()
  for (let i = 1; i < lines.length; i += 1) {
    const row = parseCsvLine(lines[i])
    const method = (row[iMethod] || '').trim().toUpperCase()
    const endpointPath = normalizePath(row[iPath] || '')
    const category = (row[iCategory] || '').trim()
    if (!method || !endpointPath) continue
    map.set(`${method} ${endpointPath}`, category)
  }
  return map
}

function extractStringLike(expr, constMap) {
  if (!expr) return null
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) return expr.text
  if (ts.isIdentifier(expr)) return constMap.get(expr.text) ?? null
  if (ts.isParenthesizedExpression(expr)) return extractStringLike(expr.expression, constMap)
  if (ts.isConditionalExpression(expr)) {
    const a = extractStringLike(expr.whenTrue, constMap)
    const b = extractStringLike(expr.whenFalse, constMap)
    return a || b
  }
  if (ts.isBinaryExpression(expr) && expr.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    const left = extractStringLike(expr.left, constMap)
    const right = extractStringLike(expr.right, constMap)
    if (left == null && right == null) return null
    return `${left ?? ''}${right ?? ''}`
  }
  if (ts.isTemplateExpression(expr)) {
    let out = expr.head.text
    for (const span of expr.templateSpans) {
      const lit = span.literal.text || ''
      const resolved = extractStringLike(span.expression, constMap)
      if (lit.startsWith('?')) {
        if (out.endsWith('/')) out += `${resolved ?? '{}'}${lit}`
        else out += lit
        continue
      }
      if (typeof resolved === 'string' && resolved.startsWith('?')) {
        out += lit
        continue
      }
      if (!lit && !out.endsWith('/') && resolved == null) {
        continue
      }
      out += `${resolved ?? '{}'}${lit}`
    }
    return out
  }
  return null
}

function collectConstMap(sf) {
  const out = new Map()

  function visit(node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const resolved = extractStringLike(node.initializer, out)
      if (resolved != null) out.set(node.name.text, resolved)
    }
    ts.forEachChild(node, visit)
  }

  visit(sf)
  return out
}

function collectTopLevelConstMap(sf) {
  const out = new Map()
  for (const stmt of sf.statements) {
    if (!ts.isVariableStatement(stmt)) continue
    for (const decl of stmt.declarationList.declarations) {
      if (!ts.isIdentifier(decl.name) || !decl.initializer) continue
      const resolved = extractStringLike(decl.initializer, out)
      if (resolved != null) out.set(decl.name.text, resolved)
    }
  }
  return out
}

function scanFrontendApi() {
  const files = walk(apiDir).filter((f) => f.endsWith('.ts') && !f.includes('/queries/') && !f.includes('__tests__'))
  const apiFns = []

  for (const file of files) {
    const rel = path.relative(frontendRoot, file).replace(/\\/g, '/')
    const text = fs.readFileSync(file, 'utf8')
    const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
    const topLevelConstMap = collectTopLevelConstMap(sf)

    const collectCalls = (node, out, constMap) => {
      if (ts.isCallExpression(node)) {
        if (ts.isPropertyAccessExpression(node.expression)) {
          const obj = node.expression.expression
          const method = node.expression.name.text
          if (ts.isIdentifier(obj) && obj.text === 'api' && ['get', 'post', 'patch', 'put', 'delete'].includes(method)) {
            const raw = extractStringLike(node.arguments[0], constMap)
            if (raw != null) {
              const endpointPath = normalizePath(raw)
              if (endpointPath) out.push({ method: method.toUpperCase(), path: endpointPath, file: rel })
            }
          }
        } else if (ts.isIdentifier(node.expression) && node.expression.text === 'fetchBlob') {
          const raw = extractStringLike(node.arguments[0], constMap)
          if (raw != null) {
            const endpointPath = normalizePath(raw)
            if (endpointPath) out.push({ method: 'GET', path: endpointPath, file: rel })
          }
        } else if (ts.isIdentifier(node.expression) && node.expression.text === 'fetchFormData') {
          const raw = extractStringLike(node.arguments[0], constMap)
          if (raw != null) {
            const endpointPath = normalizePath(raw)
            if (endpointPath) out.push({ method: 'POST', path: endpointPath, file: rel })
          }
        }
      }
      ts.forEachChild(node, (child) => collectCalls(child, out, constMap))
    }

    sf.forEachChild((node) => {
      if (!ts.isVariableStatement(node)) return
      const isExport = (node.modifiers || []).some((m) => m.kind === ts.SyntaxKind.ExportKeyword)
      if (!isExport) return

      for (const decl of node.declarationList.declarations) {
        if (!ts.isIdentifier(decl.name) || !decl.initializer || !ts.isObjectLiteralExpression(decl.initializer)) continue
        const apiObj = decl.name.text
        if (!apiObj.endsWith('Api')) continue

        for (const prop of decl.initializer.properties) {
          let fnName = null
          let body = null
          if (ts.isPropertyAssignment(prop) && ts.isIdentifier(prop.name)) {
            fnName = prop.name.text
            if (ts.isArrowFunction(prop.initializer) || ts.isFunctionExpression(prop.initializer)) body = prop.initializer.body
          } else if (ts.isMethodDeclaration(prop) && ts.isIdentifier(prop.name)) {
            fnName = prop.name.text
            body = prop.body
          }
          if (!fnName || !body) continue
          const constMap = collectConstMap(body)
          for (const [k, v] of topLevelConstMap.entries()) {
            if (!constMap.has(k)) constMap.set(k, v)
          }
          const endpoints = []
          collectCalls(body, endpoints, constMap)
          apiFns.push({ ref: `${apiObj}.${fnName}`, file: rel, endpoints })
        }
      }
    })
  }

  const calls = apiFns.flatMap((fn) => fn.endpoints.map((ep) => ({ ...ep, file: fn.file })))
  return { calls, apiFns }
}

function scanBackend() {
  const files = walk(backendDir).filter((f) => f.endsWith('.py'))
  const out = []
  for (const file of files) {
    const rel = path.relative(repoRoot, file).replace(/\\/g, '/')
    const text = fs.readFileSync(file, 'utf8')
    const prefixByRouter = {}

    const prefixRe = /(\w+)\s*=\s*APIRouter\([\s\S]*?prefix\s*=\s*["']([^"']+)["'][\s\S]*?\)/g
    let m
    while ((m = prefixRe.exec(text)) !== null) {
      prefixByRouter[m[1]] = m[2]
    }

    const routeRe = /@(\w+)\.(get|post|patch|put|delete)\(\s*["']([^"']*)["']/g
    while ((m = routeRe.exec(text)) !== null) {
      const router = m[1]
      const method = m[2].toUpperCase()
      const routePath = m[3] || ''
      const fullPath = normalizePath(`${prefixByRouter[router] || ''}${routePath}`)
      if (!fullPath) continue
      out.push({ method, path: fullPath, file: rel })
    }
  }
  return out
}

function groupBy(rows, keyFn) {
  const map = new Map()
  for (const row of rows) {
    const key = keyFn(row)
    map.set(key, (map.get(key) || 0) + 1)
  }
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([key, count]) => ({ key, count }))
}

function uniqueByMethodPath(rows) {
  const map = new Map()
  for (const row of rows) map.set(`${row.method} ${row.path}`, row)
  return [...map.values()]
}

const taxonomyByKey = parseTaxonomy()
const backend = uniqueByMethodPath(scanBackend())
const { calls: frontendCalls, apiFns } = scanFrontendApi()
const frontend = uniqueByMethodPath(frontendCalls)

const frontendSet = new Set(frontend.map((r) => `${r.method} ${r.path}`))
const backendSet = new Set(backend.map((r) => `${r.method} ${r.path}`))

const productBackend = backend.filter((r) => taxonomyByKey.get(`${r.method} ${r.path}`) === 'product-required')
const productMissingInFrontend = productBackend.filter((r) => !frontendSet.has(`${r.method} ${r.path}`))

const unknownTaxonomy = backend.filter((r) => !taxonomyByKey.has(`${r.method} ${r.path}`))
const taxonomyOrphansRaw = [...taxonomyByKey.keys()]
  .filter((k) => !backendSet.has(k))
  .map((k) => ({ key: k, category: taxonomyByKey.get(k) }))
const systemExceptions = taxonomyOrphansRaw.filter((row) => SYSTEM_EXCEPTION_KEYS.has(row.key))
const taxonomyOrphans = taxonomyOrphansRaw.filter((row) => !SYSTEM_EXCEPTION_KEYS.has(row.key))

const hooksText = walk(queriesDir)
  .filter((f) => f.endsWith('.ts'))
  .map((f) => fs.readFileSync(f, 'utf8'))
  .join('\n')
const apiFnsWithoutHook = apiFns.filter((f) => f.endpoints.length > 0 && !hooksText.includes(f.ref))

const report = {
  backend_unique: backend.length,
  backend_product_required: productBackend.length,
  frontend_api_unique: frontend.length,
  product_missing_in_frontend_count: productMissingInFrontend.length,
  product_missing_in_frontend_by_module: groupBy(productMissingInFrontend, (r) => r.path.split('/').filter(Boolean)[0] || 'root'),
  product_missing_in_frontend: productMissingInFrontend,
  api_functions_total: apiFns.length,
  api_functions_without_hook_count: apiFnsWithoutHook.length,
  api_functions_without_hook_by_file: groupBy(apiFnsWithoutHook, (r) => r.file),
  taxonomy_unknown_for_backend_count: unknownTaxonomy.length,
  taxonomy_unknown_for_backend: unknownTaxonomy,
  system_exceptions_count: systemExceptions.length,
  system_exceptions: systemExceptions,
  taxonomy_orphans_count: taxonomyOrphans.length,
  taxonomy_orphans: taxonomyOrphans,
}

const wantsJson = process.argv.includes('--json')
if (wantsJson) {
  console.log(JSON.stringify(report, null, 2))
} else {
  console.log('Endpoint coverage report')
  console.log(`- backend unique: ${report.backend_unique}`)
  console.log(`- backend product-required: ${report.backend_product_required}`)
  console.log(`- frontend api unique: ${report.frontend_api_unique}`)
  console.log(`- product missing in frontend: ${report.product_missing_in_frontend_count}`)
  console.log(`- api functions without hook: ${report.api_functions_without_hook_count}`)
  console.log(`- taxonomy unknown for backend: ${report.taxonomy_unknown_for_backend_count}`)
  console.log(`- system exceptions: ${report.system_exceptions_count}`)
  console.log(`- taxonomy orphans: ${report.taxonomy_orphans_count}`)
}

if (process.argv.includes('--fail-on-missing') && report.product_missing_in_frontend_count > 0) {
  process.exit(1)
}
