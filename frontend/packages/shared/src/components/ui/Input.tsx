import { InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../lib/utils';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  rightElement?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      label,
      error,
      hint,
      leftIcon,
      rightIcon,
      rightElement,
      id,
      ...props
    },
    ref
  ) => {
    const inputId = id || label?.toLowerCase().replace(/\s/g, '-');

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-dark-200 mb-1.5"
          >
            {label}
          </label>
        )}
        <div className="relative min-h-[44px]">
          {leftIcon && (
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-dark-400">
              {leftIcon}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              'w-full px-4 py-2.5 bg-dark-900 border rounded-lg text-dark-50 placeholder-dark-400',
              'transition-colors duration-200',
              'focus:outline-none focus:ring-2 focus:ring-offset-0',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              error
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20'
                : 'border-dark-600 focus:border-primary-500 focus:ring-primary-500/20',
              leftIcon && 'pl-10',
              (rightIcon || rightElement) && 'pr-10',
              className
            )}
            {...props}
          />
          {(rightIcon || rightElement) && (
            <div className="absolute inset-y-0 right-0 pr-4 flex items-center">
              {rightElement || (
                <span className="text-dark-400">{rightIcon}</span>
              )}
            </div>
          )}
        </div>
        {error && (
          <p className="mt-1.5 text-sm text-red-500">{error}</p>
        )}
        {hint && !error && (
          <p className="mt-1.5 text-sm text-dark-400">{hint}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
