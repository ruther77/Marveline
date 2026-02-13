import { InputHTMLAttributes, forwardRef } from 'react';
import { Check, Minus } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  description?: string;
  error?: string;
  indeterminate?: boolean;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  (
    {
      className,
      label,
      description,
      error,
      disabled,
      checked,
      indeterminate,
      id,
      ...props
    },
    ref
  ) => {
    const checkboxId = id || label?.toLowerCase().replace(/\s/g, '-');

    return (
      <div className={cn('flex items-start', className)}>
        <div className="relative flex items-center">
          <input
            ref={ref}
            type="checkbox"
            id={checkboxId}
            disabled={disabled}
            checked={checked}
            className="peer sr-only"
            {...props}
          />
          <div
            className={cn(
              'w-5 h-5 rounded border-2 transition-colors duration-200 flex items-center justify-center',
              'peer-focus:ring-2 peer-focus:ring-offset-0 peer-focus:ring-primary-500/20',
              checked || indeterminate
                ? 'bg-primary-600 border-primary-600'
                : 'bg-dark-800 border-dark-600 peer-hover:border-dark-500',
              disabled && 'opacity-50 cursor-not-allowed',
              error && 'border-red-500'
            )}
          >
            {checked && <Check className="w-3.5 h-3.5 text-white" strokeWidth={3} />}
            {indeterminate && !checked && (
              <Minus className="w-3.5 h-3.5 text-white" strokeWidth={3} />
            )}
          </div>
        </div>
        {(label || description) && (
          <label
            htmlFor={checkboxId}
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
            {error && (
              <span className="text-sm text-red-500 block mt-1">{error}</span>
            )}
          </label>
        )}
      </div>
    );
  }
);

Checkbox.displayName = 'Checkbox';

// Checkbox Group
export interface CheckboxGroupProps {
  label?: string;
  options: Array<{
    value: string;
    label: string;
    description?: string;
    disabled?: boolean;
  }>;
  value: string[];
  onChange: (value: string[]) => void;
  error?: string;
  className?: string;
  orientation?: 'vertical' | 'horizontal';
}

export function CheckboxGroup({
  label,
  options,
  value,
  onChange,
  error,
  className,
  orientation = 'vertical',
}: CheckboxGroupProps) {
  const handleChange = (optionValue: string, checked: boolean) => {
    if (checked) {
      onChange([...value, optionValue]);
    } else {
      onChange(value.filter((v) => v !== optionValue));
    }
  };

  return (
    <div className={className}>
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
          <Checkbox
            key={option.value}
            label={option.label}
            description={option.description}
            disabled={option.disabled}
            checked={value.includes(option.value)}
            onChange={(e) => handleChange(option.value, e.target.checked)}
          />
        ))}
      </div>
      {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
    </div>
  );
}
