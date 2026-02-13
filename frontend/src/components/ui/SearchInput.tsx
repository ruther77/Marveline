import { useState, useCallback, forwardRef, InputHTMLAttributes } from 'react';
import { Search, X, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useDebounce } from '../../hooks/useDebounce';

export interface SearchInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'size'> {
  value: string;
  onChange: (value: string) => void;
  onSearch?: (value: string) => void;
  debounce?: number;
  loading?: boolean;
  showClear?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const sizes = {
  sm: 'px-3 py-1.5 text-sm pl-8',
  md: 'px-4 py-2.5 pl-10',
  lg: 'px-4 py-3 text-lg pl-12',
};

const iconSizes = {
  sm: 'w-3.5 h-3.5 left-2.5',
  md: 'w-4 h-4 left-3',
  lg: 'w-5 h-5 left-4',
};

export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(
  (
    {
      value,
      onChange,
      onSearch,
      debounce = 300,
      loading = false,
      showClear = true,
      size = 'md',
      placeholder = 'Rechercher...',
      className,
      ...props
    },
    ref
  ) => {
    const [localValue, setLocalValue] = useState(value);
    const debouncedValue = useDebounce(localValue, debounce);

    // Sync debounced value with external handler
    const handleChange = useCallback(
      (e: React.ChangeEvent<HTMLInputElement>) => {
        const newValue = e.target.value;
        setLocalValue(newValue);
        onChange(newValue);

        if (onSearch && debounce > 0) {
          // The debounced effect will handle this
        } else if (onSearch) {
          onSearch(newValue);
        }
      },
      [onChange, onSearch, debounce]
    );

    // Handle search on debounced value
    if (onSearch && debouncedValue !== value) {
      onSearch(debouncedValue);
    }

    const handleClear = () => {
      setLocalValue('');
      onChange('');
      if (onSearch) {
        onSearch('');
      }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        handleClear();
      }
    };

    return (
      <div className="relative">
        <div
          className={cn(
            'absolute inset-y-0 flex items-center pointer-events-none text-dark-400',
            iconSizes[size]
          )}
        >
          {loading ? (
            <Loader2 className="animate-spin" />
          ) : (
            <Search />
          )}
        </div>
        <input
          ref={ref}
          type="search"
          value={localValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className={cn(
            'w-full bg-dark-800 border border-dark-600 rounded-lg text-white placeholder-dark-400',
            'transition-colors duration-200',
            'focus:outline-none focus:ring-2 focus:ring-offset-0 focus:border-primary-500 focus:ring-primary-500/20',
            sizes[size],
            (showClear && localValue) && 'pr-10',
            className
          )}
          {...props}
        />
        {showClear && localValue && (
          <button
            onClick={handleClear}
            className={cn(
              'absolute inset-y-0 right-0 flex items-center px-3 text-dark-400 hover:text-white transition-colors'
            )}
            aria-label="Effacer la recherche"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    );
  }
);

SearchInput.displayName = 'SearchInput';

// Search with suggestions
export interface SearchSuggestion {
  id: string;
  label: string;
  description?: string;
  icon?: React.ReactNode;
}

export interface SearchWithSuggestionsProps extends Omit<SearchInputProps, 'onSearch' | 'onSelect'> {
  suggestions: SearchSuggestion[];
  onSelect: (suggestion: SearchSuggestion) => void;
  onSearch?: (value: string) => void;
  showSuggestions?: boolean;
  emptyMessage?: string;
}

export function SearchWithSuggestions({
  suggestions,
  onSelect,
  onSearch,
  showSuggestions = true,
  emptyMessage = 'Aucun résultat',
  value,
  ...props
}: SearchWithSuggestionsProps) {
  const [isOpen, setIsOpen] = useState(false);

  const handleSelect = (suggestion: SearchSuggestion) => {
    onSelect(suggestion);
    setIsOpen(false);
  };

  const shouldShowSuggestions = showSuggestions && isOpen && value.length > 0;

  return (
    <div className="relative">
      <SearchInput
        value={value}
        onSearch={onSearch}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setTimeout(() => setIsOpen(false), 200)}
        {...props}
      />
      {shouldShowSuggestions && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-dark-800 border border-dark-700 rounded-lg shadow-xl z-50 max-h-64 overflow-y-auto">
          {suggestions.length === 0 ? (
            <div className="px-4 py-3 text-sm text-dark-400">{emptyMessage}</div>
          ) : (
            suggestions.map((suggestion) => (
              <button
                key={suggestion.id}
                onClick={() => handleSelect(suggestion)}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-dark-700 transition-colors first:rounded-t-lg last:rounded-b-lg"
              >
                {suggestion.icon && (
                  <span className="text-dark-400 flex-shrink-0">
                    {suggestion.icon}
                  </span>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">{suggestion.label}</p>
                  {suggestion.description && (
                    <p className="text-xs text-dark-400 truncate">
                      {suggestion.description}
                    </p>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
