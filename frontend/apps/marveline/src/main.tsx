import React from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { QueryClientProvider, QueryClient } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { routeTree } from './routeTree.gen'
import { applyBrandCssVars, BRAND, refreshBrandFromApi } from './brand/select'
import '@shared/styles/index.css'

applyBrandCssVars()
document.title = BRAND.name
// Refresh async depuis backend (best-effort, ne bloque pas le rendering)
void refreshBrandFromApi()

// ── Sentry (error tracking + performance) ──────────────────────────────────
const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN
if (SENTRY_DSN) {
  import('@sentry/react').then((Sentry) => {
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: import.meta.env.MODE,
      integrations: [
        Sentry.browserTracingIntegration(),
        Sentry.replayIntegration({ maskAllText: false, blockAllMedia: false }),
      ],
      tracesSampleRate: import.meta.env.PROD ? 0.1 : 1.0,
      replaysSessionSampleRate: 0.05,
      replaysOnErrorSampleRate: 1.0,
      ignoreErrors: [
        'ResizeObserver loop limit exceeded',
        'ResizeObserver loop completed with undelivered notifications',
        'Loading chunk',
        'ChunkLoadError',
      ],
    })
  }).catch(() => {
    // Sentry SDK non installe — silencieux
  })
}

// ── Web Vitals (performance monitoring) ─────────────────────────────────────
if (import.meta.env.PROD) {
  import('web-vitals').then(({ onCLS, onFID, onLCP, onFCP, onTTFB }) => {
    const report = (metric: { name: string; value: number; id: string }) => {
      // Envoyer au backend via beacon (non-blocking)
      if (navigator.sendBeacon) {
        navigator.sendBeacon(
          '/api/v1/notifications/web-vitals',
          JSON.stringify({
            name: metric.name,
            value: metric.value,
            id: metric.id,
            url: window.location.pathname,
          }),
        )
      }
    }
    onCLS(report)
    onFID(report)
    onLCP(report)
    onFCP(report)
    onTTFB(report)
  }).catch(() => {
    // web-vitals non installe — silencieux
  })
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
})

// Theme initial (evite flash)
;(() => {
  try {
    const stored = localStorage.getItem('marveline-ui')
    const parsed = stored ? JSON.parse(stored) : null
    // Si version < 2 : on ignore le theme persiste (migration light-by-default)
    const validVersion = (parsed?.version ?? 0) >= 2
    const theme: string = validVersion ? (parsed?.state?.theme ?? 'light') : 'light'
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    document.documentElement.dataset.theme = theme === 'system' ? (systemDark ? 'dark' : 'light') : theme
  } catch {
    document.documentElement.dataset.theme = 'light'
  }
})()

// Basepath dérivé de Vite base (ex: '/marveline/' ou '/splendid/').
// Le router strip le trailing '/' pour les liens internes (`navigate({ to: '/dashboard' })`
// reste portable entre marveline et splendid).
const basepath = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
const router = createRouter({ routeTree, basepath: basepath || undefined })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

const app = (
  <QueryClientProvider client={queryClient}>
    <RouterProvider router={router} />
    {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
  </QueryClientProvider>
)

ReactDOM.createRoot(document.getElementById('root')!).render(
  import.meta.env.PROD ? <React.StrictMode>{app}</React.StrictMode> : app,
)
