/**
 * Tests unitaires pour components/ui/Card.tsx
 * Card, CardHeader, CardTitle, CardContent, CardFooter, StatCard
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Card, CardHeader, CardTitle, CardContent, CardFooter, StatCard } from '../Card'

// ─── Card ─────────────────────────────────────────────────────────────────────

describe('Card - rendu de base', () => {
  it('affiche le contenu enfant', () => {
    render(<Card>Contenu</Card>)
    expect(screen.getByText('Contenu')).toBeInTheDocument()
  })

  it('applique className personnalisée', () => {
    const { container } = render(<Card className="my-card">X</Card>)
    expect(container.querySelector('.my-card')).not.toBeNull()
  })
})

describe('Card - padding', () => {
  const paddings = ['none', 'sm', 'md', 'lg'] as const

  for (const pad of paddings) {
    it(`padding ${pad} se rend sans erreur`, () => {
      render(<Card padding={pad}>Test</Card>)
      expect(screen.getByText('Test')).toBeInTheDocument()
    })
  }
})

describe('Card - onClick', () => {
  it('appelle onClick quand cliqué', () => {
    const onClick = vi.fn()
    render(<Card onClick={onClick}>Clic</Card>)
    fireEvent.click(screen.getByText('Clic'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('sans onClick : pas d\'erreur au clic', () => {
    render(<Card>Test</Card>)
    expect(() => fireEvent.click(screen.getByText('Test'))).not.toThrow()
  })
})

// ─── CardHeader ───────────────────────────────────────────────────────────────

describe('CardHeader', () => {
  it('affiche le contenu', () => {
    render(<CardHeader>Titre section</CardHeader>)
    expect(screen.getByText('Titre section')).toBeInTheDocument()
  })

  it('affiche l\'action si fournie', () => {
    render(
      <CardHeader action={<button>Action</button>}>Titre</CardHeader>
    )
    expect(screen.getByText('Action')).toBeInTheDocument()
  })

  it('sans action : pas d\'éléments supplémentaires', () => {
    render(<CardHeader>Titre</CardHeader>)
    expect(screen.queryByRole('button')).toBeNull()
  })
})

// ─── CardTitle ────────────────────────────────────────────────────────────────

describe('CardTitle', () => {
  it('affiche le titre dans un h3', () => {
    render(<CardTitle>Mon titre</CardTitle>)
    expect(screen.getByRole('heading', { level: 3, name: 'Mon titre' })).toBeInTheDocument()
  })

  it('affiche le subtitle si fourni', () => {
    render(<CardTitle subtitle="Sous-titre">Titre</CardTitle>)
    expect(screen.getByText('Sous-titre')).toBeInTheDocument()
  })

  it('sans subtitle : pas de paragraphe supplémentaire', () => {
    render(<CardTitle>Titre</CardTitle>)
    expect(screen.queryByText('Sous-titre')).toBeNull()
  })
})

// ─── CardContent ──────────────────────────────────────────────────────────────

describe('CardContent', () => {
  it('affiche le contenu', () => {
    render(<CardContent>Contenu de la carte</CardContent>)
    expect(screen.getByText('Contenu de la carte')).toBeInTheDocument()
  })
})

// ─── CardFooter ───────────────────────────────────────────────────────────────

describe('CardFooter', () => {
  it('affiche le contenu du pied de page', () => {
    render(<CardFooter>Footer</CardFooter>)
    expect(screen.getByText('Footer')).toBeInTheDocument()
  })
})

// ─── StatCard ─────────────────────────────────────────────────────────────────

describe('StatCard - rendu de base', () => {
  it('affiche le titre et la valeur', () => {
    render(<StatCard title="Revenus" value="12 500 €" />)
    expect(screen.getByText('Revenus')).toBeInTheDocument()
    expect(screen.getByText('12 500 €')).toBeInTheDocument()
  })

  it('affiche la valeur numérique', () => {
    render(<StatCard title="Commandes" value={42} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })
})

describe('StatCard - change', () => {
  it('affiche le changement positif avec "+"', () => {
    render(<StatCard title="Test" value="100" change={{ value: 12 }} />)
    expect(screen.getByText(/\+12%/)).toBeInTheDocument()
  })

  it('affiche le changement négatif sans "+"', () => {
    render(<StatCard title="Test" value="100" change={{ value: -5 }} />)
    expect(screen.getByText(/-5%/)).toBeInTheDocument()
  })

  it('affiche le label du changement si fourni', () => {
    render(<StatCard title="Test" value="100" change={{ value: 5, label: 'vs mois dernier' }} />)
    expect(screen.getByText('vs mois dernier')).toBeInTheDocument()
  })

  it('sans change : pas de pourcentage', () => {
    render(<StatCard title="Test" value="100" />)
    expect(screen.queryByText(/%/)).toBeNull()
  })
})

describe('StatCard - icon', () => {
  it('affiche l\'icône si fournie', () => {
    render(<StatCard title="Test" value="1" icon={<span data-testid="ico">★</span>} />)
    expect(screen.getByTestId('ico')).toBeInTheDocument()
  })

  it('sans icon : pas d\'élément icon', () => {
    render(<StatCard title="Test" value="1" />)
    expect(screen.queryByTestId('ico')).toBeNull()
  })
})

describe('StatCard - onClick', () => {
  it('appelle onClick quand cliqué', () => {
    const onClick = vi.fn()
    render(<StatCard title="Test" value="1" onClick={onClick} />)
    fireEvent.click(screen.getByText('Test'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})
