import { useState, forwardRef } from 'react';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, isSameDay, addMonths, subMonths, isToday, startOfWeek, endOfWeek } from 'date-fns';
import { fr } from 'date-fns/locale';
import { cn } from '../../lib/utils';
import { Dropdown } from './Dropdown';

export interface DatePickerProps {
  value?: Date | null;
  onChange: (date: Date | null) => void;
  label?: string;
  placeholder?: string;
  error?: string;
  hint?: string;
  disabled?: boolean;
  minDate?: Date;
  maxDate?: Date;
  className?: string;
}

export const DatePicker = forwardRef<HTMLInputElement, DatePickerProps>(
  (
    {
      value,
      onChange,
      label,
      placeholder = 'Sélectionner une date',
      error,
      hint,
      disabled,
      minDate,
      maxDate,
      className,
    },
    _ref
  ) => {
    const [currentMonth, setCurrentMonth] = useState(value || new Date());
    const [isOpen, setIsOpen] = useState(false);

    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);
    const calendarStart = startOfWeek(monthStart, { locale: fr });
    const calendarEnd = endOfWeek(monthEnd, { locale: fr });
    const days = eachDayOfInterval({ start: calendarStart, end: calendarEnd });

    const weekDays = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di'];

    const isDateDisabled = (date: Date) => {
      if (minDate && date < minDate) return true;
      if (maxDate && date > maxDate) return true;
      return false;
    };

    const handleSelect = (date: Date) => {
      if (!isDateDisabled(date)) {
        onChange(date);
        setIsOpen(false);
      }
    };

    const handleClear = () => {
      onChange(null);
      setIsOpen(false);
    };

    return (
      <div className={className}>
        {label && (
          <label className="block text-sm font-medium text-dark-200 mb-1.5">
            {label}
          </label>
        )}
        <Dropdown
          position="bottom-left"
          closeOnSelect={false}
          trigger={
            <div
              className={cn(
                'flex items-center gap-2 w-full px-4 py-2.5 bg-dark-800 border rounded-lg cursor-pointer transition-colors',
                disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-dark-500',
                error ? 'border-red-500' : 'border-dark-600',
                isOpen && 'border-primary-500 ring-2 ring-primary-500/20'
              )}
              onClick={() => !disabled && setIsOpen(!isOpen)}
            >
              <Calendar className="w-4 h-4 text-dark-400" />
              <span className={value ? 'text-white flex-1' : 'text-dark-400 flex-1'}>
                {value ? format(value, 'dd MMMM yyyy', { locale: fr }) : placeholder}
              </span>
            </div>
          }
        >
          <div className="p-3 w-72">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
              <button
                onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
                className="p-1.5 hover:bg-dark-700 rounded-lg transition-colors"
              >
                <ChevronLeft className="w-4 h-4 text-dark-400" />
              </button>
              <span className="font-medium text-white">
                {format(currentMonth, 'MMMM yyyy', { locale: fr })}
              </span>
              <button
                onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
                className="p-1.5 hover:bg-dark-700 rounded-lg transition-colors"
              >
                <ChevronRight className="w-4 h-4 text-dark-400" />
              </button>
            </div>

            {/* Week days */}
            <div className="grid grid-cols-7 gap-1 mb-1">
              {weekDays.map((day) => (
                <div
                  key={day}
                  className="text-center text-xs font-medium text-dark-400 py-1"
                >
                  {day}
                </div>
              ))}
            </div>

            {/* Days grid */}
            <div className="grid grid-cols-7 gap-1">
              {days.map((day, i) => {
                const isSelected = value && isSameDay(day, value);
                const isCurrentMonth = isSameMonth(day, currentMonth);
                const isDisabled = isDateDisabled(day);
                const isTodayDate = isToday(day);

                return (
                  <button
                    key={i}
                    onClick={() => handleSelect(day)}
                    disabled={isDisabled}
                    className={cn(
                      'w-8 h-8 text-sm rounded-lg transition-colors',
                      isSelected
                        ? 'bg-primary-600 text-white'
                        : isTodayDate
                        ? 'bg-dark-700 text-white'
                        : isCurrentMonth
                        ? 'text-white hover:bg-dark-700'
                        : 'text-dark-500',
                      isDisabled && 'opacity-30 cursor-not-allowed'
                    )}
                  >
                    {format(day, 'd')}
                  </button>
                );
              })}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-dark-700">
              <button
                onClick={() => handleSelect(new Date())}
                className="text-sm text-primary-500 hover:text-primary-400"
              >
                Aujourd'hui
              </button>
              {value && (
                <button
                  onClick={handleClear}
                  className="text-sm text-dark-400 hover:text-white"
                >
                  Effacer
                </button>
              )}
            </div>
          </div>
        </Dropdown>
        {error && <p className="mt-1.5 text-sm text-red-500">{error}</p>}
        {hint && !error && <p className="mt-1.5 text-sm text-dark-400">{hint}</p>}
      </div>
    );
  }
);

DatePicker.displayName = 'DatePicker';

// Date Range Picker
export interface DateRangePickerProps {
  startDate?: Date | null;
  endDate?: Date | null;
  onChange: (range: { start: Date | null; end: Date | null }) => void;
  label?: string;
  error?: string;
  disabled?: boolean;
  className?: string;
}

export function DateRangePicker({
  startDate,
  endDate,
  onChange,
  label,
  error,
  disabled,
  className,
}: DateRangePickerProps) {
  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-dark-200 mb-1.5">
          {label}
        </label>
      )}
      <div className="flex items-center gap-2">
        <DatePicker
          value={startDate}
          onChange={(date) => onChange({ start: date, end: endDate || null })}
          placeholder="Date début"
          disabled={disabled}
          maxDate={endDate || undefined}
        />
        <span className="text-dark-400">→</span>
        <DatePicker
          value={endDate}
          onChange={(date) => onChange({ start: startDate || null, end: date })}
          placeholder="Date fin"
          disabled={disabled}
          minDate={startDate || undefined}
        />
      </div>
      {error && <p className="mt-1.5 text-sm text-red-500">{error}</p>}
    </div>
  );
}
