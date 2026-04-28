import { Component, type ErrorInfo, type ReactNode } from 'react'
import { normalizeError, getErrorReporter, type AppError } from '@shared/errors'
import ErrorFallback from './ErrorFallback'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: AppError | null
}

/**
 * Page-level error boundary wrapping the <Outlet /> in DashboardLayout.
 * When a page crashes, the sidebar/navigation remain functional.
 * The user can navigate to another page or retry.
 */
export default class PageErrorBoundary extends Component<Props, State> {
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
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  private handleNavigateHome = () => {
    this.setState({ hasError: false, error: null })
    window.location.href = '/dashboard'
  }

  render() {
    if (this.state.hasError && this.state.error) {
      return (
        <ErrorFallback
          category={this.state.error.category}
          variant="page"
          onRetry={this.handleRetry}
          onNavigateHome={this.handleNavigateHome}
        />
      )
    }

    return this.props.children
  }
}
