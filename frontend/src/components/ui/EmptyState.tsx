import { ReactNode } from 'react';
import { Inbox, Search, FileX, AlertCircle, Plus } from 'lucide-react';
import { cn } from '../../lib/utils';
import { Button } from './Button';

export type EmptyStateType = 'empty' | 'search' | 'error' | 'no-results' | 'custom';

export interface EmptyStateProps {
  type?: EmptyStateType;
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
    variant?: 'primary' | 'secondary';
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

const defaultIcons = {
  empty: Inbox,
  search: Search,
  error: AlertCircle,
  'no-results': FileX,
  custom: Inbox,
};

const sizes = {
  sm: {
    container: 'py-8',
    icon: 'w-10 h-10',
    title: 'text-base',
    description: 'text-sm',
  },
  md: {
    container: 'py-12',
    icon: 'w-12 h-12',
    title: 'text-lg',
    description: 'text-sm',
  },
  lg: {
    container: 'py-16',
    icon: 'w-16 h-16',
    title: 'text-xl',
    description: 'text-base',
  },
};

export function EmptyState({
  type = 'empty',
  icon,
  title,
  description,
  action,
  secondaryAction,
  className,
  size = 'md',
}: EmptyStateProps) {
  const IconComponent = defaultIcons[type];
  const sizeStyles = sizes[size];

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center px-4',
        sizeStyles.container,
        className
      )}
    >
      <div className="p-4 bg-dark-800 rounded-full mb-4">
        {icon || (
          <IconComponent className={cn('text-dark-400', sizeStyles.icon)} />
        )}
      </div>
      <h3 className={cn('font-semibold text-white mb-2', sizeStyles.title)}>
        {title}
      </h3>
      {description && (
        <p className={cn('text-dark-400 max-w-md mb-6', sizeStyles.description)}>
          {description}
        </p>
      )}
      {(action || secondaryAction) && (
        <div className="flex items-center gap-3">
          {action && (
            <Button
              variant={action.variant || 'primary'}
              onClick={action.onClick}
              leftIcon={<Plus className="w-4 h-4" />}
            >
              {action.label}
            </Button>
          )}
          {secondaryAction && (
            <Button variant="ghost" onClick={secondaryAction.onClick}>
              {secondaryAction.label}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

// Preset Empty States
export interface NoDataProps {
  onAction?: () => void;
  actionLabel?: string;
  className?: string;
}

export function NoData({ onAction, actionLabel = 'Ajouter', className }: NoDataProps) {
  return (
    <EmptyState
      type="empty"
      title="Aucune donnée"
      description="Commencez par ajouter votre premier élément"
      action={onAction ? { label: actionLabel, onClick: onAction } : undefined}
      className={className}
    />
  );
}

export function NoSearchResults({ searchTerm, onClear, className }: { searchTerm?: string; onClear?: () => void; className?: string }) {
  return (
    <EmptyState
      type="no-results"
      title="Aucun résultat"
      description={
        searchTerm
          ? `Aucun résultat pour "${searchTerm}". Essayez d'autres termes.`
          : "Aucun élément ne correspond à vos critères de recherche."
      }
      action={onClear ? { label: 'Effacer la recherche', onClick: onClear, variant: 'secondary' } : undefined}
      className={className}
    />
  );
}

export function ErrorState({ onRetry, className }: { onRetry?: () => void; className?: string }) {
  return (
    <EmptyState
      type="error"
      title="Une erreur est survenue"
      description="Impossible de charger les données. Veuillez réessayer."
      action={onRetry ? { label: 'Réessayer', onClick: onRetry, variant: 'secondary' } : undefined}
      className={className}
    />
  );
}
