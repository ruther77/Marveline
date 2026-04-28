import { useState, useEffect } from 'react'
import { cn } from '../../lib/utils'

export interface MoneyInputProps {
  value: number // centimes
  onChange: (cents: number) => void
  label?: string
  min?: number // centimes
  max?: number // centimes
  disabled?: boolean
  placeholder?: string
  className?: string
  error?: string
}

export function MoneyInput({
  value,
  onChange,
  label,
  min,
  max,
  disabled = false,
  placeholder = '0,00',
  className,
  error,
}: MoneyInputProps) {
  const [display, setDisplay] = useState(value > 0 ? (value / 100).toFixed(2) : '')

  useEffect(() => {
    setDisplay(value > 0 ? (value / 100).toFixed(2) : '')
  }, [value])

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(',', '.')
    setDisplay(e.target.value)
    const parsed = parseFloat(raw)
    if (!isNaN(parsed) && parsed >= 0) {
      const cents = Math.round(parsed * 100)
      if (min !== undefined && cents < min) return
      if (max !== undefined && cents > max) return
      onChange(cents)
    } else if (raw === '' || raw === '0') {
      onChange(0)
    }
  }

  function handleBlur() {
    const parsed = parseFloat(display.replace(',', '.'))
    if (!isNaN(parsed) && parsed >= 0) {
      setDisplay((Math.round(parsed * 100) / 100).toFixed(2))
    } else {
      setDisplay(value > 0 ? (value / 100).toFixed(2) : '')
    }
  }

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      {label && <label className="text-sm font-medium text-dark-200">{label}</label>}
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-dark-400 text-sm">€</span>
        <input
          type="text"
          inputMode="decimal"
          value={display}
          onChange={handleChange}
          onBlur={handleBlur}
          disabled={disabled}
          placeholder={placeholder}
          className={cn(
            'w-full pl-8 pr-4 py-2 bg-dark-900 border rounded-lg text-dark-50 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-primary-500',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            error ? 'border-red-500' : 'border-dark-600'
          )}
        />
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
}
