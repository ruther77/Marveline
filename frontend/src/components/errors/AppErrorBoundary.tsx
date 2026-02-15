import { Component, type ErrorInfo, type ReactNode } from 'react'
import { normalizeError, getErrorReporter, type AppError } from '@/errors'
import ErrorFallback from './ErrorFallback'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: AppError | null
}

/**
 * Top-level error boundary wrapping the entire application.
 * Catches fatal render errors and displays a full-screen fallback.
 * Placed in main.tsx around everything.
 */
export default class AppErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: unknown): State {
    return {
      hasError: true,
      error: normalizeError(error),
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const appError = normalizeError(error)
    const reporter = getErrorReporter()

    reporter.captureError(appError, {
      componentStack: errorInfo.componentStack || undefined,
      route: window.location.pathname,
    })

    // Auto-reload once for chunk load failures
    if (appError.category === 'chunk_load') {
      const reloaded = sessionStorage.getItem('chunk_reload')
      if (!reloaded) {
        sessionStorage.setItem('chunk_reload', '1')
        window.location.reload()
        return
      }
      sessionStorage.removeItem('chunk_reload')
    }
  }

  private handleRetry = () => {
    sessionStorage.removeItem('chunk_reload')
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  render() {
    if (this.state.hasError && this.state.error) {
      return (
        <ErrorFallback
          category={this.state.error.category}
          variant="full"
          onRetry={this.handleRetry}
        />
      )
    }

    return this.props.children
  }
}
