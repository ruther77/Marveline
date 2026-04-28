import { ReactNode } from 'react';
import { cn } from '../../lib/utils';

export interface CardProps {
  children: ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hover?: boolean;
  onClick?: () => void;
}

const paddings = {
  none: '',
  sm: 'p-2',
  md: 'p-4',
  lg: 'p-6',
};

export function Card({
  children,
  className,
  padding = 'md',
  hover = false,
  onClick,
}: CardProps) {
  return (
    <div
      className={cn(
        'card',
        paddings[padding],
        hover && 'hover:border-dark-600 transition-colors cursor-pointer',
        onClick && 'cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
}

export interface CardHeaderProps {
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}

export function CardHeader({ children, className, action }: CardHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between mb-4', className)}>
      <div>{children}</div>
      {action && <div>{action}</div>}
    </div>
  );
}

export interface CardTitleProps {
  children: ReactNode;
  className?: string;
  subtitle?: string;
}

export function CardTitle({ children, className, subtitle }: CardTitleProps) {
  return (
    <div>
      <h3 className={cn('text-lg font-semibold', className)}>
        {children}
      </h3>
      {subtitle && (
        <p className="text-sm text-dark-400 mt-0.5">{subtitle}</p>
      )}
    </div>
  );
}

export interface CardContentProps {
  children: ReactNode;
  className?: string;
}

export function CardContent({ children, className }: CardContentProps) {
  return <div className={cn(className)}>{children}</div>;
}

export interface CardFooterProps {
  children: ReactNode;
  className?: string;
}

export function CardFooter({ children, className }: CardFooterProps) {
  return (
    <div className={cn('mt-4 pt-4 border-t border-dark-600', className)}>
      {children}
    </div>
  );
}

// Stat Card variant
export interface StatCardProps {
  title: string;
  value: string | number;
  change?: {
    value: number;
    label?: string;
  };
  icon?: ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  className?: string;
  onClick?: () => void;
}

export function StatCard({
  title,
  value,
  change,
  icon,
  trend,
  className,
  onClick,
}: StatCardProps) {
  const trendColors = {
    up: 'text-green-500',
    down: 'text-red-500',
    neutral: 'text-dark-400',
  };

  return (
    <Card className={className} hover={!!onClick} onClick={onClick}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-dark-400">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {change && (
            <p className={cn('text-sm mt-2', trendColors[trend || 'neutral'])}>
              {change.value > 0 ? '+' : ''}{change.value}%
              {change.label && (
                <span className="text-dark-400 ml-1">{change.label}</span>
              )}
            </p>
          )}
        </div>
        {icon && (
          <div className="p-2 bg-dark-900 rounded-lg text-primary-500">
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
}
