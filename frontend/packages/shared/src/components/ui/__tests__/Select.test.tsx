/**
 * Tests unitaires pour components/ui/Select.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Select } from '../Select'

const options = [
  { value: 'a', label: 'Option A' },
  { value: 'b', label: 'Option B' },
  { value: 'c', label: 'Option C', disabled: true },
]

describe('Select - rendu de base', () => {
  it('rend un select', () => {
    render(<Select options={options} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('affiche toutes les options', () => {
    render(<Select options={options} />)
    expect(screen.getByText('Option A')).toBeInTheDocument()
    expect(screen.getByText('Option B')).toBeInTheDocument()
    expect(screen.getByText('Option C')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<Select options={options} label="Catégorie" />)
    expect(screen.getByText('Catégorie')).toBeInTheDocument()
  })

  it('affiche le placeholder si fourni', () => {
    render(<Select options={options} placeholder="Sélectionner..." />)
    expect(screen.getByText('Sélectionner...')).toBeInTheDocument()
  })

  it('affiche l\'erreur si fournie', () => {
    render(<Select options={options} error="Sélection requise" />)
    expect(screen.getByText('Sélection requise')).toBeInTheDocument()
  })

  it('affiche le hint si fourni (sans erreur)', () => {
    render(<Select options={options} hint="Choisissez une option" />)
    expect(screen.getByText('Choisissez une option')).toBeInTheDocument()
  })

  it('hint masqué si erreur présente', () => {
    render(<Select options={options} hint="Aide" error="Erreur" />)
    expect(screen.queryByText('Aide')).toBeNull()
  })
})

describe('Select - option disabled', () => {
  it('option disabled est désactivée', () => {
    render(<Select options={options} />)
    const optionC = screen.getByText('Option C')
    expect(optionC).toBeDisabled()
  })
})

describe('Select - disabled', () => {
  it('select désactivé', () => {
    render(<Select options={options} disabled />)
    expect(screen.getByRole('combobox')).toBeDisabled()
  })
})

describe('Select - onChange', () => {
  it('onChange appelé lors du changement de valeur', () => {
    const onChange = vi.fn()
    render(<Select options={options} onChange={onChange} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'b' } })
    expect(onChange).toHaveBeenCalled()
  })
})

describe('Select - forwardRef', () => {
  it('transmet la ref au select', () => {
    const ref = { current: null } as React.RefObject<HTMLSelectElement>
    render(<Select options={options} ref={ref} />)
    expect(ref.current).not.toBeNull()
    expect(ref.current?.tagName).toBe('SELECT')
  })
})

describe('Select - displayName', () => {
  it('displayName = "Select"', () => {
    expect(Select.displayName).toBe('Select')
  })
})
