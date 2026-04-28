/**
 * Tests unitaires pour components/ui/EmptyState.tsx
 * EmptyState, NoData, NoSearchResults, ErrorState
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EmptyState, NoData, NoSearchResults, ErrorState } from '../EmptyState'

// ─── EmptyState ───────────────────────────────────────────────────────────────

describe('EmptyState - rendu de base', () => {
  it('affiche le titre', () => {
    render(<EmptyState title="Aucun élément" />)
    expect(screen.getByText('Aucun élément')).toBeInTheDocument()
  })

  it('affiche la description si fournie', () => {
    render(<EmptyState title="Titre" description="Description ici" />)
    expect(screen.getByText('Description ici')).toBeInTheDocument()
  })

  it('sans description : pas de paragraphe desc', () => {
    render(<EmptyState title="Titre" />)
    expect(screen.queryByText('Description ici')).toBeNull()
  })

  it('applique className personnalisée', () => {
    const { container } = render(<EmptyState title="Titre" className="my-empty" />)
    expect(container.querySelector('.my-empty')).not.toBeNull()
  })
})

describe('EmptyState - types', () => {
  const types = ['empty', 'search', 'error', 'no-results', 'custom'] as const

  for (const type of types) {
    it(`type ${type} se rend sans erreur`, () => {
      render(<EmptyState title={`Type ${type}`} type={type} />)
      expect(screen.getByText(`Type ${type}`)).toBeInTheDocument()
    })
  }
})

describe('EmptyState - icon personnalisée', () => {
  it('affiche l\'icon personnalisée', () => {
    render(<EmptyState title="Titre" icon={<span data-testid="custom">★</span>} />)
    expect(screen.getByTestId('custom')).toBeInTheDocument()
  })
})

describe('EmptyState - action', () => {
  it('affiche le bouton d\'action', () => {
    render(<EmptyState title="Titre" action={{ label: 'Ajouter', onClick: vi.fn() }} />)
    expect(screen.getByText('Ajouter')).toBeInTheDocument()
  })

  it('clic sur action appelle onClick', () => {
    const onClick = vi.fn()
    render(<EmptyState title="Titre" action={{ label: 'Clic', onClick }} />)
    fireEvent.click(screen.getByText('Clic'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('sans action : pas de bouton', () => {
    render(<EmptyState title="Titre" />)
    expect(screen.queryByRole('button')).toBeNull()
  })
})

describe('EmptyState - secondaryAction', () => {
  it('affiche le bouton secondaire', () => {
    render(
      <EmptyState
        title="Titre"
        action={{ label: 'Principal', onClick: vi.fn() }}
        secondaryAction={{ label: 'Annuler', onClick: vi.fn() }}
      />
    )
    expect(screen.getByText('Annuler')).toBeInTheDocument()
  })

  it('clic secondaryAction appelle son onClick', () => {
    const onClick = vi.fn()
    render(
      <EmptyState
        title="Titre"
        action={{ label: 'P', onClick: vi.fn() }}
        secondaryAction={{ label: 'S', onClick }}
      />
    )
    fireEvent.click(screen.getByText('S'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})

describe('EmptyState - sizes', () => {
  const sizes = ['sm', 'md', 'lg'] as const

  for (const size of sizes) {
    it(`size ${size} se rend sans erreur`, () => {
      render(<EmptyState title="Titre" size={size} />)
      expect(screen.getByText('Titre')).toBeInTheDocument()
    })
  }
})

// ─── NoData ───────────────────────────────────────────────────────────────────

describe('NoData', () => {
  it('affiche "Aucune donnée"', () => {
    render(<NoData />)
    expect(screen.getByText('Aucune donnée')).toBeInTheDocument()
  })

  it('affiche le bouton Ajouter si onAction est fourni', () => {
    render(<NoData onAction={vi.fn()} />)
    expect(screen.getByText('Ajouter')).toBeInTheDocument()
  })

  it('actionLabel personnalisé', () => {
    render(<NoData onAction={vi.fn()} actionLabel="Créer" />)
    expect(screen.getByText('Créer')).toBeInTheDocument()
  })

  it('sans onAction : pas de bouton', () => {
    render(<NoData />)
    expect(screen.queryByRole('button')).toBeNull()
  })
})

// ─── NoSearchResults ──────────────────────────────────────────────────────────

describe('NoSearchResults', () => {
  it('affiche "Aucun résultat"', () => {
    render(<NoSearchResults />)
    expect(screen.getByText('Aucun résultat')).toBeInTheDocument()
  })

  it('inclut le terme de recherche dans la description', () => {
    render(<NoSearchResults searchTerm="paris" />)
    expect(screen.getByText(/paris/)).toBeInTheDocument()
  })

  it('affiche le bouton Effacer si onClear est fourni', () => {
    render(<NoSearchResults onClear={vi.fn()} />)
    expect(screen.getByText('Effacer la recherche')).toBeInTheDocument()
  })
})

// ─── ErrorState ───────────────────────────────────────────────────────────────

describe('ErrorState', () => {
  it('affiche "Une erreur est survenue"', () => {
    render(<ErrorState />)
    expect(screen.getByText('Une erreur est survenue')).toBeInTheDocument()
  })

  it('affiche le bouton Réessayer si onRetry est fourni', () => {
    const onRetry = vi.fn()
    render(<ErrorState onRetry={onRetry} />)
    expect(screen.getByText('Réessayer')).toBeInTheDocument()
  })

  it('clic sur Réessayer appelle onRetry', () => {
    const onRetry = vi.fn()
    render(<ErrorState onRetry={onRetry} />)
    fireEvent.click(screen.getByText('Réessayer'))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
