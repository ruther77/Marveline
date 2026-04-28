/**
 * Tests unitaires pour components/ui/Spinner.tsx
 * Spinner, LoadingOverlay, LoadingDots, Skeleton, SkeletonText
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Spinner, LoadingOverlay, LoadingDots, Skeleton, SkeletonText, SkeletonCard, SkeletonTable } from '../Spinner'

// ─── Spinner ──────────────────────────────────────────────────────────────────

describe('Spinner - rendu de base', () => {
  it('rend avec role="status"', () => {
    render(<Spinner />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('aria-label = "Chargement" par défaut', () => {
    render(<Spinner />)
    expect(screen.getByLabelText('Chargement')).toBeInTheDocument()
  })

  it('aria-label = label personnalisé', () => {
    render(<Spinner label="Envoi en cours" />)
    expect(screen.getByLabelText('Envoi en cours')).toBeInTheDocument()
  })

  it('affiche le texte du label si fourni', () => {
    render(<Spinner label="Patientez" />)
    expect(screen.getByText('Patientez')).toBeInTheDocument()
  })

  it('sans label : pas de texte visible', () => {
    render(<Spinner />)
    expect(screen.queryByText('Chargement')).toBeNull()
  })
})

describe('Spinner - sizes', () => {
  const sizes = ['xs', 'sm', 'md', 'lg', 'xl'] as const

  for (const size of sizes) {
    it(`size ${size} se rend sans erreur`, () => {
      render(<Spinner size={size} />)
      expect(screen.getByRole('status')).toBeInTheDocument()
    })
  }
})

// ─── LoadingOverlay ───────────────────────────────────────────────────────────

describe('LoadingOverlay', () => {
  it('affiche "Chargement..." par défaut', () => {
    render(<LoadingOverlay />)
    expect(screen.getByText('Chargement...')).toBeInTheDocument()
  })

  it('affiche un label personnalisé', () => {
    render(<LoadingOverlay label="Traitement en cours" />)
    expect(screen.getByText('Traitement en cours')).toBeInTheDocument()
  })
})

// ─── LoadingDots ──────────────────────────────────────────────────────────────

describe('LoadingDots', () => {
  it('rend 3 points', () => {
    const { container } = render(<LoadingDots />)
    const dots = container.querySelectorAll('.rounded-full.animate-bounce')
    expect(dots).toHaveLength(3)
  })

  it('applique une className personnalisée', () => {
    const { container } = render(<LoadingDots className="my-dots" />)
    expect(container.querySelector('.my-dots')).not.toBeNull()
  })
})

// ─── Skeleton ─────────────────────────────────────────────────────────────────

describe('Skeleton - rendu de base', () => {
  it('se rend sans erreur', () => {
    const { container } = render(<Skeleton />)
    expect(container.firstChild).not.toBeNull()
  })

  it('applique className personnalisée', () => {
    const { container } = render(<Skeleton className="h-10 w-full" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain('h-10')
  })
})

describe('Skeleton - variants', () => {
  it('variant text = rounded', () => {
    const { container } = render(<Skeleton variant="text" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain('rounded')
  })

  it('variant circular = rounded-full', () => {
    const { container } = render(<Skeleton variant="circular" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain('rounded-full')
  })

  it('variant rectangular = rounded-lg', () => {
    const { container } = render(<Skeleton variant="rectangular" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain('rounded-lg')
  })
})

describe('Skeleton - animation', () => {
  it('animation pulse (défaut)', () => {
    const { container } = render(<Skeleton />)
    const el = container.firstChild as HTMLElement
    expect(el.className).toContain('animate-pulse')
  })

  it('animation none : pas d\'animation', () => {
    const { container } = render(<Skeleton animation="none" />)
    const el = container.firstChild as HTMLElement
    expect(el.className).not.toContain('animate-pulse')
  })
})

// ─── SkeletonText ─────────────────────────────────────────────────────────────

describe('SkeletonText', () => {
  it('affiche 3 lignes par défaut', () => {
    const { container } = render(<SkeletonText />)
    // Chaque skeleton a bg-dark-900
    const items = container.querySelectorAll('.bg-dark-900')
    expect(items.length).toBe(3)
  })

  it('affiche le nombre de lignes spécifié', () => {
    const { container } = render(<SkeletonText lines={5} />)
    const items = container.querySelectorAll('.bg-dark-900')
    expect(items.length).toBe(5)
  })
})

// ─── SkeletonCard + SkeletonTable ─────────────────────────────────────────────

describe('SkeletonCard', () => {
  it('se rend sans erreur', () => {
    const { container } = render(<SkeletonCard />)
    expect(container.firstChild).not.toBeNull()
  })
})

describe('SkeletonTable', () => {
  it('se rend avec rows et cols par défaut', () => {
    const { container } = render(<SkeletonTable />)
    expect(container.firstChild).not.toBeNull()
  })

  it('se rend avec rows=2 cols=3', () => {
    const { container } = render(<SkeletonTable rows={2} cols={3} />)
    // Header row + 2 data rows
    const rows = container.querySelectorAll('.flex.gap-4')
    expect(rows.length).toBe(3)
  })
})
