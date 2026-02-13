import { InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../lib/utils';

export interface RadioProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  description?: string;
  error?: string;
}

export const Radio = forwardRef<HTMLInputElement, RadioProps>(
  (
    {
      className,
      label,
      description,
      error,
      disabled,
      checked,
      id,
      ...props
    },
    ref
  ) => {
    const radioId = id || `radio-${props.name}-${props.value}`;

    return (
      <div className={cn('flex items-start', className)}>
        <div className="relative flex items-center">
          <input
            ref={ref}
            type="radio"
            id={radioId}
            disabled={disabled}
            checked={checked}
            className="peer sr-only"
            {...props}
          />
          <div
            className={cn(
              'w-5 h-5 rounded-full border-2 transition-colors duration-200 flex items-center justify-center',
              'peer-focus:ring-2 peer-focus:ring-offset-0 peer-focus:ring-primary-500/20',
              checked
                ? 'border-primary-600'
                : 'bg-dark-800 border-dark-600 peer-hover:border-dark-500',
              disabled && 'opacity-50 cursor-not-allowed',
              error && 'border-red-500'
            )}
          >
            {checked && (
              <div className="w-2.5 h-2.5 rounded-full bg-primary-600" />
            )}
          </div>
        </div>
        {(label || description) && (
          <label
            htmlFor={radioId}
            className={cn(
              'ml-3 cursor-pointer',
              disabled && 'opacity-50 cursor-not-allowed'
            )}
          >
            {label && (
              <span className="text-sm font-medium text-white block">
                {label}
              </span>
            )}
            {description && (
              <span className="text-sm text-dark-400 block">{description}</span>
            )}
          </label>
        )}
      </div>
    );
  }
);

Radio.displayName = 'Radio';

// Radio Group
export interface RadioGroupProps {
  label?: string;
  options: Array<{
    value: string;
    label: string;
    description?: string;
    disabled?: boolean;
  }>;
  value: string;
  onChange: (value: string) => void;
  name: string;
  error?: string;
  className?: string;
  orientation?: 'vertical' | 'horizontal';
}

export function RadioGroup({
  label,
  options,
  value,
  onChange,
  name,
  error,
  className,
  orientation = 'vertical',
}: RadioGroupProps) {
  return (
    <div className={className} role="radiogroup" aria-label={label}>
      {label && (
        <span className="block text-sm font-medium text-dark-200 mb-3">
          {label}
        </span>
      )}
      <div
        className={cn(
          'flex gap-4',
          orientation === 'vertical' ? 'flex-col' : 'flex-row flex-wrap'
        )}
      >
        {options.map((option) => (
          <Radio
            key={option.value}
            name={name}
            value={option.value}
            label={option.label}
            description={option.description}
            disabled={option.disabled}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
        ))}
      </div>
      {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
    </div>
  );
}

// Radio Cards - Alternative visuelle
export interface RadioCardOption {
  value: string;
  label: string;
  description?: string;
  icon?: React.ReactNode;
  disabled?: boolean;
}

export interface RadioCardsProps {
  options: RadioCardOption[];
  value: string;
  onChange: (value: string) => void;
  name: string;
  className?: string;
  columns?: 1 | 2 | 3 | 4;
}

export function RadioCards({
  options,
  value,
  onChange,
  name,
  className,
  columns = 2,
}: RadioCardsProps) {
  const gridCols = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
  };

  return (
    <div className={cn('grid gap-3', gridCols[columns], className)}>
      {options.map((option) => {
        const isSelected = value === option.value;

        return (
          <label
            key={option.value}
            className={cn(
              'relative flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all',
              isSelected
                ? 'border-primary-500 bg-primary-900/20'
                : 'border-dark-700 bg-dark-800 hover:border-dark-600',
              option.disabled && 'opacity-50 cursor-not-allowed'
            )}
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={isSelected}
              onChange={() => onChange(option.value)}
              disabled={option.disabled}
              className="sr-only"
            />
            {option.icon && (
              <div
                className={cn(
                  'p-2 rounded-lg',
                  isSelected ? 'bg-primary-600 text-white' : 'bg-dark-700 text-dark-400'
                )}
              >
                {option.icon}
              </div>
            )}
            <div className="flex-1">
              <span
                className={cn(
                  'font-medium block',
                  isSelected ? 'text-white' : 'text-dark-200'
                )}
              >
                {option.label}
              </span>
              {option.description && (
                <span className="text-sm text-dark-400 block mt-0.5">
                  {option.description}
                </span>
              )}
            </div>
            <div
              className={cn(
                'w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0',
                isSelected ? 'border-primary-500' : 'border-dark-600'
              )}
            >
              {isSelected && (
                <div className="w-2.5 h-2.5 rounded-full bg-primary-500" />
              )}
            </div>
          </label>
        );
      })}
    </div>
  );
}
