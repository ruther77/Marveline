import { createContext, useContext, useState, ReactNode } from 'react';
import { cn } from '../../lib/utils';

// Context
interface TabsContextValue {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

const TabsContext = createContext<TabsContextValue | undefined>(undefined);

function useTabsContext() {
  const context = useContext(TabsContext);
  if (!context) {
    throw new Error('Tabs components must be used within a Tabs provider');
  }
  return context;
}

// Main Tabs Container
export interface TabsProps {
  defaultValue?: string;
  value?: string;
  onChange?: (value: string) => void;
  children: ReactNode;
  className?: string;
}

export function Tabs({
  defaultValue = '',
  value,
  onChange,
  children,
  className,
}: TabsProps) {
  const [internalValue, setInternalValue] = useState(defaultValue);
  const activeTab = value ?? internalValue;

  const setActiveTab = (tab: string) => {
    if (onChange) {
      onChange(tab);
    } else {
      setInternalValue(tab);
    }
  };

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

// Tab List
export interface TabListProps {
  children: ReactNode;
  className?: string;
  variant?: 'default' | 'pills' | 'underline';
}

export function TabList({ children, className, variant = 'default' }: TabListProps) {
  const variantStyles = {
    default: 'bg-dark-800 p-1 rounded-lg',
    pills: 'gap-2',
    underline: 'border-b border-dark-700',
  };

  return (
    <div
      className={cn(
        'flex items-center',
        variantStyles[variant],
        className
      )}
      role="tablist"
    >
      {children}
    </div>
  );
}

// Individual Tab Trigger
export interface TabTriggerProps {
  value: string;
  children: ReactNode;
  disabled?: boolean;
  icon?: ReactNode;
  className?: string;
  variant?: 'default' | 'pills' | 'underline';
}

export function TabTrigger({
  value,
  children,
  disabled = false,
  icon,
  className,
  variant = 'default',
}: TabTriggerProps) {
  const { activeTab, setActiveTab } = useTabsContext();
  const isActive = activeTab === value;

  const baseStyles = 'flex items-center gap-2 font-medium transition-colors';

  const variantStyles = {
    default: cn(
      'px-4 py-2 text-sm rounded-md',
      isActive
        ? 'bg-dark-700 text-white'
        : 'text-dark-400 hover:text-white'
    ),
    pills: cn(
      'px-4 py-2 text-sm rounded-full',
      isActive
        ? 'bg-primary-600 text-white'
        : 'bg-dark-800 text-dark-400 hover:text-white hover:bg-dark-700'
    ),
    underline: cn(
      'px-4 py-3 text-sm border-b-2 -mb-px',
      isActive
        ? 'border-primary-500 text-white'
        : 'border-transparent text-dark-400 hover:text-white hover:border-dark-500'
    ),
  };

  return (
    <button
      role="tab"
      aria-selected={isActive}
      aria-controls={`tabpanel-${value}`}
      disabled={disabled}
      onClick={() => setActiveTab(value)}
      className={cn(
        baseStyles,
        variantStyles[variant],
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
    >
      {icon && <span className="flex-shrink-0">{icon}</span>}
      {children}
    </button>
  );
}

// Tab Content Panel
export interface TabContentProps {
  value: string;
  children: ReactNode;
  className?: string;
  forceMount?: boolean;
}

export function TabContent({
  value,
  children,
  className,
  forceMount = false,
}: TabContentProps) {
  const { activeTab } = useTabsContext();
  const isActive = activeTab === value;

  if (!isActive && !forceMount) {
    return null;
  }

  return (
    <div
      role="tabpanel"
      id={`tabpanel-${value}`}
      aria-labelledby={`tab-${value}`}
      hidden={!isActive}
      className={cn('mt-4', className)}
    >
      {children}
    </div>
  );
}
