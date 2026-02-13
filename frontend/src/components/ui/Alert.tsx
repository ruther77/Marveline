import { ReactNode } from 'react';
import { AlertCircle, CheckCircle, Info, AlertTriangle, X } from 'lucide-react';
import { cn } from '../../lib/utils';

export type AlertVariant = 'info' | 'success' | 'warning' | 'error';

export interface AlertProps {
  variant?: AlertVariant;
  title?: string;
  children: ReactNode;
  icon?: ReactNode;
  dismissible?: boolean;
  onDismiss?: () => void;
  className?: string;
  actions?: ReactNode;
}

const variants = {
  info: {
    container: 'bg-blue-900/20 border-blue-700 text-blue-200',
    icon: 'text-blue-400',
    title: 'text-blue-100',
  },
  success: {
    container: 'bg-green-900/20 border-green-700 text-green-200',
    icon: 'text-green-400',
    title: 'text-green-100',
  },
  warning: {
    container: 'bg-yellow-900/20 border-yellow-700 text-yellow-200',
    icon: 'text-yellow-400',
    title: 'text-yellow-100',
  },
  error: {
    container: 'bg-red-900/20 border-red-700 text-red-200',
    icon: 'text-red-400',
    title: 'text-red-100',
  },
};

const icons = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: AlertCircle,
};

export function Alert({
  variant = 'info',
  title,
  children,
  icon,
  dismissible = false,
  onDismiss,
  className,
  actions,
}: AlertProps) {
  const styles = variants[variant];
  const IconComponent = icons[variant];

  return (
    <div
      className={cn(
        'relative flex gap-3 p-4 rounded-lg border',
        styles.container,
        className
      )}
      role="alert"
    >
      <div className={cn('flex-shrink-0 mt-0.5', styles.icon)}>
        {icon || <IconComponent className="w-5 h-5" />}
      </div>
      <div className="flex-1 min-w-0">
        {title && (
          <h4 className={cn('font-semibold mb-1', styles.title)}>{title}</h4>
        )}
        <div className="text-sm">{children}</div>
        {actions && <div className="mt-3 flex items-center gap-2">{actions}</div>}
      </div>
      {dismissible && (
        <button
          onClick={onDismiss}
          className={cn(
            'flex-shrink-0 p-1 hover:bg-white/10 rounded transition-colors',
            styles.icon
          )}
          aria-label="Fermer"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

// Inline Alert - plus compact, pour les formulaires
export interface InlineAlertProps {
  variant?: AlertVariant;
  children: ReactNode;
  className?: string;
}

export function InlineAlert({
  variant = 'error',
  children,
  className,
}: InlineAlertProps) {
  const styles = variants[variant];
  const IconComponent = icons[variant];

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded text-sm',
        styles.container,
        className
      )}
      role="alert"
    >
      <IconComponent className={cn('w-4 h-4 flex-shrink-0', styles.icon)} />
      {children}
    </div>
  );
}

// Banner Alert - pour les notifications globales
export interface BannerAlertProps {
  variant?: AlertVariant;
  children: ReactNode;
  dismissible?: boolean;
  onDismiss?: () => void;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function BannerAlert({
  variant = 'info',
  children,
  dismissible = false,
  onDismiss,
  action,
  className,
}: BannerAlertProps) {
  const styles = variants[variant];
  const IconComponent = icons[variant];

  return (
    <div
      className={cn(
        'flex items-center justify-center gap-3 px-4 py-3 text-sm',
        styles.container,
        'border-x-0 border-t-0 rounded-none',
        className
      )}
      role="alert"
    >
      <IconComponent className={cn('w-4 h-4 flex-shrink-0', styles.icon)} />
      <span>{children}</span>
      {action && (
        <button
          onClick={action.onClick}
          className="font-medium underline hover:no-underline"
        >
          {action.label}
        </button>
      )}
      {dismissible && (
        <button
          onClick={onDismiss}
          className="ml-auto p-1 hover:bg-white/10 rounded transition-colors"
          aria-label="Fermer"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
