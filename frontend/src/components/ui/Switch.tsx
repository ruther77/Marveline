import { InputHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../lib/utils';

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'size'> {
  label?: string;
  description?: string;
  error?: string;
  size?: 'sm' | 'md' | 'lg';
}

const sizes = {
  sm: {
    track: 'w-8 h-4',
    thumb: 'w-3 h-3',
    thumbChecked: 'translate-x-4',
    label: 'text-sm',
  },
  md: {
    track: 'w-10 h-5',
    thumb: 'w-4 h-4',
    thumbChecked: 'translate-x-5',
    label: 'text-sm',
  },
  lg: {
    track: 'w-12 h-6',
    thumb: 'w-5 h-5',
    thumbChecked: 'translate-x-6',
    label: 'text-base',
  },
};

export const Switch = forwardRef<HTMLInputElement, SwitchProps>(
  (
    {
      className,
      label,
      description,
      error,
      disabled,
      checked,
      size = 'md',
      id,
      ...props
    },
    ref
  ) => {
    const switchId = id || label?.toLowerCase().replace(/\s/g, '-');
    const sizeConfig = sizes[size];

    return (
      <div className={cn('flex items-start', className)}>
        <div className="relative flex items-center">
          <input
            ref={ref}
            type="checkbox"
            role="switch"
            id={switchId}
            disabled={disabled}
            checked={checked}
            className="peer sr-only"
            {...props}
          />
          <div
            className={cn(
              'rounded-full transition-colors duration-200 cursor-pointer',
              'peer-focus:ring-2 peer-focus:ring-offset-0 peer-focus:ring-primary-500/20 peer-focus:ring-offset-dark-900',
              sizeConfig.track,
              checked ? 'bg-primary-600' : 'bg-dark-600',
              disabled && 'opacity-50 cursor-not-allowed'
            )}
          >
            <div
              className={cn(
                'rounded-full bg-white shadow-sm transition-transform duration-200',
                sizeConfig.thumb,
                'absolute top-1/2 -translate-y-1/2 left-0.5',
                checked && sizeConfig.thumbChecked
              )}
            />
          </div>
        </div>
        {(label || description) && (
          <label
            htmlFor={switchId}
            className={cn(
              'ml-3 cursor-pointer',
              disabled && 'opacity-50 cursor-not-allowed'
            )}
          >
            {label && (
              <span className={cn('font-medium text-white block', sizeConfig.label)}>
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

Switch.displayName = 'Switch';

// Switch avec label de chaque côté
export interface LabeledSwitchProps extends Omit<SwitchProps, 'label'> {
  labelOff: string;
  labelOn: string;
}

export const LabeledSwitch = forwardRef<HTMLInputElement, LabeledSwitchProps>(
  ({ labelOff, labelOn, checked, className, ...props }, ref) => {
    return (
      <div className={cn('flex items-center gap-3', className)}>
        <span
          className={cn(
            'text-sm transition-colors',
            !checked ? 'text-white font-medium' : 'text-dark-400'
          )}
        >
          {labelOff}
        </span>
        <Switch ref={ref} checked={checked} {...props} />
        <span
          className={cn(
            'text-sm transition-colors',
            checked ? 'text-white font-medium' : 'text-dark-400'
          )}
        >
          {labelOn}
        </span>
      </div>
    );
  }
);

LabeledSwitch.displayName = 'LabeledSwitch';
