/**
 * Tests unitaires pour components/ui/Badge.tsx
 * Badge (variants, sizes, dot, removable) + StatusBadge
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Badge, StatusBadge } from '../Badge'

// ─── Badge ────────────────────────────────────────────────────────────────────

describe('Badge - rendu de base', () => {
  it('affiche le texte enfant', () => {
    render(<Badge>Actif</Badge>)
    expect(screen.getByText('Actif')).toBeInTheDocument()
  })

  it('est un span inline', () => {
    render(<Badge>Test</Badge>)
    const el = screen.getByText('Test')
    expect(el.tagName.toLowerCase()).toBe('span')
  })

  it('applique une className personnalisée', () => {
    render(<Badge className="custom-cls">X</Badge>)
    expect(screen.getByText('X').className).toContain('custom-cls')
  })
})

describe('Badge - variants', () => {
  const variants = ['default', 'primary', 'success', 'warning', 'danger', 'info'] as const

  for (const variant of variants) {
    it(`variant ${variant} se rend sans erreur`, () => {
      render(<Badge variant={variant}>{variant}</Badge>)
      expect(screen.getByText(variant)).toBeInTheDocument()
    })
  }
})

describe('Badge - sizes', () => {
  const sizes = ['sm', 'md', 'lg'] as const

  for (const size of sizes) {
    it(`size ${size} se rend sans erreur`, () => {
      render(<Badge size={size}>{size}</Badge>)
      expect(screen.getByText(size)).toBeInTheDocument()
    })
  }
})

describe('Badge - dot', () => {
  it('sans dot : pas de point coloré', () => {
    const { container } = render(<Badge>Test</Badge>)
    // Le span du dot n'est pas rendu
    const spans = container.querySelectorAll('span > span')
    expect(spans).toHaveLength(0)
  })

  it('avec dot=true : rend un span supplémentaire', () => {
    const { container } = render(<Badge dot>Test</Badge>)
    const inner = container.querySelector('span > span')
    expect(inner).not.toBeNull()
  })
})

describe('Badge - removable', () => {
  it('sans removable : pas de bouton Supprimer', () => {
    render(<Badge>Test</Badge>)
    expect(screen.queryByLabelText('Supprimer')).toBeNull()
  })

  it('avec removable=true : affiche bouton Supprimer', () => {
    render(<Badge removable>Test</Badge>)
    expect(screen.getByLabelText('Supprimer')).toBeInTheDocument()
  })

  it('clic sur Supprimer appelle onRemove', () => {
    const onRemove = vi.fn()
    render(<Badge removable onRemove={onRemove}>Test</Badge>)
    fireEvent.click(screen.getByLabelText('Supprimer'))
    expect(onRemove).toHaveBeenCalledTimes(1)
  })

  it('sans onRemove : clic ne plante pas', () => {
    render(<Badge removable>Test</Badge>)
    expect(() => fireEvent.click(screen.getByLabelText('Supprimer'))).not.toThrow()
  })
})

// ─── StatusBadge ──────────────────────────────────────────────────────────────

describe('StatusBadge - labels par défaut', () => {
  it('active → "Actif"', () => {
    render(<StatusBadge status="active" />)
    expect(screen.getByText('Actif')).toBeInTheDocument()
  })

  it('inactive → "Inactif"', () => {
    render(<StatusBadge status="inactive" />)
    expect(screen.getByText('Inactif')).toBeInTheDocument()
  })

  it('pending → "En attente"', () => {
    render(<StatusBadge status="pending" />)
    expect(screen.getByText('En attente')).toBeInTheDocument()
  })

  it('completed → "Terminé"', () => {
    render(<StatusBadge status="completed" />)
    expect(screen.getByText('Terminé')).toBeInTheDocument()
  })

  it('cancelled → "Annulé"', () => {
    render(<StatusBadge status="cancelled" />)
    expect(screen.getByText('Annulé')).toBeInTheDocument()
  })

  it('error → "Erreur"', () => {
    render(<StatusBadge status="error" />)
    expect(screen.getByText('Erreur')).toBeInTheDocument()
  })
})

describe('StatusBadge - customLabel', () => {
  it('customLabel remplace le label par défaut', () => {
    render(<StatusBadge status="active" customLabel="En service" />)
    expect(screen.getByText('En service')).toBeInTheDocument()
    expect(screen.queryByText('Actif')).toBeNull()
  })
})

describe('StatusBadge - dot par défaut = true', () => {
  it('rend un point par défaut', () => {
    const { container } = render(<StatusBadge status="active" />)
    const inner = container.querySelector('span > span')
    expect(inner).not.toBeNull()
  })

  it('dot=false ne rend pas de point', () => {
    const { container } = render(<StatusBadge status="active" dot={false} />)
    const inner = container.querySelector('span > span')
    expect(inner).toBeNull()
  })
})
