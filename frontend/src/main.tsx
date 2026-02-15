import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query'
import App from './App'
import { ToastProvider } from './components/ui/Toast'
import { AppErrorBoundary } from './components/errors'
import { normalizeError, AuthError } from './errors'
import './index.css'

// --- Global toast ref (bridged outside React tree for QueryCache callbacks) ---

let toastError: ((title: string, message?: string) => void) | null = null

export function registerToastError(fn: (title: string, message?: string) => void) {
  toastError = fn
}

// --- React Query caches with global error handling ---

const queryCache = new QueryCache({
  onError: (error, query) => {
    // Skip if the query opts out via meta.silent
    if (query.meta?.silent) return

    const appError = normalizeError(error)

    // Auth errors: don't toast, the interceptor handles redirect
    if (appError instanceof AuthError) return

    if (toastError) {
      toastError(
        appError.category === 'network' ? 'Probleme de connexion' : 'Erreur de chargement',
        appError.message,
      )
    }
  },
})

const mutationCache = new MutationCache({
  onError: (error, _variables, _context, mutation) => {
    // Skip if the mutation opts out via meta.silent
    if (mutation.meta?.silent) return

    const appError = normalizeError(error)

    if (appError instanceof AuthError) return

    if (toastError) {
      toastError('Erreur', appError.message)
    }
  },
})

const queryClient = new QueryClient({
  queryCache,
  mutationCache,
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        const appError = normalizeError(error)
        // Don't retry auth/validation/not_found/forbidden errors
        if (!appError.retryable) return false
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ToastProvider>
            <App />
          </ToastProvider>
        </BrowserRouter>
      </QueryClientProvider>
    </AppErrorBoundary>
  </React.StrictMode>,
)
