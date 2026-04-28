/**
 * Tests unitaires pour components/ui/DomainStatusBadge.tsx
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DomainStatusBadge } from '../DomainStatusBadge'

describe('DomainStatusBadge - statuts connus', () => {
  it('draft → "Brouillon"', () => {
    render(<DomainStatusBadge status="draft" />)
    expect(screen.getByText('Brouillon')).toBeInTheDocument()
  })

  it('confirmed → "Confirmé"', () => {
    render(<DomainStatusBadge status="confirmed" />)
    expect(screen.getByText('Confirmé')).toBeInTheDocument()
  })

  it('cancelled → "Annulé"', () => {
    render(<DomainStatusBadge status="cancelled" />)
    expect(screen.getByText('Annulé')).toBeInTheDocument()
  })

  it('sent → "Envoyé"', () => {
    render(<DomainStatusBadge status="sent" />)
    expect(screen.getByText('Envoyé')).toBeInTheDocument()
  })

  it('completed → "Terminé"', () => {
    render(<DomainStatusBadge status="completed" />)
    expect(screen.getByText('Terminé')).toBeInTheDocument()
  })

  it('pending → "En attente"', () => {
    render(<DomainStatusBadge status="pending" />)
    expect(screen.getByText('En attente')).toBeInTheDocument()
  })

  it('fully_paid → "Payé"', () => {
    render(<DomainStatusBadge status="fully_paid" />)
    expect(screen.getByText('Payé')).toBeInTheDocument()
  })
})

describe('DomainStatusBadge - statut inconnu', () => {
  it('statut inconnu → affiche la valeur brute', () => {
    render(<DomainStatusBadge status="custom_status" />)
    expect(screen.getByText('custom_status')).toBeInTheDocument()
  })
})

describe('DomainStatusBadge - sizes', () => {
  it('size=sm (défaut) → classes px-2', () => {
    const { container } = render(<DomainStatusBadge status="draft" size="sm" />)
    expect(container.querySelector('.px-2')).not.toBeNull()
  })

  it('size=md → classes px-2.5', () => {
    const { container } = render(<DomainStatusBadge status="draft" size="md" />)
    expect(container.querySelector('.px-2\\.5')).not.toBeNull()
  })
})

describe('DomainStatusBadge - className', () => {
  it('applique className personnalisé', () => {
    const { container } = render(<DomainStatusBadge status="draft" className="custom-cls" />)
    expect(container.querySelector('.custom-cls')).not.toBeNull()
  })
})
