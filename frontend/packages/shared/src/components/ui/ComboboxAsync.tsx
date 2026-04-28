import { useState, useEffect, useRef, useLayoutEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { Search, X, ChevronDown } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface ComboboxItem {
  id: number
  label: string
}

export interface ComboboxAsyncProps {
  value: number | ''
  onChange: (id: number | '') => void
  items: ComboboxItem[]
  onSearchChange: (query: string) => void
  isLoading?: boolean
  placeholder?: string
  className?: string
}

export function ComboboxAsync({
  value,
  onChange,
  items,
  onSearchChange,
  isLoading = false,
  placeholder = 'Rechercher…',
  className,
}: ComboboxAsyncProps) {
  const [inputValue, setInputValue] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({})

  const selectedItem = items.find((i) => i.id === value)

  const updateDropdownPosition = useCallback(() => {
    if (!inputRef.current) return
    const rect = inputRef.current.getBoundingClientRect()
    const spaceBelow = window.innerHeight - rect.bottom
    const dropdownMaxH = 224
    const openAbove = spaceBelow < dropdownMaxH && rect.top > spaceBelow

    setDropdownStyle({
      position: 'fixed',
      width: rect.width,
      left: rect.left,
      ...(openAbove
        ? { bottom: window.innerHeight - rect.top + 4 }
        : { top: rect.bottom + 4 }),
      zIndex: 9999,
    })
  }, [])

  useLayoutEffect(() => {
    if (isOpen) updateDropdownPosition()
  }, [isOpen, items, updateDropdownPosition])

  useEffect(() => {
    if (!isOpen) return
    const onScrollOrResize = () => updateDropdownPosition()
    window.addEventListener('scroll', onScrollOrResize, true)
    window.addEventListener('resize', onScrollOrResize)
    return () => {
      window.removeEventListener('scroll', onScrollOrResize, true)
      window.removeEventListener('resize', onScrollOrResize)
    }
  }, [isOpen, updateDropdownPosition])

  useEffect(() => {
    if (value === '') setInputValue('')
  }, [value])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node
      if (
        containerRef.current && !containerRef.current.contains(target) &&
        dropdownRef.current && !dropdownRef.current.contains(target)
      ) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handleInput = (q: string) => {
    setInputValue(q)
    onSearchChange(q)
    setIsOpen(true)
    if (!q) onChange('')
  }

  const handleFocus = () => {
    setIsOpen(true)
    if (value !== '') setInputValue('')
  }

  const handleSelect = (item: ComboboxItem) => {
    onChange(item.id)
    setInputValue(item.label)
    setIsOpen(false)
  }

  const handleClear = () => {
    onChange('')
    setInputValue('')
    onSearchChange('')
    setIsOpen(false)
  }

  const displayValue = value !== '' && !isOpen ? (selectedItem?.label ?? inputValue) : inputValue

  const dropdown = isOpen ? (
    <div
      ref={dropdownRef}
      style={dropdownStyle}
      className="bg-[var(--s1)] border border-[var(--border2)] rounded-xl shadow-xl overflow-hidden"
    >
      <div className="max-h-56 overflow-y-auto">
        {isLoading ? (
          <div className="px-4 py-4 text-center text-[var(--muted)] text-sm">Chargement…</div>
        ) : items.length === 0 ? (
          <div className="px-4 py-4 text-center text-[var(--muted)] text-sm">Aucun résultat</div>
        ) : (
          items.map((item) => (
            <button
              key={item.id}
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => handleSelect(item)}
              className={cn(
                'w-full text-left px-4 py-2 text-sm hover:bg-[var(--s2)] transition-colors',
                value === item.id
                  ? 'text-primary-400 bg-primary-500/10'
                  : 'text-[var(--text)]'
              )}
            >
              {item.label}
            </button>
          ))
        )}
      </div>
    </div>
  ) : null

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)] pointer-events-none" />
        <input
          ref={inputRef}
          type="text"
          value={displayValue}
          onChange={(e) => handleInput(e.target.value)}
          onFocus={handleFocus}
          placeholder={placeholder}
          autoComplete="off"
          className="input w-full pl-9 pr-8 py-2 text-sm"
        />
        {value !== '' ? (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-[var(--muted)] hover:text-[var(--text)]"
            aria-label="Effacer la sélection"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        ) : (
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)] pointer-events-none" />
        )}
      </div>

      {createPortal(dropdown, document.body)}
    </div>
  )
}
