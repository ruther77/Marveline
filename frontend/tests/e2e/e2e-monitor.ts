/**
 * E2E Monitor — Module de capture des 5 axes de monitoring
 *
 * Axes :
 *   1. Trace d'exécution  — horodatage de chaque action utilisateur
 *   2. Temps d'exécution  — latence réseau, temps de rendu pages
 *   3. Parasitage d'appels — appels API dupliqués, requêtes fantômes
 *   4. Cohérence backend/frontend — statuts HTTP, réponses inattendues
 *   5. Logs erreurs/activités — console errors, network failures, 4xx/5xx
 *
 * Sortie : fichiers .txt horodatés dans test-results/monitoring/
 */

import { type Page, type Response, type Request } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// ── Types ────────────────────────────────────────────────────────────────────

interface TraceEntry {
  timestamp: string
  elapsed_ms: number
  action: string
  detail: string
}

interface RequestEntry {
  timestamp: string
  method: string
  path: string
  status: number
  size_bytes: number
  duration_ms: number
  content_type: string
}

interface ErrorEntry {
  timestamp: string
  source: 'console' | 'network' | 'api_4xx' | 'api_5xx' | 'uncaught'
  message: string
  url?: string
  status?: number
}

interface DuplicateCall {
  key: string
  count: number
  total_duration_ms: number
}

interface CoherenceIssue {
  timestamp: string
  method: string
  path: string
  issue: string
  detail: string
}

interface PageTiming {
  page_name: string
  url: string
  navigation_ms: number
  first_api_response_ms: number
  all_api_settled_ms: number
  api_call_count: number
}

// ── Monitor Class ────────────────────────────────────────────────────────────

export class E2EMonitor {
  private sessionId: string
  private startTime: number
  private traces: TraceEntry[] = []
  private requests: RequestEntry[] = []
  private errors: ErrorEntry[] = []
  private coherenceIssues: CoherenceIssue[] = []
  private pageTimings: PageTiming[] = []
  private pendingRequests = new Map<string, number>()
  private outputDir: string

  constructor(sessionName: string) {
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    this.sessionId = `${ts}_${sessionName}`
    this.startTime = Date.now()
    this.outputDir = path.resolve(__dirname, '../../test-results/monitoring')
    fs.mkdirSync(this.outputDir, { recursive: true })
  }

  // ── Axe 1 : Trace d'exécution ───────────────────────────────────────────

  trace(action: string, detail = '') {
    this.traces.push({
      timestamp: new Date().toISOString(),
      elapsed_ms: Date.now() - this.startTime,
      action,
      detail,
    })
  }

  // ── Axe 2 + 3 + 4 + 5 : Attacher les listeners à une page ──────────────

  attach(page: Page) {
    // Request start → mémoriser le timestamp
    page.on('request', (req: Request) => {
      const url = req.url()
      if (!url.includes('/api/v1/')) return
      this.pendingRequests.set(url + req.method(), Date.now())
    })

    // Response → capturer timing, taille, statut
    page.on('response', async (res: Response) => {
      const url = res.url()
      if (!url.includes('/api/v1/')) return

      const method = res.request().method()
      const startTime = this.pendingRequests.get(url + method) ?? Date.now()
      const duration = Date.now() - startTime
      this.pendingRequests.delete(url + method)

      let size = 0
      let contentType = ''
      try {
        const body = await res.body()
        size = body.length
        contentType = res.headers()['content-type'] ?? ''
      } catch {
        // Body unavailable (redirect, etc.)
      }

      const reqPath = this.extractPath(url)
      const status = res.status()

      this.requests.push({
        timestamp: new Date().toISOString(),
        method,
        path: reqPath,
        status,
        size_bytes: size,
        duration_ms: duration,
        content_type: contentType,
      })

      // Axe 5 : Erreurs API
      if (status >= 400 && status < 500) {
        let detail = ''
        try {
          detail = (await res.body()).toString().slice(0, 500)
        } catch { /* ignore */ }
        this.errors.push({
          timestamp: new Date().toISOString(),
          source: 'api_4xx',
          message: `${method} ${reqPath} → ${status}`,
          url: reqPath,
          status,
        })
        // Axe 4 : Cohérence
        this.coherenceIssues.push({
          timestamp: new Date().toISOString(),
          method,
          path: reqPath,
          issue: 'CLIENT_ERROR',
          detail: `${status} — ${detail}`,
        })
      }
      if (status >= 500) {
        let detail = ''
        try {
          detail = (await res.body()).toString().slice(0, 500)
        } catch { /* ignore */ }
        this.errors.push({
          timestamp: new Date().toISOString(),
          source: 'api_5xx',
          message: `${method} ${reqPath} → ${status}`,
          url: reqPath,
          status,
        })
        this.coherenceIssues.push({
          timestamp: new Date().toISOString(),
          method,
          path: reqPath,
          issue: 'SERVER_ERROR',
          detail: `${status} — ${detail}`,
        })
      }

      // Axe 4 : Réponse vide inattendue
      if (status === 200 && size === 0 && method === 'GET') {
        this.coherenceIssues.push({
          timestamp: new Date().toISOString(),
          method,
          path: reqPath,
          issue: 'EMPTY_RESPONSE',
          detail: 'GET 200 avec body vide',
        })
      }
    })

    // Request failed → erreur réseau
    page.on('requestfailed', (req: Request) => {
      const url = req.url()
      if (!url.includes('/api/v1/')) return
      this.errors.push({
        timestamp: new Date().toISOString(),
        source: 'network',
        message: `${req.method()} ${this.extractPath(url)} — ${req.failure()?.errorText ?? 'unknown'}`,
        url: this.extractPath(url),
      })
    })

    // Console errors
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        this.errors.push({
          timestamp: new Date().toISOString(),
          source: 'console',
          message: msg.text().slice(0, 1000),
        })
      }
    })

    // Page errors (uncaught exceptions)
    page.on('pageerror', (err) => {
      this.errors.push({
        timestamp: new Date().toISOString(),
        source: 'uncaught',
        message: `${err.name}: ${err.message}`.slice(0, 1000),
      })
    })
  }

  // ── Axe 2 : Mesurer le timing d'une navigation ──────────────────────────

  async measureNavigation(page: Page, url: string, pageName: string, waitMs = 3000) {
    const navStart = Date.now()
    let firstApiMs = 0
    const apiCount = { value: 0 }

    const handler = (res: Response) => {
      if (res.url().includes('/api/v1/')) {
        apiCount.value++
        if (firstApiMs === 0) firstApiMs = Date.now() - navStart
      }
    }
    page.on('response', handler)

    await page.goto(url, { waitUntil: 'domcontentloaded' })
    const navigationMs = Date.now() - navStart

    await page.waitForTimeout(waitMs)
    const settledMs = Date.now() - navStart

    page.removeListener('response', handler)

    const timing: PageTiming = {
      page_name: pageName,
      url,
      navigation_ms: navigationMs,
      first_api_response_ms: firstApiMs,
      all_api_settled_ms: settledMs,
      api_call_count: apiCount.value,
    }
    this.pageTimings.push(timing)
    this.trace('NAVIGATE', `${pageName} (${url}) — DOM: ${navigationMs}ms, API settled: ${settledMs}ms, calls: ${apiCount.value}`)
    return timing
  }

  // ── Axe 3 : Analyser les doublons ───────────────────────────────────────

  private analyzeDuplicates(): DuplicateCall[] {
    const freq = new Map<string, { count: number; totalDuration: number }>()
    for (const r of this.requests) {
      const normalized = r.path.replace(/\/\d+/g, '/:id')
      const key = `${r.method} ${normalized}`
      const entry = freq.get(key) ?? { count: 0, totalDuration: 0 }
      entry.count++
      entry.totalDuration += r.duration_ms
      freq.set(key, entry)
    }
    return [...freq.entries()]
      .filter(([, v]) => v.count > 1)
      .map(([key, v]) => ({ key, count: v.count, total_duration_ms: v.totalDuration }))
      .sort((a, b) => b.count - a.count)
  }

  // ── Export .txt ─────────────────────────────────────────────────────────

  flush(): string {
    const duplicates = this.analyzeDuplicates()
    const elapsed = Date.now() - this.startTime
    const lines: string[] = []

    const hr = '═'.repeat(80)
    const sr = '─'.repeat(80)

    lines.push(hr)
    lines.push(`  E2E MONITORING REPORT — ${this.sessionId}`)
    lines.push(`  Generated: ${new Date().toISOString()}`)
    lines.push(`  Total duration: ${(elapsed / 1000).toFixed(1)}s`)
    lines.push(`  Total API calls: ${this.requests.length}`)
    lines.push(`  Total errors: ${this.errors.length}`)
    lines.push(`  Duplicate call patterns: ${duplicates.length}`)
    lines.push(`  Coherence issues: ${this.coherenceIssues.length}`)
    lines.push(hr)

    // ── AXE 1 : Trace d'exécution ──
    lines.push('')
    lines.push(`  AXE 1 — TRACE D'EXÉCUTION (${this.traces.length} actions)`)
    lines.push(sr)
    for (const t of this.traces) {
      const ts = t.timestamp.slice(11, 23)
      const ms = String(t.elapsed_ms).padStart(8)
      lines.push(`  ${ts}  +${ms}ms  ${t.action.padEnd(20)} ${t.detail}`)
    }

    // ── AXE 2 : Temps d'exécution ──
    lines.push('')
    lines.push(`  AXE 2 — TEMPS D'EXÉCUTION`)
    lines.push(sr)

    if (this.pageTimings.length > 0) {
      lines.push('  Page Timings:')
      lines.push(`  ${'Page'.padEnd(25)} ${'DOM(ms)'.padStart(8)} ${'1st API'.padStart(8)} ${'Settled'.padStart(8)} ${'Calls'.padStart(6)}`)
      for (const t of this.pageTimings) {
        lines.push(`  ${t.page_name.padEnd(25)} ${String(t.navigation_ms).padStart(8)} ${String(t.first_api_response_ms).padStart(8)} ${String(t.all_api_settled_ms).padStart(8)} ${String(t.api_call_count).padStart(6)}`)
      }
    }

    if (this.requests.length > 0) {
      const avgDuration = this.requests.reduce((s, r) => s + r.duration_ms, 0) / this.requests.length
      const maxDuration = Math.max(...this.requests.map((r) => r.duration_ms))
      const p95 = this.requests.map((r) => r.duration_ms).sort((a, b) => a - b)[Math.floor(this.requests.length * 0.95)] ?? 0
      lines.push('')
      lines.push(`  API Latency: avg=${avgDuration.toFixed(0)}ms  p95=${p95}ms  max=${maxDuration}ms`)
      lines.push('')
      lines.push('  All API Calls:')
      lines.push(`  ${'Method'.padEnd(7)} ${'Path'.padEnd(70)} ${'Status'.padEnd(6)} ${'Size'.padStart(10)} ${'Time'.padStart(8)}`)
      for (const r of this.requests) {
        const sizeStr = r.size_bytes > 1024 ? `${(r.size_bytes / 1024).toFixed(1)}KB` : `${r.size_bytes}B`
        lines.push(`  ${r.method.padEnd(7)} ${r.path.slice(0, 70).padEnd(70)} ${String(r.status).padEnd(6)} ${sizeStr.padStart(10)} ${(r.duration_ms + 'ms').padStart(8)}`)
      }
    }

    // ── AXE 3 : Parasitage d'appels ──
    lines.push('')
    lines.push(`  AXE 3 — PARASITAGE D'APPELS (${duplicates.length} patterns dupliqués)`)
    lines.push(sr)
    if (duplicates.length === 0) {
      lines.push('  Aucun appel dupliqué détecté.')
    } else {
      for (const d of duplicates) {
        const flag = d.count >= 5 ? 'CRITIQUE' : d.count >= 3 ? 'ATTENTION' : 'INFO'
        lines.push(`  [${flag}] ${d.key} × ${d.count} (total: ${d.total_duration_ms}ms)`)
      }
    }

    // ── AXE 4 : Cohérence backend/frontend ──
    lines.push('')
    lines.push(`  AXE 4 — COHÉRENCE BACKEND/FRONTEND (${this.coherenceIssues.length} issues)`)
    lines.push(sr)
    if (this.coherenceIssues.length === 0) {
      lines.push('  Aucune incohérence détectée.')
    } else {
      for (const c of this.coherenceIssues) {
        const ts = c.timestamp.slice(11, 23)
        lines.push(`  ${ts}  [${c.issue}] ${c.method} ${c.path}`)
        lines.push(`           ${c.detail.slice(0, 200)}`)
      }
    }

    // ── AXE 5 : Logs erreurs et activités ──
    lines.push('')
    lines.push(`  AXE 5 — LOGS ERREURS ET ACTIVITÉS (${this.errors.length} erreurs)`)
    lines.push(sr)
    if (this.errors.length === 0) {
      lines.push('  Aucune erreur détectée.')
    } else {
      const bySource = new Map<string, number>()
      for (const e of this.errors) {
        bySource.set(e.source, (bySource.get(e.source) ?? 0) + 1)
      }
      lines.push(`  Répartition: ${[...bySource.entries()].map(([k, v]) => `${k}=${v}`).join(', ')}`)
      lines.push('')
      for (const e of this.errors) {
        const ts = e.timestamp.slice(11, 23)
        lines.push(`  ${ts}  [${e.source.toUpperCase().padEnd(10)}] ${e.message.slice(0, 200)}`)
      }
    }

    // ── Résumé final ──
    lines.push('')
    lines.push(hr)
    lines.push('  RÉSUMÉ')
    lines.push(hr)
    const statusCounts = new Map<number, number>()
    for (const r of this.requests) {
      statusCounts.set(r.status, (statusCounts.get(r.status) ?? 0) + 1)
    }
    lines.push(`  Status codes: ${[...statusCounts.entries()].sort((a, b) => a[0] - b[0]).map(([k, v]) => `${k}×${v}`).join('  ')}`)
    lines.push(`  Erreurs totales: ${this.errors.length}`)
    lines.push(`  Appels dupliqués: ${duplicates.reduce((s, d) => s + d.count - 1, 0)} appels superflus`)
    lines.push(`  Cohérence issues: ${this.coherenceIssues.length}`)
    const verdict = this.errors.filter((e) => e.source === 'api_5xx' || e.source === 'uncaught').length === 0
      ? 'PASS' : 'FAIL'
    lines.push(`  Verdict: ${verdict}`)
    lines.push(hr)

    const content = lines.join('\n')
    const filePath = path.join(this.outputDir, `${this.sessionId}.txt`)
    fs.writeFileSync(filePath, content, 'utf-8')
    console.log(`\n[E2E Monitor] Report saved: ${filePath}`)
    return filePath
  }

  // ── Utilities ──────────────────────────────────────────────────────────

  private extractPath(url: string): string {
    try {
      const u = new URL(url)
      return u.pathname + u.search
    } catch {
      return url
    }
  }
}
