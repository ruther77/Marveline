import type { AppError, ErrorCategory } from './types'

// --- Error context attached to every report ---

export interface ErrorContext {
  route?: string
  componentStack?: string
  userId?: number
  tenantId?: string
  action?: string
  extra?: Record<string, unknown>
}

// --- Reporter interface (pluggable: console, Sentry, backend, etc.) ---

export interface ErrorReporter {
  captureError(error: AppError, context?: ErrorContext): void
  captureMessage(message: string, level: 'warning' | 'info'): void
  setUser(user: { id: number; email: string; tenant_id?: number }): void
}

// --- Console reporter (development) ---

const CATEGORY_COLORS: Record<ErrorCategory, string> = {
  network: '#f59e0b',
  auth: '#ef4444',
  validation: '#f97316',
  not_found: '#6b7280',
  forbidden: '#ef4444',
  server: '#dc2626',
  chunk_load: '#8b5cf6',
  unknown: '#6b7280',
}

class ConsoleReporter implements ErrorReporter {
  private user: { id: number; email: string; tenant_id?: number } | null = null

  captureError(error: AppError, context?: ErrorContext): void {
    const color = CATEGORY_COLORS[error.category] || '#6b7280'

    console.groupCollapsed(
      `%c[${error.category.toUpperCase()}]%c ${error.message}`,
      `color: ${color}; font-weight: bold`,
      'color: inherit',
    )
    console.log('Error:', error)
    console.log('Category:', error.category)
    console.log('Status:', error.status ?? 'N/A')
    console.log('Retryable:', error.retryable)

    if (context) {
      console.log('Context:', context)
    }

    if (this.user) {
      console.log('User:', this.user)
    }

    if (error.original) {
      console.log('Original:', error.original)
    }

    console.groupEnd()
  }

  captureMessage(message: string, level: 'warning' | 'info'): void {
    if (level === 'warning') {
      console.warn(`[REPORT] ${message}`)
    } else {
      console.info(`[REPORT] ${message}`)
    }
  }

  setUser(user: { id: number; email: string; tenant_id?: number }): void {
    this.user = user
  }
}

// --- Singleton reporter instance ---

let _reporter: ErrorReporter = new ConsoleReporter()

export function getErrorReporter(): ErrorReporter {
  return _reporter
}

export function setErrorReporter(reporter: ErrorReporter): void {
  _reporter = reporter
}
