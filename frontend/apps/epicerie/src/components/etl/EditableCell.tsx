// Cellule éditable inline — clic pour éditer, blur/Enter pour confirmer

import { useState, useRef, useEffect } from 'react'
import type { FieldAlert } from '@/types/etl_import'

const ALERT_STYLES: Record<string, string> = {
  error: 'bg-red-50 border border-red-300 text-red-600',
  warning: 'bg-amber-50 border border-amber-300 text-amber-600',
}

interface EditableCellProps {
  value: string | number | null | undefined
  onChange: (val: string) => void
  type?: 'text' | 'number'
  className?: string
  alert?: FieldAlert
  placeholder?: string
  onKeyNav?: (e: React.KeyboardEvent) => void
  cellRef?: (el: HTMLElement | null) => void
}

export default function EditableCell({
  value, onChange, type = 'text', className = '',
  alert = null, placeholder = '', onKeyNav, cellRef,
}: EditableCellProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(String(value ?? ''))
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing && inputRef.current) inputRef.current.focus()
  }, [editing])

  const isEmpty = value === null || value === undefined || value === '' || value === 0
  const alertStyle = alert ? ALERT_STYLES[alert] : ''

  if (!editing) {
    return (
      <button
        ref={el => cellRef?.(el)}
        type="button"
        onClick={() => { setDraft(String(value ?? '')); setEditing(true) }}
        onKeyDown={e => {
          if (onKeyNav && (e.key === 'Tab' || e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
            onKeyNav(e)
          }
        }}
        className={`block text-left w-full min-h-[28px] cursor-pointer rounded transition-colors ${
          alert && isEmpty
            ? `${alertStyle} px-2 py-1 text-[11px] italic`
            : isEmpty
              ? 'px-1 py-1 text-slate-300 hover:bg-slate-100 italic text-[11px]'
              : `px-1 py-1 hover:bg-emerald-50 hover:text-emerald-700 ${className}`
        }`}
      >
        {isEmpty ? (placeholder || 'Cliquer pour saisir') : value}
      </button>
    )
  }

  return (
    <input
      ref={inputRef}
      type={type}
      value={draft}
      onChange={e => setDraft(e.target.value)}
      onBlur={() => { onChange(draft); setEditing(false) }}
      onKeyDown={e => {
        if (e.key === 'Enter') { onChange(draft); setEditing(false); onKeyNav?.(e) }
        if (e.key === 'Escape') setEditing(false)
        if (e.key === 'Tab' && onKeyNav) onKeyNav(e)
      }}
      placeholder={placeholder}
      className="bg-white border border-emerald-400 rounded px-2 py-1 text-xs w-full outline-none"
    />
  )
}
