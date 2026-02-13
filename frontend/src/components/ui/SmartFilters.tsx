import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { cn } from '@/lib/utils'
import {
  Search,
  Filter,
  X,
  ChevronDown,
  Check,
  Clock,
  Sparkles,
  RotateCcw,
  LucideIcon,
} from 'lucide-react'

// ============================================================================
// TYPES
// ============================================================================

export interface FilterOption {
  value: string
  label: string
  icon?: LucideIcon
  count?: number
}

export interface FilterConfig {
  key: string
  label: string
  type: 'select' | 'date' | 'range' | 'text'
  icon?: LucideIcon
  options?: FilterOption[]
  multiple?: boolean
  placeholder?: string
  min?: number
  max?: number
  step?: number
  unit?: string
  presets?: { label: string; value: string }[]
}

export interface FilterSuggestion {
  label: string
  filters: Record<string, unknown>
}

export interface FilterPreset {
  label: string
  description?: string
  icon?: LucideIcon
  filters: Record<string, unknown>
}

export interface SmartFiltersProps {
  filters?: FilterConfig[]
  values?: Record<string, unknown>
  onChange?: (key: string, value: unknown) => void
  onReset?: () => void
  suggestions?: FilterSuggestion[]
  presets?: FilterPreset[]
  searchable?: boolean
  searchValue?: string
  onSearchChange?: (value: string) => void
  searchPlaceholder?: string
  className?: string
}

// ============================================================================
// SMART FILTERS - Filtres intelligents avec suggestions et presets
// ============================================================================

export default function SmartFilters({
  filters = [],
  values = {},
  onChange,
  onReset,
  suggestions = [],
  presets = [],
  searchable = true,
  searchValue = '',
  onSearchChange,
  searchPlaceholder = 'Rechercher...',
  className,
}: SmartFiltersProps) {
  const [expandedFilter, setExpandedFilter] = useState<string | null>(null)
  const [showPresets, setShowPresets] = useState(false)

  // Compter les filtres actifs
  const activeCount = useMemo(() => {
    return Object.entries(values).filter(([, value]) => {
      if (value === null || value === undefined || value === '') return false
      if (Array.isArray(value) && value.length === 0) return false
      return true
    }).length
  }, [values])

  // Appliquer une suggestion
  const applySuggestion = useCallback((suggestion: FilterSuggestion) => {
    Object.entries(suggestion.filters).forEach(([key, value]) => {
      onChange?.(key, value)
    })
  }, [onChange])

  // Appliquer un preset
  const applyPreset = useCallback((preset: FilterPreset) => {
    filters.forEach((f) => onChange?.(f.key, null))
    Object.entries(preset.filters).forEach(([key, value]) => {
      onChange?.(key, value)
    })
    setShowPresets(false)
  }, [filters, onChange])

  return (
    <div className={cn('space-y-3', className)}>
      {/* Barre principale */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Recherche */}
        {searchable && (
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-400" />
            <input
              type="text"
              value={searchValue}
              onChange={(e) => onSearchChange?.(e.target.value)}
              placeholder={searchPlaceholder}
              className={cn(
                'w-full pl-10 pr-10 py-2.5 text-sm rounded-xl',
                'bg-dark-800 border border-dark-700 text-white placeholder-dark-400',
                'focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50',
                'transition-all'
              )}
            />
            {searchValue && (
              <button
                type="button"
                onClick={() => onSearchChange?.('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-dark-400 hover:text-white transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        )}

        {/* Filtres rapides */}
        <div className="flex items-center gap-2">
          {filters.slice(0, 3).map((filter) => (
            <FilterDropdown
              key={filter.key}
              filter={filter}
              value={values[filter.key]}
              onChange={(value) => onChange?.(filter.key, value)}
              expanded={expandedFilter === filter.key}
              onToggle={() => setExpandedFilter(
                expandedFilter === filter.key ? null : filter.key
              )}
            />
          ))}

          {/* Plus de filtres */}
          {filters.length > 3 && (
            <MoreFiltersDropdown
              filters={filters.slice(3)}
              values={values}
              onChange={onChange}
            />
          )}
        </div>

        <div className="flex-1" />

        {/* Presets */}
        {presets.length > 0 && (
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowPresets(!showPresets)}
              className={cn(
                'flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors',
                'border border-dark-700 hover:bg-dark-800 text-dark-300'
              )}
            >
              <Sparkles className="h-4 w-4" />
              <span className="hidden sm:inline">Filtres rapides</span>
              <ChevronDown className={cn('h-4 w-4 transition-transform', showPresets && 'rotate-180')} />
            </button>

            {showPresets && (
              <PresetsDropdown
                presets={presets}
                onSelect={applyPreset}
                onClose={() => setShowPresets(false)}
              />
            )}
          </div>
        )}

        {/* Reset */}
        {activeCount > 0 && (
          <button
            type="button"
            onClick={onReset}
            className="flex items-center gap-2 px-3 py-2 text-sm text-dark-400 hover:text-white transition-colors"
          >
            <RotateCcw className="h-4 w-4" />
            <span className="hidden sm:inline">Réinitialiser</span>
            <span className="w-5 h-5 flex items-center justify-center text-xs bg-primary-500 text-white rounded-full">
              {activeCount}
            </span>
          </button>
        )}
      </div>

      {/* Suggestions IA */}
      {suggestions.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-dark-500 flex items-center gap-1">
            <Sparkles className="h-3 w-3" />
            Suggestions:
          </span>
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              type="button"
              onClick={() => applySuggestion(suggestion)}
              className={cn(
                'px-2.5 py-1 text-xs rounded-full transition-colors',
                'bg-primary-500/10 text-primary-400 hover:bg-primary-500/20 border border-primary-500/20'
              )}
            >
              {suggestion.label}
            </button>
          ))}
        </div>
      )}

      {/* Tags des filtres actifs */}
      {activeCount > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          {Object.entries(values).map(([key, value]) => {
            if (value === null || value === undefined || value === '') return null
            if (Array.isArray(value) && value.length === 0) return null

            const filter = filters.find((f) => f.key === key)
            if (!filter) return null

            const displayValue = Array.isArray(value)
              ? value.length > 1 ? `${value.length} sélectionnés` : String(value[0])
              : filter.options?.find((o) => o.value === value)?.label || String(value)

            return (
              <span
                key={key}
                className={cn(
                  'inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full',
                  'bg-dark-700 text-dark-200 animate-in fade-in zoom-in-95 duration-200'
                )}
              >
                <span className="text-dark-400">{filter.label}:</span>
                <span className="font-medium">{displayValue}</span>
                <button
                  type="button"
                  onClick={() => onChange?.(key, null)}
                  className="p-0.5 hover:bg-dark-600 rounded-full transition-colors"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// FILTER DROPDOWN
// ============================================================================

interface FilterDropdownProps {
  filter: FilterConfig
  value: unknown
  onChange: (value: unknown) => void
  expanded: boolean
  onToggle: () => void
}

function FilterDropdown({ filter, value, onChange, expanded, onToggle }: FilterDropdownProps) {
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        onToggle()
      }
    }
    if (expanded) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [expanded, onToggle])

  const hasValue = value !== null && value !== undefined && value !== '' &&
    !(Array.isArray(value) && value.length === 0)

  const Icon = filter.icon

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          'flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-all',
          'border',
          hasValue
            ? 'border-primary-500/50 bg-primary-500/10 text-primary-300'
            : 'border-dark-700 hover:bg-dark-800 text-dark-300'
        )}
      >
        {Icon && <Icon className="h-4 w-4" />}
        {filter.label}
        <ChevronDown className={cn('h-4 w-4 transition-transform', expanded && 'rotate-180')} />
      </button>

      {expanded && (
        <div
          className={cn(
            'absolute top-full left-0 mt-2 min-w-[200px] bg-dark-800 rounded-xl shadow-xl border border-dark-700 py-2 z-30',
            'animate-in fade-in slide-in-from-top-2 duration-200'
          )}
        >
          {filter.type === 'select' && (
            <SelectFilterContent
              options={filter.options || []}
              value={value}
              onChange={onChange}
              multiple={filter.multiple}
            />
          )}

          {filter.type === 'date' && (
            <DateFilterContent
              value={value as string}
              onChange={onChange}
              presets={filter.presets}
            />
          )}

          {filter.type === 'range' && (
            <RangeFilterContent
              value={value as { min: number; max: number }}
              onChange={onChange}
              min={filter.min}
              max={filter.max}
              step={filter.step}
              unit={filter.unit}
            />
          )}

          {filter.type === 'text' && (
            <TextFilterContent
              value={value as string}
              onChange={onChange}
              placeholder={filter.placeholder}
            />
          )}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// FILTER CONTENTS
// ============================================================================

interface SelectFilterContentProps {
  options: FilterOption[]
  value: unknown
  onChange: (value: unknown) => void
  multiple?: boolean
}

function SelectFilterContent({ options, value, onChange, multiple = false }: SelectFilterContentProps) {
  const selectedValues = multiple ? (Array.isArray(value) ? value : []) : [value]

  const toggleValue = (optValue: string) => {
    if (multiple) {
      const newValues = selectedValues.includes(optValue)
        ? selectedValues.filter((v) => v !== optValue)
        : [...selectedValues, optValue]
      onChange(newValues.length > 0 ? newValues : null)
    } else {
      onChange(value === optValue ? null : optValue)
    }
  }

  return (
    <div className="max-h-64 overflow-y-auto">
      {options.map((option) => {
        const isSelected = selectedValues.includes(option.value)
        const Icon = option.icon
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => toggleValue(option.value)}
            className={cn(
              'w-full flex items-center gap-3 px-4 py-2 text-sm text-left transition-colors',
              isSelected ? 'bg-primary-500/20 text-primary-300' : 'text-dark-300 hover:bg-dark-700'
            )}
          >
            <div className={cn(
              'w-4 h-4 rounded flex items-center justify-center border transition-colors',
              isSelected ? 'bg-primary-500 border-primary-500' : 'border-dark-500'
            )}>
              {isSelected && <Check className="h-3 w-3 text-white" />}
            </div>
            {Icon && <Icon className="h-4 w-4 text-dark-400" />}
            <span className="flex-1">{option.label}</span>
            {option.count !== undefined && (
              <span className="text-xs text-dark-500">{option.count}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}

interface DateFilterContentProps {
  value: string | null | undefined
  onChange: (value: unknown) => void
  presets?: { label: string; value: string }[]
}

function DateFilterContent({ value, onChange, presets = [] }: DateFilterContentProps) {
  const defaultPresets = [
    { label: "Aujourd'hui", value: 'today' },
    { label: 'Hier', value: 'yesterday' },
    { label: '7 derniers jours', value: 'last7days' },
    { label: '30 derniers jours', value: 'last30days' },
    { label: 'Ce mois', value: 'thisMonth' },
    { label: 'Mois dernier', value: 'lastMonth' },
  ]

  const allPresets = presets.length > 0 ? presets : defaultPresets

  return (
    <div className="p-2">
      <div className="space-y-1">
        {allPresets.map((preset) => (
          <button
            key={preset.value}
            type="button"
            onClick={() => onChange(preset.value)}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors text-left',
              value === preset.value
                ? 'bg-primary-500/20 text-primary-300'
                : 'text-dark-300 hover:bg-dark-700'
            )}
          >
            <Clock className="h-4 w-4 text-dark-400" />
            {preset.label}
          </button>
        ))}
      </div>
      <div className="mt-3 pt-3 border-t border-dark-700">
        <label className="block text-xs text-dark-400 mb-2">Date personnalisée</label>
        <input
          type="date"
          value={typeof value === 'string' && !['today', 'yesterday', 'last7days', 'last30days', 'thisMonth', 'lastMonth'].includes(value) ? value : ''}
          onChange={(e) => onChange(e.target.value || null)}
          className="w-full px-3 py-2 text-sm bg-dark-700 border border-dark-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50"
        />
      </div>
    </div>
  )
}

interface RangeFilterContentProps {
  value: { min: number; max: number } | null | undefined
  onChange: (value: unknown) => void
  min?: number
  max?: number
  step?: number
  unit?: string
}

function RangeFilterContent({ value, onChange, min = 0, max = 100, step = 1, unit = '' }: RangeFilterContentProps) {
  const [localValue, setLocalValue] = useState(value || { min, max })

  useEffect(() => {
    if (value) setLocalValue(value)
  }, [value])

  const handleApply = () => {
    onChange(localValue)
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <label className="block text-xs text-dark-400 mb-1">Min</label>
          <input
            type="number"
            value={localValue.min}
            onChange={(e) => setLocalValue({ ...localValue, min: Number(e.target.value) })}
            min={min}
            max={max}
            step={step}
            className="w-full px-3 py-2 text-sm bg-dark-700 border border-dark-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50"
          />
        </div>
        <span className="text-dark-500 mt-5">—</span>
        <div className="flex-1">
          <label className="block text-xs text-dark-400 mb-1">Max</label>
          <input
            type="number"
            value={localValue.max}
            onChange={(e) => setLocalValue({ ...localValue, max: Number(e.target.value) })}
            min={min}
            max={max}
            step={step}
            className="w-full px-3 py-2 text-sm bg-dark-700 border border-dark-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50"
          />
        </div>
      </div>
      {unit && (
        <p className="text-xs text-dark-500 text-center">{unit}</p>
      )}
      <button
        type="button"
        onClick={handleApply}
        className="w-full py-2 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
      >
        Appliquer
      </button>
    </div>
  )
}

interface TextFilterContentProps {
  value: string | null | undefined
  onChange: (value: unknown) => void
  placeholder?: string
}

function TextFilterContent({ value, onChange, placeholder }: TextFilterContentProps) {
  const [localValue, setLocalValue] = useState(value || '')

  return (
    <div className="p-3">
      <input
        type="text"
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            onChange(localValue || null)
          }
        }}
        onBlur={() => onChange(localValue || null)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-dark-400 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
        autoFocus
      />
    </div>
  )
}

// ============================================================================
// MORE FILTERS DROPDOWN
// ============================================================================

interface MoreFiltersDropdownProps {
  filters: FilterConfig[]
  values: Record<string, unknown>
  onChange?: (key: string, value: unknown) => void
}

function MoreFiltersDropdown({ filters, values, onChange }: MoreFiltersDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const activeInMore = filters.filter((f) => {
    const v = values[f.key]
    return v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0)
  }).length

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors border',
          activeInMore > 0
            ? 'border-primary-500/50 bg-primary-500/10 text-primary-300'
            : 'border-dark-700 hover:bg-dark-800 text-dark-300'
        )}
      >
        <Filter className="h-4 w-4" />
        Plus
        {activeInMore > 0 && (
          <span className="w-5 h-5 flex items-center justify-center text-xs bg-primary-500 text-white rounded-full">
            {activeInMore}
          </span>
        )}
      </button>

      {isOpen && (
        <div
          className={cn(
            'absolute top-full right-0 mt-2 w-72 bg-dark-800 rounded-xl shadow-xl border border-dark-700 p-4 z-30',
            'animate-in fade-in slide-in-from-top-2 duration-200'
          )}
        >
          <div className="space-y-4">
            {filters.map((filter) => (
              <div key={filter.key}>
                <label className="block text-xs font-medium text-dark-400 uppercase tracking-wide mb-2">
                  {filter.label}
                </label>
                {filter.type === 'select' && (
                  <select
                    value={(values[filter.key] as string) || ''}
                    onChange={(e) => onChange?.(filter.key, e.target.value || null)}
                    className="w-full px-3 py-2 text-sm bg-dark-700 border border-dark-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary-500/50"
                  >
                    <option value="">Tous</option>
                    {filter.options?.map((opt) => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                )}
                {filter.type === 'text' && (
                  <input
                    type="text"
                    value={(values[filter.key] as string) || ''}
                    onChange={(e) => onChange?.(filter.key, e.target.value || null)}
                    placeholder={filter.placeholder}
                    className="w-full px-3 py-2 text-sm bg-dark-700 border border-dark-600 rounded-lg text-white placeholder-dark-400 focus:outline-none focus:ring-2 focus:ring-primary-500/50"
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================================
// PRESETS DROPDOWN
// ============================================================================

interface PresetsDropdownProps {
  presets: FilterPreset[]
  onSelect: (preset: FilterPreset) => void
  onClose: () => void
}

function PresetsDropdown({ presets, onSelect, onClose }: PresetsDropdownProps) {
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  return (
    <div
      ref={dropdownRef}
      className={cn(
        'absolute top-full right-0 mt-2 w-64 bg-dark-800 rounded-xl shadow-xl border border-dark-700 py-2 z-30',
        'animate-in fade-in slide-in-from-top-2 duration-200'
      )}
    >
      <div className="px-3 py-2 border-b border-dark-700">
        <span className="text-xs font-semibold uppercase text-dark-400">Filtres rapides</span>
      </div>
      <div className="py-1">
        {presets.map((preset, index) => {
          const Icon = preset.icon || Sparkles
          return (
            <button
              key={index}
              type="button"
              onClick={() => onSelect(preset)}
              className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-left text-dark-300 hover:bg-dark-700 transition-colors"
            >
              <Icon className="h-4 w-4 text-dark-400" />
              <div className="flex-1">
                <div className="font-medium text-white">{preset.label}</div>
                {preset.description && (
                  <div className="text-xs text-dark-500">{preset.description}</div>
                )}
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export { FilterDropdown, SelectFilterContent, DateFilterContent, RangeFilterContent }
