import { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { cn } from '../../lib/utils';

export interface SubNavItem {
  label: string;
  href: string;
  icon?: ReactNode;
  badge?: string | number;
}

export interface SubNavProps {
  items: SubNavItem[];
  className?: string;
}

export function SubNav({ items, className }: SubNavProps) {
  return (
    <nav className={cn('flex items-center gap-1 p-1 bg-dark-800 rounded-lg', className)}>
      {items.map((item) => (
        <NavLink
          key={item.href}
          to={item.href}
          end
          className={({ isActive }) =>
            cn(
              'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
              isActive
                ? 'bg-dark-700 text-white'
                : 'text-dark-400 hover:text-white hover:bg-dark-700/50'
            )
          }
        >
          {item.icon}
          <span>{item.label}</span>
          {item.badge !== undefined && (
            <span className="ml-1 px-1.5 py-0.5 text-xs bg-dark-600 rounded">
              {item.badge}
            </span>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

// Version avec tabs (non-routée)
export interface TabItem {
  id: string;
  label: string;
  icon?: ReactNode;
  badge?: string | number;
}

export interface TabNavProps {
  tabs: TabItem[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  className?: string;
}

export function TabNav({ tabs, activeTab, onTabChange, className }: TabNavProps) {
  return (
    <nav className={cn('flex items-center gap-1 p-1 bg-dark-800 rounded-lg', className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
            activeTab === tab.id
              ? 'bg-dark-700 text-white'
              : 'text-dark-400 hover:text-white hover:bg-dark-700/50'
          )}
        >
          {tab.icon}
          <span>{tab.label}</span>
          {tab.badge !== undefined && (
            <span className="ml-1 px-1.5 py-0.5 text-xs bg-dark-600 rounded">
              {tab.badge}
            </span>
          )}
        </button>
      ))}
    </nav>
  );
}
