/**
 * E2E Network Audit — Capture et analyse les appels API par page.
 *
 * Objectif : constater les vrais appels reseau apres les optimisations
 * et identifier les gaps backend-frontend (endpoints manquants, payloads lourds).
 *
 * Usage : npx playwright test network-audit --headed
 */

import { test, expect, type Page, type Response } from '@playwright/test'

// Credentials reels
const ADMIN_EMAIL = 'admin@carocorp.dev'
const ADMIN_PASSWORD = 'Admin123!'
const API_BASE_URL = 'http://localhost:8001/api/v1'

/** Login via API puis injecte le token dans localStorage (apres navigation initiale). */
async function loginForAudit(page: Page) {
  // 1. Naviguer d'abord pour etablir l'origine (sinon localStorage inaccessible)
  await page.goto('/login', { waitUntil: 'domcontentloaded' })

  // 2. Login via API
  const response = await page.request.post(`${API_BASE_URL}/auth/login`, {
    form: { username: ADMIN_EMAIL, password: ADMIN_PASSWORD },
  })
  expect(response.ok(), `Login failed: ${response.status()}`).toBeTruthy()
  const data = await response.json()

  // 3. Injecter dans localStorage (maintenant qu'on a un origin)
  await page.evaluate(
    ({ accessToken }) => {
      localStorage.setItem('marveline-auth', JSON.stringify({
        state: { isAuthenticated: true },
        version: 0,
      }))
    },
    { accessToken: data.access_token },
  )

  // 4. Naviguer vers le dashboard
  await page.goto('/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(3000)
}

// ── Types ──────────────────────────────────────────────────────────────────────

interface CapturedRequest {
  url: string
  path: string
  method: string
  status: number
  size: number
  duration: number
  timestamp: number
}

interface PageAudit {
  page: string
  url: string
  requests: CapturedRequest[]
  totalRequests: number
  totalApiRequests: number
  authRequests: number
  dataRequests: number
  heavyPayloads: CapturedRequest[]
  duplicates: Map<string, number>
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function extractPath(url: string): string {
  try {
    const u = new URL(url)
    return u.pathname + u.search
  } catch {
    return url
  }
}

async function capturePageRequests(
  page: Page,
  targetUrl: string,
  pageName: string,
  waitMs = 3000,
): Promise<PageAudit> {
  const requests: CapturedRequest[] = []
  const startTimes = new Map<string, number>()

  // Capture les timings de depart
  page.on('request', (req) => {
    if (req.url().includes('/api/')) {
      startTimes.set(req.url() + req.method(), Date.now())
    }
  })

  // Capture les reponses
  const responseHandler = async (response: Response) => {
    const url = response.url()
    if (!url.includes('/api/')) return

    const method = response.request().method()
    const startTime = startTimes.get(url + method) ?? Date.now()
    let size = 0
    try {
      const body = await response.body()
      size = body.length
    } catch {
      // Response body unavailable (redirect, etc.)
    }

    requests.push({
      url,
      path: extractPath(url),
      method,
      status: response.status(),
      size,
      duration: Date.now() - startTime,
      timestamp: Date.now(),
    })
  }
  page.on('response', responseHandler)

  // Naviguer
  await page.goto(targetUrl, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(waitMs)

  // Cleanup listeners
  page.removeListener('response', responseHandler)

  // Analyse
  const apiRequests = requests.filter((r) => r.path.includes('/api/'))
  const authRequests = apiRequests.filter(
    (r) =>
      r.path.includes('/auth/') ||
      r.path.includes('/users/me'),
  )
  const dataRequests = apiRequests.filter(
    (r) =>
      !r.path.includes('/auth/') &&
      !r.path.includes('/users/me'),
  )
  const heavyPayloads = apiRequests.filter((r) => r.size > 50_000)

  // Detecter les duplicats (meme path+method)
  const duplicates = new Map<string, number>()
  for (const r of apiRequests) {
    const key = `${r.method} ${r.path}`
    duplicates.set(key, (duplicates.get(key) ?? 0) + 1)
  }

  return {
    page: pageName,
    url: targetUrl,
    requests: apiRequests,
    totalRequests: requests.length,
    totalApiRequests: apiRequests.length,
    authRequests: authRequests.length,
    dataRequests: dataRequests.length,
    heavyPayloads,
    duplicates,
  }
}

function printAudit(audit: PageAudit) {
  console.log(`\n${'═'.repeat(70)}`)
  console.log(`  ${audit.page}`)
  console.log(`  ${audit.url}`)
  console.log(`${'═'.repeat(70)}`)
  console.log(
    `  API calls: ${audit.totalApiRequests} (auth: ${audit.authRequests}, data: ${audit.dataRequests})`,
  )

  if (audit.heavyPayloads.length > 0) {
    console.log(`  ⚠ HEAVY PAYLOADS (>50KB):`)
    for (const r of audit.heavyPayloads) {
      console.log(
        `    ${r.method} ${r.path} → ${r.status} (${(r.size / 1024).toFixed(1)}KB, ${r.duration}ms)`,
      )
    }
  }

  // Duplicats
  const dups = [...audit.duplicates.entries()].filter(([, count]) => count > 1)
  if (dups.length > 0) {
    console.log(`  ⚠ DUPLICATE CALLS:`)
    for (const [key, count] of dups) {
      console.log(`    ${key} × ${count}`)
    }
  }

  // Toutes les requetes
  console.log(`  ── Requests ──`)
  for (const r of audit.requests) {
    const sizeStr = r.size > 1024 ? `${(r.size / 1024).toFixed(1)}KB` : `${r.size}B`
    console.log(
      `  ${r.method.padEnd(6)} ${r.path.substring(0, 80).padEnd(80)} ${String(r.status).padEnd(4)} ${sizeStr.padStart(8)} ${String(r.duration).padStart(5)}ms`,
    )
  }
}

// ── Pages a auditer ────────────────────────────────────────────────────────────

const PAGES_TO_AUDIT = [
  { name: 'Dashboard', url: '/dashboard' },
  { name: 'Reservations (liste)', url: '/reservations' },
  { name: 'Devis (liste)', url: '/devis' },
  { name: 'Produits (catalogue)', url: '/catalogue' },
  { name: 'Factures', url: '/factures' },
  { name: 'Clients', url: '/clients' },
  { name: 'Stock', url: '/stock' },
  { name: 'Formules', url: '/catalogue/formules' },
  { name: 'Planning', url: '/planning' },
  { name: 'Relances', url: '/relances' },
]

// ── Test principal ─────────────────────────────────────────────────────────────

test.describe('Network Audit', () => {
  test.beforeEach(async ({ page }) => {
    await loginForAudit(page)
  })

  test('audit all key pages — capture API requests', async ({ page }) => {
    const audits: PageAudit[] = []
    const allRequests: CapturedRequest[] = []

    for (const target of PAGES_TO_AUDIT) {
      const audit = await capturePageRequests(page, target.url, target.name)
      audits.push(audit)
      allRequests.push(...audit.requests)
      printAudit(audit)
    }

    // ── Rapport de synthese ──────────────────────────────────────────────────

    console.log(`\n${'═'.repeat(70)}`)
    console.log('  SYNTHESE GLOBALE')
    console.log(`${'═'.repeat(70)}`)

    const totalApi = audits.reduce((s, a) => s + a.totalApiRequests, 0)
    const totalAuth = audits.reduce((s, a) => s + a.authRequests, 0)
    const totalData = audits.reduce((s, a) => s + a.dataRequests, 0)
    const totalHeavy = audits.reduce((s, a) => s + a.heavyPayloads.length, 0)

    console.log(`  Total API calls (${PAGES_TO_AUDIT.length} pages): ${totalApi}`)
    console.log(`  Auth overhead: ${totalAuth} (${((totalAuth / totalApi) * 100).toFixed(0)}%)`)
    console.log(`  Data calls: ${totalData}`)
    console.log(`  Heavy payloads (>50KB): ${totalHeavy}`)

    // Pages les plus couteuses
    const sorted = [...audits].sort((a, b) => b.totalApiRequests - a.totalApiRequests)
    console.log(`\n  Pages par nombre d'appels API:`)
    for (const a of sorted) {
      const bar = '█'.repeat(a.totalApiRequests)
      console.log(`    ${a.page.padEnd(25)} ${String(a.totalApiRequests).padStart(3)} ${bar}`)
    }

    // Endpoints uniques et frequence
    const endpointFreq = new Map<string, number>()
    for (const r of allRequests) {
      // Normaliser les IDs dans les paths
      const normalized = r.path.replace(/\/\d+/g, '/:id')
      const key = `${r.method} ${normalized}`
      endpointFreq.set(key, (endpointFreq.get(key) ?? 0) + 1)
    }
    const topEndpoints = [...endpointFreq.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)

    console.log(`\n  Top 20 endpoints (freq):`)
    for (const [ep, count] of topEndpoints) {
      console.log(`    ${String(count).padStart(3)}x  ${ep}`)
    }

    // Endpoints 404/500
    const errors = allRequests.filter((r) => r.status >= 400)
    if (errors.length > 0) {
      console.log(`\n  ⚠ ERREURS API (${errors.length}):`)
      for (const r of errors) {
        console.log(`    ${r.method} ${r.path} → ${r.status}`)
      }
    }

    // Le test ne doit pas echouer — c'est un audit informatif
    expect(true).toBe(true)
  })

  test('cross-navigation auth overhead — measure init calls', async ({ page }) => {
    const authCalls: { page: string; calls: string[] }[] = []

    const pages = ['/dashboard', '/reservations', '/devis', '/catalogue', '/factures']

    for (const targetUrl of pages) {
      const calls: string[] = []

      const handler = (response: Response) => {
        const url = response.url()
        if (
          url.includes('/auth/refresh') ||
          url.includes('/auth/me') ||
          url.includes('/users/me') ||
          url.includes('/auth/csrf')
        ) {
          calls.push(extractPath(url))
        }
      }
      page.on('response', handler)

      await page.goto(targetUrl, { waitUntil: 'domcontentloaded' })
      await page.waitForTimeout(2000)

      page.removeListener('response', handler)
      authCalls.push({ page: targetUrl, calls })
    }

    console.log(`\n${'═'.repeat(70)}`)
    console.log('  AUTH OVERHEAD — Cross-navigation')
    console.log(`${'═'.repeat(70)}`)

    for (const entry of authCalls) {
      console.log(`\n  ${entry.page}:`)
      if (entry.calls.length === 0) {
        console.log('    ✓ 0 auth calls (cache hit)')
      } else {
        for (const c of entry.calls) {
          console.log(`    → ${c}`)
        }
      }
    }

    const totalAuth = authCalls.reduce((s, e) => s + e.calls.length, 0)
    console.log(`\n  Total auth calls across ${pages.length} navigations: ${totalAuth}`)
    console.log(
      `  Expected with 5min cache: ≤4 (first page only)`,
    )

    // Apres la premiere page, les autres devraient avoir 0 auth calls (cache 5min)
    const afterFirst = authCalls.slice(1)
    const authAfterFirst = afterFirst.reduce((s, e) => s + e.calls.length, 0)
    console.log(`  Auth calls after first page: ${authAfterFirst} (should be 0)`)
  })
})
