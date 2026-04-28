/**
 * Tests unitaires pour components/ui/ViewToggle.tsx
 * ViewToggle, getStoredViewMode, setStoredViewMode
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ViewToggle, getStoredViewMode, setStoredViewMode } from '../ViewToggle'

// ─── getStoredViewMode ────────────────────────────────────────────────────────

describe('getStoredViewMode', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('retourne "table" par défaut si rien en localStorage', () => {
    expect(getStoredViewMode()).toBe('table')
  })

  it('retourne "grid" si "grid" est stocké', () => {
    localStorage.setItem('catalogue-view-mode', 'grid')
    expect(getStoredViewMode()).toBe('grid')
  })

  it('retourne "table" pour toute valeur inconnue', () => {
    localStorage.setItem('catalogue-view-mode', 'list')
    expect(getStoredViewMode()).toBe('table')
  })
})

// ─── setStoredViewMode ────────────────────────────────────────────────────────

describe('setStoredViewMode', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('stocke "grid" dans localStorage', () => {
    setStoredViewMode('grid')
    expect(localStorage.getItem('catalogue-view-mode')).toBe('grid')
  })

  it('stocke "table" dans localStorage', () => {
    setStoredViewMode('table')
    expect(localStorage.getItem('catalogue-view-mode')).toBe('table')
  })
})

// ─── ViewToggle ───────────────────────────────────────────────────────────────

describe('ViewToggle - rendu de base', () => {
  it('affiche les boutons Vue tableau et Vue grille', () => {
    render(<ViewToggle mode="table" onChange={vi.fn()} />)
    expect(screen.getByLabelText('Vue tableau')).toBeInTheDocument()
    expect(screen.getByLabelText('Vue grille')).toBeInTheDocument()
  })
})

describe('ViewToggle - onChange', () => {
  it('clic sur Vue grille appelle onChange("grid")', () => {
    const onChange = vi.fn()
    render(<ViewToggle mode="table" onChange={onChange} />)
    fireEvent.click(screen.getByLabelText('Vue grille'))
    expect(onChange).toHaveBeenCalledWith('grid')
  })

  it('clic sur Vue tableau appelle onChange("table")', () => {
    const onChange = vi.fn()
    render(<ViewToggle mode="grid" onChange={onChange} />)
    fireEvent.click(screen.getByLabelText('Vue tableau'))
    expect(onChange).toHaveBeenCalledWith('table')
  })
})

describe('ViewToggle - className', () => {
  it('applique className personnalisée', () => {
    const { container } = render(<ViewToggle mode="table" onChange={vi.fn()} className="my-toggle" />)
    expect(container.querySelector('.my-toggle')).not.toBeNull()
  })
})
