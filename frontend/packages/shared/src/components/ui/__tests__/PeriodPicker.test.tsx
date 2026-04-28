/**
 * Tests unitaires pour components/ui/PeriodPicker.tsx
 * PeriodPicker, DEFAULT_PRESETS
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PeriodPicker, DEFAULT_PRESETS } from '../PeriodPicker'
import type { PeriodValue } from '../PeriodPicker'

const emptyValue: PeriodValue = {
  start: null,
  end: null,
  preset: null,
  compareEnabled: false,
  compareStart: null,
  compareEnd: null,
}

describe('PeriodPicker - DEFAULT_PRESETS', () => {
  it('contient "today"', () => {
    expect(DEFAULT_PRESETS.find(p => p.key === 'today')).toBeDefined()
  })

  it('contient "yesterday"', () => {
    expect(DEFAULT_PRESETS.find(p => p.key === 'yesterday')).toBeDefined()
  })

  it('getRange() retourne un objet { start, end }', () => {
    const preset = DEFAULT_PRESETS[0]
    const range = preset.getRange()
    expect(range.start).toBeInstanceOf(Date)
    expect(range.end).toBeInstanceOf(Date)
  })

  it('la liste est non vide', () => {
    expect(DEFAULT_PRESETS.length).toBeGreaterThan(0)
  })
})

describe('PeriodPicker - rendu de base', () => {
  it('pas de badge de période si aucune date sélectionnée', () => {
    render(<PeriodPicker value={emptyValue} onChange={vi.fn()} />)
    // Sans start/end, la section de badge n'est pas rendue
    expect(screen.queryByText(/Comparer avec N-1/)).toBeNull()
  })

  it('affiche des boutons de presets rapides', () => {
    render(<PeriodPicker value={emptyValue} onChange={vi.fn()} />)
    // Les quick presets (today, yesterday, etc.) sont affichés comme boutons
    const buttons = screen.getAllByRole('button')
    expect(buttons.length).toBeGreaterThan(0)
  })

  it('affiche le preset "Aujourd\'hui" parmi les boutons rapides', () => {
    render(<PeriodPicker value={emptyValue} onChange={vi.fn()} />)
    expect(screen.getByText("Auj.")).toBeInTheDocument()
  })
})

describe('PeriodPicker - sélection d\'un preset rapide', () => {
  it('clic sur "Auj." appelle onChange', () => {
    const onChange = vi.fn()
    render(<PeriodPicker value={emptyValue} onChange={onChange} />)
    fireEvent.click(screen.getByText("Auj."))
    expect(onChange).toHaveBeenCalled()
  })

  it('preset sélectionné inclut start, end et preset="today"', () => {
    const onChange = vi.fn()
    render(<PeriodPicker value={emptyValue} onChange={onChange} />)
    fireEvent.click(screen.getByText("Auj."))
    const result: PeriodValue = onChange.mock.calls[0][0]
    expect(result.start).toBeInstanceOf(Date)
    expect(result.end).toBeInstanceOf(Date)
    expect(result.preset).toBe('today')
  })
})

describe('PeriodPicker - valeur active', () => {
  it('affiche la date formatée quand start et end sont définis', () => {
    const today = new Date()
    const value: PeriodValue = {
      ...emptyValue,
      preset: 'today',
      start: today,
      end: today,
    }
    render(<PeriodPicker value={value} onChange={vi.fn()} />)
    // La date est formatée (format fr, ex: "15 janv. 2026")
    // Au moins une valeur non-"Sélectionner" est affichée
    expect(screen.queryByText('Sélectionner une période')).toBeNull()
  })
})
