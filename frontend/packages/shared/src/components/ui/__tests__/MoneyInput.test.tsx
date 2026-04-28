/**
 * Tests unitaires pour components/ui/MoneyInput.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MoneyInput } from '../MoneyInput'

describe('MoneyInput - rendu de base', () => {
  it('rend un input de type text', () => {
    render(<MoneyInput value={0} onChange={vi.fn()} />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('affiche le symbole €', () => {
    render(<MoneyInput value={0} onChange={vi.fn()} />)
    expect(screen.getByText('€')).toBeInTheDocument()
  })

  it('affiche le label si fourni', () => {
    render(<MoneyInput value={0} onChange={vi.fn()} label="Montant" />)
    expect(screen.getByText('Montant')).toBeInTheDocument()
  })

  it('affiche l\'erreur si fournie', () => {
    render(<MoneyInput value={0} onChange={vi.fn()} error="Montant requis" />)
    expect(screen.getByText('Montant requis')).toBeInTheDocument()
  })

  it('disabled rend l\'input désactivé', () => {
    render(<MoneyInput value={0} onChange={vi.fn()} disabled />)
    expect(screen.getByRole('textbox')).toBeDisabled()
  })
})

describe('MoneyInput - valeur initiale', () => {
  it('value=1250 → affiche "12.50"', () => {
    render(<MoneyInput value={1250} onChange={vi.fn()} />)
    expect(screen.getByRole('textbox')).toHaveValue('12.50')
  })

  it('value=0 → champ vide', () => {
    render(<MoneyInput value={0} onChange={vi.fn()} />)
    expect(screen.getByRole('textbox')).toHaveValue('')
  })
})

describe('MoneyInput - onChange', () => {
  it('saisie "10.00" → onChange appelé avec 1000', () => {
    const onChange = vi.fn()
    render(<MoneyInput value={0} onChange={onChange} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '10.00' } })
    expect(onChange).toHaveBeenCalledWith(1000)
  })

  it('saisie "5,50" (virgule) → onChange appelé avec 550', () => {
    const onChange = vi.fn()
    render(<MoneyInput value={0} onChange={onChange} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '5,50' } })
    expect(onChange).toHaveBeenCalledWith(550)
  })

  it('saisie vide → onChange appelé avec 0', () => {
    const onChange = vi.fn()
    render(<MoneyInput value={1000} onChange={onChange} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '' } })
    expect(onChange).toHaveBeenCalledWith(0)
  })
})

describe('MoneyInput - onBlur', () => {
  it('blur normalise la valeur affichée à 2 décimales', () => {
    render(<MoneyInput value={0} onChange={vi.fn()} />)
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '5' } })
    fireEvent.blur(input)
    expect(input).toHaveValue('5.00')
  })
})
