import { useState, useCallback, useMemo } from 'react';
import {
  Calendar,
  ChevronDown,
  Check,
  ArrowLeftRight,
  X,
} from 'lucide-react';
import {
  format,
  startOfDay,
  endOfDay,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  startOfQuarter,
  endOfQuarter,
  startOfYear,
  endOfYear,
  subDays,
  subMonths,
  subQuarters,
  subYears,
  differenceInDays,
} from 'date-fns';
import { fr } from 'date-fns/locale';
import { cn } from '../../lib/utils';
import { DateRangePicker } from './DatePicker';
import { Dropdown } from './Dropdown';

// =============================================================================
// Types
// =============================================================================

export interface PeriodPreset {
  key: string;
  label: string;
  shortLabel?: string;
  getRange: () => { start: Date; end: Date };
}

export interface PeriodValue {
  start: Date | null;
  end: Date | null;
  preset: string | null;
  compareEnabled: boolean;
  compareStart: Date | null;
  compareEnd: Date | null;
}

export interface PeriodPickerProps {
  value: PeriodValue;
  onChange: (value: PeriodValue) => void;
  presets?: PeriodPreset[];
  showComparison?: boolean;
  showCustom?: boolean;
  className?: string;
  size?: 'sm' | 'md';
}

// =============================================================================
// Default Presets
// =============================================================================

// const today = () => startOfDay(new Date());

export const DEFAULT_PRESETS: PeriodPreset[] = [
  {
    key: 'today',
    label: "Aujourd'hui",
    shortLabel: "Auj.",
    getRange: () => ({
      start: startOfDay(new Date()),
      end: endOfDay(new Date()),
    }),
  },
  {
    key: 'yesterday',
    label: 'Hier',
    getRange: () => ({
      start: startOfDay(subDays(new Date(), 1)),
      end: endOfDay(subDays(new Date(), 1)),
    }),
  },
  {
    key: 'last_7_days',
    label: '7 derniers jours',
    shortLabel: '7j',
    getRange: () => ({
      start: startOfDay(subDays(new Date(), 6)),
      end: endOfDay(new Date()),
    }),
  },
  {
    key: 'last_30_days',
    label: '30 derniers jours',
    shortLabel: '30j',
    getRange: () => ({
      start: startOfDay(subDays(new Date(), 29)),
      end: endOfDay(new Date()),
    }),
  },
  {
    key: 'this_week',
    label: 'Cette semaine',
    getRange: () => ({
      start: startOfWeek(new Date(), { locale: fr }),
      end: endOfWeek(new Date(), { locale: fr }),
    }),
  },
  {
    key: 'last_week',
    label: 'Semaine dernière',
    getRange: () => {
      const lastWeek = subDays(startOfWeek(new Date(), { locale: fr }), 1);
      return {
        start: startOfWeek(lastWeek, { locale: fr }),
        end: endOfWeek(lastWeek, { locale: fr }),
      };
    },
  },
  {
    key: 'this_month',
    label: 'Ce mois',
    shortLabel: 'Mois',
    getRange: () => ({
      start: startOfMonth(new Date()),
      end: endOfMonth(new Date()),
    }),
  },
  {
    key: 'last_month',
    label: 'Mois dernier',
    getRange: () => {
      const lastMonth = subMonths(new Date(), 1);
      return {
        start: startOfMonth(lastMonth),
        end: endOfMonth(lastMonth),
      };
    },
  },
  {
    key: 'this_quarter',
    label: 'Ce trimestre',
    shortLabel: 'Trim.',
    getRange: () => ({
      start: startOfQuarter(new Date()),
      end: endOfQuarter(new Date()),
    }),
  },
  {
    key: 'last_quarter',
    label: 'Trimestre dernier',
    getRange: () => {
      const lastQuarter = subQuarters(new Date(), 1);
      return {
        start: startOfQuarter(lastQuarter),
        end: endOfQuarter(lastQuarter),
      };
    },
  },
  {
    key: 'this_year',
    label: 'Cette année',
    shortLabel: 'Année',
    getRange: () => ({
      start: startOfYear(new Date()),
      end: endOfYear(new Date()),
    }),
  },
  {
    key: 'last_year',
    label: 'Année dernière',
    getRange: () => {
      const lastYear = subYears(new Date(), 1);
      return {
        start: startOfYear(lastYear),
        end: endOfYear(lastYear),
      };
    },
  },
];

// Quick presets shown as buttons
const QUICK_PRESET_KEYS = ['today', 'last_7_days', 'last_30_days', 'this_month'];

// =============================================================================
// Helper Functions
// =============================================================================

function calculateComparisonPeriod(start: Date, end: Date): { start: Date; end: Date } {
  const days = differenceInDays(end, start) + 1;
  return {
    start: subDays(start, days),
    end: subDays(end, days),
  };
}

function formatPeriodDisplay(start: Date | null, end: Date | null): string {
  if (!start || !end) return 'Sélectionner une période';

  const sameDay = format(start, 'yyyy-MM-dd') === format(end, 'yyyy-MM-dd');
  if (sameDay) {
    return format(start, 'd MMM yyyy', { locale: fr });
  }

  const sameMonth = format(start, 'yyyy-MM') === format(end, 'yyyy-MM');
  if (sameMonth) {
    return `${format(start, 'd')} - ${format(end, 'd MMM yyyy', { locale: fr })}`;
  }

  const sameYear = format(start, 'yyyy') === format(end, 'yyyy');
  if (sameYear) {
    return `${format(start, 'd MMM', { locale: fr })} - ${format(end, 'd MMM yyyy', { locale: fr })}`;
  }

  return `${format(start, 'd MMM yyyy', { locale: fr })} - ${format(end, 'd MMM yyyy', { locale: fr })}`;
}

// =============================================================================
// Component
// =============================================================================

export function PeriodPicker({
  value,
  onChange,
  presets = DEFAULT_PRESETS,
  showComparison = true,
  showCustom = true,
  className,
  size = 'md',
}: PeriodPickerProps) {
  const [, setShowCustomPicker] = useState(false);
  const [, setShowMorePresets] = useState(false);

  // Get presets for quick buttons and dropdown
  const quickPresets = useMemo(
    () => presets.filter((p) => QUICK_PRESET_KEYS.includes(p.key)),
    [presets]
  );
  const morePresets = useMemo(
    () => presets.filter((p) => !QUICK_PRESET_KEYS.includes(p.key)),
    [presets]
  );

  // Current preset label (used for display purposes)
  const _currentPresetLabel = useMemo(() => {
    if (value.preset === 'custom') return 'Personnalisé';
    const preset = presets.find((p) => p.key === value.preset);
    return preset?.label || 'Sélectionner';
  }, [value.preset, presets]);
  void _currentPresetLabel; // Suppress unused warning

  // Handle preset selection
  const handlePresetSelect = useCallback(
    (preset: PeriodPreset) => {
      const range = preset.getRange();
      const comparison = calculateComparisonPeriod(range.start, range.end);

      onChange({
        start: range.start,
        end: range.end,
        preset: preset.key,
        compareEnabled: value.compareEnabled,
        compareStart: comparison.start,
        compareEnd: comparison.end,
      });
      setShowCustomPicker(false);
      setShowMorePresets(false);
    },
    [onChange, value.compareEnabled]
  );

  // Handle custom date range
  const handleCustomRangeChange = useCallback(
    (range: { start: Date | null; end: Date | null }) => {
      if (range.start && range.end) {
        const comparison = calculateComparisonPeriod(range.start, range.end);
        onChange({
          start: range.start,
          end: range.end,
          preset: 'custom',
          compareEnabled: value.compareEnabled,
          compareStart: comparison.start,
          compareEnd: comparison.end,
        });
      } else {
        onChange({
          ...value,
          start: range.start,
          end: range.end,
          preset: 'custom',
        });
      }
    },
    [onChange, value]
  );

  // Toggle comparison
  const handleCompareToggle = useCallback(() => {
    onChange({
      ...value,
      compareEnabled: !value.compareEnabled,
    });
  }, [onChange, value]);

  // Clear selection
  const handleClear = useCallback(() => {
    onChange({
      start: null,
      end: null,
      preset: null,
      compareEnabled: false,
      compareStart: null,
      compareEnd: null,
    });
    setShowCustomPicker(false);
  }, [onChange]);

  const buttonSize = size === 'sm' ? 'px-2 py-1 text-xs' : 'px-4 py-1.5 text-sm';

  return (
    <div className={cn('space-y-2', className)}>
      {/* Main row with presets */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Quick preset buttons */}
        {quickPresets.map((preset) => (
          <button
            key={preset.key}
            onClick={() => handlePresetSelect(preset)}
            className={cn(
              'rounded-lg font-medium transition-all',
              buttonSize,
              value.preset === preset.key
                ? 'bg-primary-500/20 text-primary-400 border border-primary-500/50'
                : 'bg-dark-900 text-dark-300 border border-dark-600 hover:bg-dark-600 hover:text-dark-50'
            )}
          >
            {preset.shortLabel || preset.label}
          </button>
        ))}

        {/* More presets dropdown */}
        {morePresets.length > 0 && (
          <Dropdown
            position="bottom-left"
            trigger={
              <button
                className={cn(
                  'flex items-center gap-1 rounded-lg font-medium transition-all',
                  buttonSize,
                  morePresets.some((p) => p.key === value.preset)
                    ? 'bg-primary-500/20 text-primary-400 border border-primary-500/50'
                    : 'bg-dark-900 text-dark-300 border border-dark-600 hover:bg-dark-600 hover:text-dark-50'
                )}
              >
                Plus
                <ChevronDown className="w-3 h-3" />
              </button>
            }
          >
            <div className="py-1 min-w-[180px]">
              {morePresets.map((preset) => (
                <button
                  key={preset.key}
                  onClick={() => handlePresetSelect(preset)}
                  className={cn(
                    'w-full flex items-center justify-between px-4 py-2 text-sm transition-colors',
                    value.preset === preset.key
                      ? 'bg-primary-500/10 text-primary-400'
                      : 'text-dark-200 hover:bg-dark-600'
                  )}
                >
                  {preset.label}
                  {value.preset === preset.key && <Check className="w-4 h-4" />}
                </button>
              ))}
            </div>
          </Dropdown>
        )}

        {/* Custom date picker trigger */}
        {showCustom && (
          <Dropdown
            position="bottom-left"
            closeOnSelect={false}
            trigger={
              <button
                className={cn(
                  'flex items-center gap-1.5 rounded-lg font-medium transition-all',
                  buttonSize,
                  value.preset === 'custom'
                    ? 'bg-primary-500/20 text-primary-400 border border-primary-500/50'
                    : 'bg-dark-900 text-dark-300 border border-dark-600 hover:bg-dark-600 hover:text-dark-50'
                )}
              >
                <Calendar className="w-3.5 h-3.5" />
                Personnalisé
              </button>
            }
          >
            <div className="p-4">
              <DateRangePicker
                startDate={value.start}
                endDate={value.end}
                onChange={handleCustomRangeChange}
              />
            </div>
          </Dropdown>
        )}

        {/* Clear button */}
        {value.preset && (
          <button
            onClick={handleClear}
            className="p-1.5 text-dark-400 hover:text-dark-50 hover:bg-dark-600 rounded-lg transition-colors"
            title="Effacer"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Period display and comparison toggle */}
      {value.start && value.end && (
        <div className="flex flex-wrap items-center gap-4 text-sm">
          {/* Current period badge */}
          <div className="flex items-center gap-2 px-4 py-1.5 bg-dark-900/50 rounded-lg">
            <Calendar className="w-4 h-4 text-primary-400" />
            <span className="font-medium">
              {formatPeriodDisplay(value.start, value.end)}
            </span>
          </div>

          {/* Comparison toggle */}
          {showComparison && (
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={value.compareEnabled}
                onChange={handleCompareToggle}
                className="w-4 h-4 rounded border-dark-500 bg-dark-900 text-primary-500 focus:ring-primary-500/20"
              />
              <span className="text-dark-300">Comparer avec N-1</span>
            </label>
          )}

          {/* Comparison period display */}
          {value.compareEnabled && value.compareStart && value.compareEnd && (
            <div className="flex items-center gap-2 px-4 py-1.5 bg-amber-500/10 border border-amber-500/30 rounded-lg">
              <ArrowLeftRight className="w-4 h-4 text-amber-400" />
              <span className="text-amber-400">
                vs {formatPeriodDisplay(value.compareStart, value.compareEnd)}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Default Value Helper
// =============================================================================

export function getDefaultPeriodValue(presetKey: string = 'last_30_days'): PeriodValue {
  const preset = DEFAULT_PRESETS.find((p) => p.key === presetKey);
  if (!preset) {
    return {
      start: null,
      end: null,
      preset: null,
      compareEnabled: false,
      compareStart: null,
      compareEnd: null,
    };
  }

  const range = preset.getRange();
  const comparison = calculateComparisonPeriod(range.start, range.end);

  return {
    start: range.start,
    end: range.end,
    preset: presetKey,
    compareEnabled: false,
    compareStart: comparison.start,
    compareEnd: comparison.end,
  };
}
