import { Component, type ErrorInfo, type ReactNode } from 'react'
import { normalizeError, getErrorReporter, type AppError } from '@/errors'
import ErrorFallback from './ErrorFallback'

interface Props {
  children: ReactNode
  className?: string
}

interface State {
  hasError: boolean
  error: AppError | null
}

/**
 * Widget-level error boundary for isolating individual cards/widgets.
 * One widget crashing won't take down the rest of the page.
 * Displays a compact inline error with retry.
 */
export default class WidgetErrorBoundary extends Component<Props, State> {
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

  render() {
    if (this.state.hasError && this.state.error) {
      return (
        <ErrorFallback
          category={this.state.error.category}
          variant="widget"
          onRetry={this.handleRetry}
          className={this.props.className}
        />
      )
    }

    return this.props.children
  }
}
