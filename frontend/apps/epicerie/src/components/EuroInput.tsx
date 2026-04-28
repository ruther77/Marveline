/**
 * Input monétaire — affiche en euros, stocke en centimes.
 *
 * L'opérateur saisit "12.50" ou "12,50" et le composant appelle
 * onChange(1250) en centimes. Affiche "—" si null.
 */
import { useState, useCallback } from 'react'

interface EuroInputProps {
  value: number | null
  onChange: (centimes: number) => void
  placeholder?: string
  alert?: 'error' | 'warning' | null
  disabled?: boolean
  className?: string
}

function centimesToEuro(cts: number | null): string {
  if (cts === null || cts === undefined) return ''
  return (cts / 100).toFixed(2)
}

function euroToCentimes(input: string): number | null {
  const normalized = input.replace(',', '.').trim()
  if (!normalized) return null
  const val = parseFloat(normalized)
  if (isNaN(val) || val < 0) return null
  return Math.round(val * 100)
}

export default function EuroInput({
  value,
  onChange,
  placeholder = '0.00',
  alert,
  disabled = false,
  className = '',
}: EuroInputProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')

  const handleFocus = useCallback(() => {
    setDraft(centimesToEuro(value))
    setEditing(true)
  }, [value])

  const handleBlur = useCallback(() => {
    setEditing(false)
    const cts = euroToCentimes(draft)
    if (cts !== null) {
      onChange(cts)
    }
  }, [draft, onChange])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      ;(e.target as HTMLInputElement).blur()
    }
    if (e.key === 'Escape') {
      setEditing(false)
    }
  }, [])

  const alertCls = alert === 'error'
    ? 'bg-red-600/[.08] text-red-600'
    : alert === 'warning'
      ? 'bg-amber-700/[.08] text-amber-700'
      : ''

  if (editing && !disabled) {
    return (
      <input
        type="text"
        inputMode="decimal"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        autoFocus
        placeholder={placeholder}
        className={`w-full px-2 py-1 text-[12px] border border-emerald-500 rounded outline-none text-right font-mono ${className}`}
      />
    )
  }

  const display = value !== null && value !== undefined
    ? `${centimesToEuro(value)} €`
    : '—'

  return (
    <button
      type="button"
      onClick={handleFocus}
      disabled={disabled}
      className={`w-full px-2 py-1 text-[12px] text-right font-mono rounded cursor-pointer hover:bg-slate-100 transition-colors ${alertCls} ${disabled ? 'opacity-50 cursor-default' : ''} ${className}`}
    >
      {display}
    </button>
  )
}
