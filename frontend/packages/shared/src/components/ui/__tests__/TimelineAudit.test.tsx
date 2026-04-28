/**
 * Tests unitaires pour components/ui/TimelineAudit.tsx
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TimelineAudit } from '../TimelineAudit'
import type { TimelineEntry } from '../TimelineAudit'

const entries: TimelineEntry[] = [
  {
    date: '2026-01-15T10:00:00Z',
    user: 'Alice',
    action: 'Réservation confirmée',
    type: 'state',
  },
  {
    date: '2026-01-16T14:30:00Z',
    user: 'Bob',
    action: 'Paiement reçu',
    detail: 'Virement bancaire 500€',
    type: 'action',
  },
  {
    date: '2026-01-17T09:00:00Z',
    user: 'Carol',
    action: 'Note ajoutée',
    detail: 'Client difficile',
    type: 'note',
  },
]

describe('TimelineAudit - rendu de base', () => {
  it('affiche les actions', () => {
    render(<TimelineAudit entries={entries} />)
    expect(screen.getByText('Réservation confirmée')).toBeInTheDocument()
    expect(screen.getByText('Paiement reçu')).toBeInTheDocument()
    expect(screen.getByText('Note ajoutée')).toBeInTheDocument()
  })

  it('affiche les auteurs', () => {
    render(<TimelineAudit entries={entries} />)
    expect(screen.getByText('par Alice')).toBeInTheDocument()
    expect(screen.getByText('par Bob')).toBeInTheDocument()
    expect(screen.getByText('par Carol')).toBeInTheDocument()
  })

  it('affiche les détails si fournis', () => {
    render(<TimelineAudit entries={entries} />)
    expect(screen.getByText('Virement bancaire 500€')).toBeInTheDocument()
    expect(screen.getByText('Client difficile')).toBeInTheDocument()
  })

  it('pas de détail pour les entrées sans detail', () => {
    render(<TimelineAudit entries={[entries[0]]} />)
    expect(screen.queryByText('Virement bancaire 500€')).toBeNull()
  })
})

describe('TimelineAudit - liste vide', () => {
  it('affiche "Aucun historique disponible" si entries=[]', () => {
    render(<TimelineAudit entries={[]} />)
    expect(screen.getByText('Aucun historique disponible')).toBeInTheDocument()
  })
})

describe('TimelineAudit - tri chronologique', () => {
  it('entrées triées du plus récent au plus ancien', () => {
    render(<TimelineAudit entries={entries} />)
    const texts = screen.getAllByText(/par /)
    // Ordre attendu : Carol (17 jan), Bob (16 jan), Alice (15 jan)
    expect(texts[0]).toHaveTextContent('par Carol')
    expect(texts[1]).toHaveTextContent('par Bob')
    expect(texts[2]).toHaveTextContent('par Alice')
  })
})
