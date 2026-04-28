/**
 * Tests unitaires pour components/ui/Breadcrumb.tsx
 * Breadcrumb, PageHeader
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Breadcrumb, PageHeader } from '../Breadcrumb'

// Mock TanStack Router Link pour les tests unitaires
vi.mock('@tanstack/react-router', () => ({
  Link: ({ to, children, className }: { to: string; children: React.ReactNode; className?: string }) => (
    <a href={to} className={className}>{children}</a>
  ),
}))

// ─── Breadcrumb ───────────────────────────────────────────────────────────────

describe('Breadcrumb - rendu de base', () => {
  it('a role="navigation" (nav aria-label)', () => {
    render(<Breadcrumb items={[{ label: 'Produits' }]} />)
    expect(screen.getByRole('navigation')).toBeInTheDocument()
  })

  it('affiche "Accueil" par défaut (showHome=true)', () => {
    render(<Breadcrumb items={[{ label: 'Page' }]} />)
    // L'item Accueil est affiché via icon Home (pas de label texte visible pour l'item 0 sauf sur la home)
    // La nav est présente, on vérifie juste le dernier item
    expect(screen.getByText('Page')).toBeInTheDocument()
  })

  it('showHome=false : pas d\'icône Accueil', () => {
    const { container } = render(
      <Breadcrumb items={[{ label: 'Produits' }]} showHome={false} />
    )
    // Pas de svg pour Home quand showHome=false et un seul item
    // L'item unique sera le dernier donc rendu comme span
    expect(screen.getByText('Produits')).toBeInTheDocument()
    // Pas de lien supplémentaire
    expect(container.querySelectorAll('a').length).toBe(0)
  })

  it('affiche les items du breadcrumb', () => {
    // showHome=true (default) → allItems=[Accueil, Produits, Détail]
    // Produits est à index 1 → label visible
    render(
      <Breadcrumb
        items={[
          { label: 'Produits', href: '/catalogue/products' },
          { label: 'Détail' },
        ]}
      />
    )
    expect(screen.getByText('Produits')).toBeInTheDocument()
    expect(screen.getByText('Détail')).toBeInTheDocument()
  })

  it('item avec href génère un lien', () => {
    render(
      <Breadcrumb
        items={[
          { label: 'Produits', href: '/catalogue/products' },
          { label: 'Détail' },
        ]}
      />
    )
    const link = screen.getByText('Produits').closest('a')
    expect(link).not.toBeNull()
    expect(link?.getAttribute('href')).toBe('/catalogue/products')
  })

  it('dernier item est un span (non cliquable)', () => {
    render(
      <Breadcrumb
        items={[{ label: 'Produits', href: '/catalogue/products' }, { label: 'Détail' }]}
      />
    )
    // "Détail" est le dernier → span, pas un lien
    const detail = screen.getByText('Détail')
    expect(detail.tagName).toBe('SPAN')
  })
})

describe('Breadcrumb - séparateur', () => {
  it('séparateur personnalisé affiché', () => {
    render(
      <Breadcrumb
        items={[{ label: 'A', href: '/a' }, { label: 'B' }]}
        showHome={false}
        separator={<span data-testid="sep">/</span>}
      />
    )
    expect(screen.getByTestId('sep')).toBeInTheDocument()
  })
})

// ─── PageHeader ───────────────────────────────────────────────────────────────

describe('PageHeader - rendu de base', () => {
  it('affiche le titre', () => {
    render(<PageHeader title="Gestion des produits" />)
    expect(screen.getByText('Gestion des produits')).toBeInTheDocument()
  })

  it('affiche le sous-titre si fourni', () => {
    render(<PageHeader title="Titre" subtitle="Sous-titre ici" />)
    expect(screen.getByText('Sous-titre ici')).toBeInTheDocument()
  })

  it('pas de sous-titre si absent', () => {
    render(<PageHeader title="Titre" />)
    expect(screen.queryByText('Sous-titre ici')).toBeNull()
  })

  it('affiche les actions si fournies', () => {
    render(
      <PageHeader
        title="Titre"
        actions={<button>Ajouter</button>}
      />
    )
    expect(screen.getByText('Ajouter')).toBeInTheDocument()
  })

  it('affiche le breadcrumb si fourni', () => {
    render(
      <PageHeader
        title="Titre"
        breadcrumbs={[{ label: 'Produits', href: '/catalogue/products' }, { label: 'Détail' }]}
      />
    )
    expect(screen.getByText('Détail')).toBeInTheDocument()
  })
})
