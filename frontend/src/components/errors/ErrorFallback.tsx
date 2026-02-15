import { AlertTriangle, RefreshCw, Home, WifiOff, ShieldAlert, ServerCrash } from 'lucide-react'
import type { ErrorCategory } from '@/errors'
import { ERROR_TITLES, ERROR_MESSAGES, ERROR_ACTIONS } from '@/errors'
import { cn } from '@/lib/utils'

// --- Variant determines visual density ---

export type ErrorFallbackVariant = 'page' | 'widget' | 'full'

interface ErrorFallbackProps {
  category?: ErrorCategory
  title?: string
  message?: string
  variant?: ErrorFallbackVariant
  onRetry?: () => void
  onNavigateHome?: () => void
  className?: string
}

const CATEGORY_ICONS: Record<ErrorCategory, React.ComponentType<{ className?: string }>> = {
  network: WifiOff,
  auth: ShieldAlert,
  validation: AlertTriangle,
  not_found: AlertTriangle,
  forbidden: ShieldAlert,
  server: ServerCrash,
  chunk_load: RefreshCw,
  unknown: AlertTriangle,
}

const CATEGORY_ICON_COLORS: Record<ErrorCategory, string> = {
  network: 'text-yellow-400',
  auth: 'text-red-400',
  validation: 'text-orange-400',
  not_found: 'text-dark-400',
  forbidden: 'text-red-400',
  server: 'text-red-500',
  chunk_load: 'text-purple-400',
  unknown: 'text-dark-400',
}

export default function ErrorFallback({
  category = 'unknown',
  title,
  message,
  variant = 'page',
  onRetry,
  onNavigateHome,
  className,
}: ErrorFallbackProps) {
  const Icon = CATEGORY_ICONS[category]
  const iconColor = CATEGORY_ICON_COLORS[category]
  const displayTitle = title || ERROR_TITLES[category]
  const displayMessage = message || ERROR_MESSAGES[category]
  const actionLabel = ERROR_ACTIONS[category]

  // --- Widget variant: compact inline ---
  if (variant === 'widget') {
    return (
      <div
        className={cn(
          'flex items-center gap-3 p-4 rounded-xl bg-dark-800/50 border border-dark-700/50',
          className,
        )}
      >
        <Icon className={cn('w-5 h-5 flex-shrink-0', iconColor)} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-dark-200">{displayTitle}</p>
          <p className="text-xs text-dark-500 mt-0.5 truncate">{displayMessage}</p>
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-primary-400 hover:text-primary-300 hover:bg-primary-500/10 rounded-lg transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            {actionLabel}
          </button>
        )}
      </div>
    )
  }

  // --- Full variant: centered fullscreen ---
  if (variant === 'full') {
    return (
      <div
        className={cn(
          'min-h-screen flex items-center justify-center bg-dark-900 p-6',
          className,
        )}
      >
        <div className="max-w-md w-full text-center">
          <div className="mb-6 flex justify-center">
            <div className="w-16 h-16 rounded-2xl bg-dark-800 border border-dark-700/50 flex items-center justify-center">
              <Icon className={cn('w-8 h-8', iconColor)} />
            </div>
          </div>
          <h1 className="text-xl font-bold text-white mb-2">{displayTitle}</h1>
          <p className="text-dark-400 mb-8">{displayMessage}</p>
          <div className="flex items-center justify-center gap-3">
            {onRetry && (
              <button
                onClick={onRetry}
                className="flex items-center gap-2 px-5 py-2.5 bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium rounded-xl transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                {actionLabel}
              </button>
            )}
            {onNavigateHome && (
              <button
                onClick={onNavigateHome}
                className="flex items-center gap-2 px-5 py-2.5 bg-dark-700 hover:bg-dark-600 text-dark-200 text-sm font-medium rounded-xl transition-colors"
              >
                <Home className="w-4 h-4" />
                Accueil
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  // --- Page variant (default): centered in content area ---
  return (
    <div
      className={cn(
        'flex items-center justify-center py-20 px-6',
        className,
      )}
    >
      <div className="max-w-md w-full text-center">
        <div className="mb-5 flex justify-center">
          <div className="w-14 h-14 rounded-2xl bg-dark-800 border border-dark-700/50 flex items-center justify-center">
            <Icon className={cn('w-7 h-7', iconColor)} />
          </div>
        </div>
        <h2 className="text-lg font-bold text-white mb-2">{displayTitle}</h2>
        <p className="text-sm text-dark-400 mb-6">{displayMessage}</p>
        <div className="flex items-center justify-center gap-3">
          {onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium rounded-xl transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              {actionLabel}
            </button>
          )}
          {onNavigateHome && (
            <button
              onClick={onNavigateHome}
              className="flex items-center gap-2 px-4 py-2 bg-dark-700 hover:bg-dark-600 text-dark-200 text-sm font-medium rounded-xl transition-colors"
            >
              <Home className="w-4 h-4" />
              Accueil
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
