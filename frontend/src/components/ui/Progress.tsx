import { cn } from '../../lib/utils';

export type ProgressVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';
export type ProgressSize = 'xs' | 'sm' | 'md' | 'lg';

export interface ProgressProps {
  value: number;
  max?: number;
  variant?: ProgressVariant;
  size?: ProgressSize;
  showLabel?: boolean;
  label?: string;
  className?: string;
  animated?: boolean;
  striped?: boolean;
}

const variants = {
  default: 'bg-primary-600',
  success: 'bg-green-600',
  warning: 'bg-yellow-600',
  danger: 'bg-red-600',
  info: 'bg-blue-600',
};

const sizes = {
  xs: 'h-1',
  sm: 'h-2',
  md: 'h-3',
  lg: 'h-4',
};

export function Progress({
  value,
  max = 100,
  variant = 'default',
  size = 'md',
  showLabel = false,
  label,
  className,
  animated = false,
  striped = false,
}: ProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);

  return (
    <div className={className}>
      {(showLabel || label) && (
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-dark-300">{label}</span>
          {showLabel && (
            <span className="text-sm font-medium text-white">
              {Math.round(percentage)}%
            </span>
          )}
        </div>
      )}
      <div
        className={cn(
          'w-full bg-dark-700 rounded-full overflow-hidden',
          sizes[size]
        )}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500 ease-out',
            variants[variant],
            striped && 'bg-stripes',
            animated && striped && 'animate-stripes'
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// Circular Progress
export interface CircularProgressProps {
  value: number;
  max?: number;
  size?: number;
  strokeWidth?: number;
  variant?: ProgressVariant;
  showLabel?: boolean;
  label?: string;
  className?: string;
}

const circularVariants = {
  default: 'stroke-primary-600',
  success: 'stroke-green-600',
  warning: 'stroke-yellow-600',
  danger: 'stroke-red-600',
  info: 'stroke-blue-600',
};

export function CircularProgress({
  value,
  max = 100,
  size = 64,
  strokeWidth = 6,
  variant = 'default',
  showLabel = true,
  label,
  className,
}: CircularProgressProps) {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100);
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className={cn('relative inline-flex', className)}>
      <svg width={size} height={size} className="-rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          className="stroke-dark-700 fill-none"
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className={cn('fill-none transition-all duration-500 ease-out', circularVariants[variant])}
        />
      </svg>
      {showLabel && (
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold text-white">
            {Math.round(percentage)}%
          </span>
          {label && (
            <span className="text-xs text-dark-400">{label}</span>
          )}
        </div>
      )}
    </div>
  );
}

// Steps Progress
export interface Step {
  label: string;
  description?: string;
  status?: 'pending' | 'current' | 'completed' | 'error';
}

export interface StepsProgressProps {
  steps: Step[];
  currentStep?: number;
  className?: string;
  orientation?: 'horizontal' | 'vertical';
}

export function StepsProgress({
  steps,
  currentStep = 0,
  className,
  orientation = 'horizontal',
}: StepsProgressProps) {
  return (
    <div
      className={cn(
        'flex',
        orientation === 'horizontal' ? 'items-center' : 'flex-col',
        className
      )}
    >
      {steps.map((step, index) => {
        const status = step.status || (
          index < currentStep ? 'completed' :
          index === currentStep ? 'current' : 'pending'
        );

        return (
          <div
            key={index}
            className={cn(
              'flex',
              orientation === 'horizontal'
                ? 'items-center flex-1'
                : 'items-start'
            )}
          >
            <div
              className={cn(
                'flex items-center',
                orientation === 'vertical' && 'flex-col'
              )}
            >
              {/* Step indicator */}
              <div
                className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center font-medium text-sm border-2 transition-colors',
                  status === 'completed' && 'bg-primary-600 border-primary-600 text-white',
                  status === 'current' && 'border-primary-600 text-primary-500',
                  status === 'pending' && 'border-dark-600 text-dark-400',
                  status === 'error' && 'bg-red-600 border-red-600 text-white'
                )}
              >
                {status === 'completed' ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : status === 'error' ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  index + 1
                )}
              </div>

              {/* Labels */}
              <div
                className={cn(
                  orientation === 'horizontal' ? 'ml-3' : 'mt-2 text-center'
                )}
              >
                <p
                  className={cn(
                    'text-sm font-medium',
                    status === 'current' ? 'text-white' : 'text-dark-300'
                  )}
                >
                  {step.label}
                </p>
                {step.description && (
                  <p className="text-xs text-dark-500">{step.description}</p>
                )}
              </div>
            </div>

            {/* Connector line */}
            {index < steps.length - 1 && (
              <div
                className={cn(
                  orientation === 'horizontal'
                    ? 'flex-1 h-0.5 mx-4'
                    : 'w-0.5 h-8 ml-4 my-2',
                  index < currentStep ? 'bg-primary-600' : 'bg-dark-700'
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
