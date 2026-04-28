/**
 * Tests unitaires pour components/ui/StockIndicator.tsx
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StockIndicator } from '../StockIndicator'

describe('StockIndicator - labels de niveau', () => {
  it('stock <= min → "Rupture"', () => {
    render(<StockIndicator current={2} min={2} />)
    expect(screen.getByText(/Rupture/)).toBeInTheDocument()
  })

  it('stock <= min*2 → "Faible"', () => {
    render(<StockIndicator current={3} min={2} />)
    expect(screen.getByText(/Faible/)).toBeInTheDocument()
  })

  it('stock > min*2 → "OK"', () => {
    render(<StockIndicator current={10} min={2} />)
    expect(screen.getByText(/OK/)).toBeInTheDocument()
  })
})

describe('StockIndicator - affichage valeur', () => {
  it('affiche la quantité courante', () => {
    render(<StockIndicator current={7} min={2} />)
    expect(screen.getByText(/7/)).toBeInTheDocument()
  })

  it('affiche l\'unité si fournie', () => {
    render(<StockIndicator current={5} min={1} unit="pcs" />)
    expect(screen.getByText(/5 pcs/)).toBeInTheDocument()
  })

  it('sans unité : pas de suffixe', () => {
    render(<StockIndicator current={5} min={1} />)
    const text = screen.getByText(/5/)
    expect(text.textContent).not.toMatch(/5 \w/)
  })
})

describe('StockIndicator - barre de progression', () => {
  it('barre présente si max fourni', () => {
    const { container } = render(<StockIndicator current={5} min={1} max={10} />)
    expect(container.querySelector('.h-1\\.5')).not.toBeNull()
  })

  it('barre absente si max absent', () => {
    const { container } = render(<StockIndicator current={5} min={1} />)
    expect(container.querySelector('.h-1\\.5')).toBeNull()
  })
})
