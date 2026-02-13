import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export type BadgeVariant = 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info';
export type BadgeSize = 'sm' | 'md' | 'lg';

export interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
  removable?: boolean;
  onRemove?: () => void;
  className?: string;
}

const variants = {
  default: 'bg-dark-700 text-dark-200 border-dark-600',
  primary: 'bg-primary-900/50 text-primary-300 border-primary-700',
  success: 'bg-green-900/50 text-green-300 border-green-700',
  warning: 'bg-yellow-900/50 text-yellow-300 border-yellow-700',
  danger: 'bg-red-900/50 text-red-300 border-red-700',
  info: 'bg-blue-900/50 text-blue-300 border-blue-700',
};

const dotColors = {
  default: 'bg-dark-400',
  primary: 'bg-primary-500',
  success: 'bg-green-500',
  warning: 'bg-yellow-500',
  danger: 'bg-red-500',
  info: 'bg-blue-500',
};

const sizes = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-xs',
  lg: 'px-3 py-1.5 text-sm',
};

export function Badge({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
  removable = false,
  onRemove,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-medium rounded-full border',
        variants[variant],
        sizes[size],
        className
      )}
    >
      {dot && (
        <span className={cn('w-1.5 h-1.5 rounded-full', dotColors[variant])} />
      )}
      {children}
      {removable && (
        <button
          onClick={onRemove}
          className="ml-0.5 hover:text-white transition-colors"
          aria-label="Supprimer"
        >
          <svg
            className="w-3 h-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      )}
    </span>
  );
}

// Status Badge - pour les statuts courants
export type StatusType = 'active' | 'inactive' | 'pending' | 'completed' | 'cancelled' | 'error';

const statusConfig: Record<StatusType, { variant: BadgeVariant; label: string }> = {
  active: { variant: 'success', label: 'Actif' },
  inactive: { variant: 'default', label: 'Inactif' },
  pending: { variant: 'warning', label: 'En attente' },
  completed: { variant: 'success', label: 'Terminé' },
  cancelled: { variant: 'danger', label: 'Annulé' },
  error: { variant: 'danger', label: 'Erreur' },
};

export interface StatusBadgeProps {
  status: StatusType;
  customLabel?: string;
  size?: BadgeSize;
  dot?: boolean;
  className?: string;
}

export function StatusBadge({
  status,
  customLabel,
  size = 'md',
  dot = true,
  className,
}: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <Badge variant={config.variant} size={size} dot={dot} className={className}>
      {customLabel || config.label}
    </Badge>
  );
}
