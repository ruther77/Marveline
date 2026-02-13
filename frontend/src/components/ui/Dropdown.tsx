import { useState, useRef, useEffect, ReactNode } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { cn } from '../../lib/utils';

export type DropdownPosition = 'bottom-left' | 'bottom-right' | 'top-left' | 'top-right';

export interface DropdownProps {
  trigger: ReactNode;
  children: ReactNode;
  position?: DropdownPosition;
  className?: string;
  contentClassName?: string;
  closeOnSelect?: boolean;
}

const positions = {
  'bottom-left': 'top-full left-0 mt-1',
  'bottom-right': 'top-full right-0 mt-1',
  'top-left': 'bottom-full left-0 mb-1',
  'top-right': 'bottom-full right-0 mb-1',
};

export function Dropdown({
  trigger,
  children,
  position = 'bottom-left',
  className,
  contentClassName,
  closeOnSelect = true,
}: DropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = () => {
    if (closeOnSelect) {
      setIsOpen(false);
    }
  };

  return (
    <div ref={dropdownRef} className={cn('relative inline-block', className)}>
      <div onClick={() => setIsOpen(!isOpen)} className="cursor-pointer">
        {trigger}
      </div>
      {isOpen && (
        <div
          className={cn(
            'absolute z-50 min-w-[180px] bg-dark-800 rounded-lg shadow-xl border border-dark-700',
            'animate-in fade-in zoom-in-95 duration-150',
            positions[position],
            contentClassName
          )}
          onClick={handleSelect}
        >
          {children}
        </div>
      )}
    </div>
  );
}

// Dropdown Menu Items
export interface DropdownItemProps {
  children: ReactNode;
  onClick?: () => void;
  icon?: ReactNode;
  shortcut?: string;
  disabled?: boolean;
  danger?: boolean;
  selected?: boolean;
  className?: string;
}

export function DropdownItem({
  children,
  onClick,
  icon,
  shortcut,
  disabled = false,
  danger = false,
  selected = false,
  className,
}: DropdownItemProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors',
        'first:rounded-t-lg last:rounded-b-lg',
        disabled
          ? 'text-dark-500 cursor-not-allowed'
          : danger
          ? 'text-red-400 hover:bg-red-900/30 hover:text-red-300'
          : 'text-dark-200 hover:bg-dark-700 hover:text-white',
        selected && 'bg-primary-900/30 text-primary-300',
        className
      )}
    >
      {icon && <span className="w-4 h-4 flex-shrink-0">{icon}</span>}
      <span className="flex-1">{children}</span>
      {selected && <Check className="w-4 h-4 text-primary-500" />}
      {shortcut && (
        <span className="text-xs text-dark-500 ml-auto">{shortcut}</span>
      )}
    </button>
  );
}

export function DropdownSeparator() {
  return <div className="border-t border-dark-700 my-1" />;
}

export function DropdownLabel({ children }: { children: ReactNode }) {
  return (
    <div className="px-3 py-2 text-xs font-semibold text-dark-400 uppercase tracking-wider">
      {children}
    </div>
  );
}

// Select Dropdown (combo trigger + dropdown)
export interface SelectDropdownOption {
  value: string;
  label: string;
  icon?: ReactNode;
  disabled?: boolean;
}

export interface SelectDropdownProps {
  options: SelectDropdownOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  error?: string;
  disabled?: boolean;
  className?: string;
}

export function SelectDropdown({
  options,
  value,
  onChange,
  placeholder = 'Sélectionner...',
  label,
  error,
  disabled,
  className,
}: SelectDropdownProps) {
  const selectedOption = options.find((opt) => opt.value === value);

  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-dark-200 mb-1.5">
          {label}
        </label>
      )}
      <Dropdown
        position="bottom-left"
        contentClassName="w-full"
        trigger={
          <div
            className={cn(
              'flex items-center justify-between w-full px-4 py-2.5 bg-dark-800 border rounded-lg',
              'transition-colors cursor-pointer',
              disabled
                ? 'opacity-50 cursor-not-allowed'
                : 'hover:border-dark-500',
              error ? 'border-red-500' : 'border-dark-600'
            )}
          >
            <span className={selectedOption ? 'text-white' : 'text-dark-400'}>
              {selectedOption ? (
                <span className="flex items-center gap-2">
                  {selectedOption.icon}
                  {selectedOption.label}
                </span>
              ) : (
                placeholder
              )}
            </span>
            <ChevronDown className="w-4 h-4 text-dark-400" />
          </div>
        }
      >
        <div className="py-1 max-h-60 overflow-y-auto">
          {options.map((option) => (
            <DropdownItem
              key={option.value}
              icon={option.icon}
              selected={option.value === value}
              disabled={option.disabled}
              onClick={() => onChange(option.value)}
            >
              {option.label}
            </DropdownItem>
          ))}
        </div>
      </Dropdown>
      {error && <p className="mt-1.5 text-sm text-red-500">{error}</p>}
    </div>
  );
}
