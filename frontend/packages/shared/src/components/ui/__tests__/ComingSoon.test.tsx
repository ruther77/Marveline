/**
 * Tests unitaires pour components/ui/ComingSoon.tsx
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ComingSoon from '../ComingSoon'

describe('ComingSoon - rendu de base', () => {
  it('affiche le titre', () => {
    render(<ComingSoon title="Statistiques avancées" />)
    expect(screen.getByText('Statistiques avancées')).toBeInTheDocument()
  })

  it('affiche la description si fournie', () => {
    render(<ComingSoon title="Titre" description="Disponible en mars 2026" />)
    expect(screen.getByText('Disponible en mars 2026')).toBeInTheDocument()
  })

  it('pas de description si absente', () => {
    render(<ComingSoon title="Titre" />)
    expect(screen.queryByText('Disponible en mars 2026')).toBeNull()
  })

  it('affiche le message générique "prochainement"', () => {
    render(<ComingSoon title="Titre" />)
    expect(screen.getByText(/prochainement/i)).toBeInTheDocument()
  })

  it('titre en h1', () => {
    render(<ComingSoon title="Mon Module" />)
    const h1 = screen.getByRole('heading', { level: 1 })
    expect(h1).toHaveTextContent('Mon Module')
  })
})
