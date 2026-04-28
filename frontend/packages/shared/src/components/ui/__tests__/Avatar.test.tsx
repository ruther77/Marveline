/**
 * Tests unitaires pour components/ui/Avatar.tsx
 * Avatar (src, name, initiales, icon, status) + AvatarGroup
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Avatar, AvatarGroup } from '../Avatar'

// ─── Avatar - image ───────────────────────────────────────────────────────────

describe('Avatar - avec src', () => {
  it('affiche une image quand src est fourni', () => {
    render(<Avatar src="https://example.com/photo.jpg" alt="Alice" />)
    expect(screen.getByRole('img')).toBeInTheDocument()
    expect(screen.getByRole('img')).toHaveAttribute('src', 'https://example.com/photo.jpg')
  })

  it('alt = nom de la personne si fourni', () => {
    render(<Avatar src="https://example.com/photo.jpg" name="Alice Dupont" />)
    expect(screen.getByRole('img')).toHaveAttribute('alt', 'Alice Dupont')
  })

  it('alt = "Avatar" par défaut si ni alt ni name', () => {
    render(<Avatar src="https://example.com/photo.jpg" />)
    expect(screen.getByRole('img')).toHaveAttribute('alt', 'Avatar')
  })

  it('en cas d\'erreur image : bascule sur les initiales si name', () => {
    render(<Avatar src="broken.jpg" name="Alice Dupont" />)
    fireEvent.error(screen.getByRole('img'))
    // Après erreur, l'image disparaît et les initiales s'affichent
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.getByText('AD')).toBeInTheDocument()
  })
})

// ─── Avatar - initiales ───────────────────────────────────────────────────────

describe('Avatar - initiales', () => {
  it('affiche les initiales quand pas de src', () => {
    render(<Avatar name="Alice Dupont" />)
    expect(screen.getByText('AD')).toBeInTheDocument()
  })

  it('initiales = 2 premières lettres des mots', () => {
    render(<Avatar name="Jean-Marie Martin" />)
    expect(screen.getByText('JM')).toBeInTheDocument()
  })

  it('initiales en majuscules', () => {
    render(<Avatar name="alice dupont" />)
    expect(screen.getByText('AD')).toBeInTheDocument()
  })

  it('une seule initiale si un seul mot', () => {
    render(<Avatar name="Alice" />)
    expect(screen.getByText('A')).toBeInTheDocument()
  })
})

// ─── Avatar - icône par défaut ────────────────────────────────────────────────

describe('Avatar - icône par défaut', () => {
  it('sans src ni name : rend un svg (icône User)', () => {
    const { container } = render(<Avatar />)
    expect(container.querySelector('svg')).not.toBeNull()
  })
})

// ─── Avatar - sizes ───────────────────────────────────────────────────────────

describe('Avatar - sizes', () => {
  const sizes = ['xs', 'sm', 'md', 'lg', 'xl', '2xl'] as const

  for (const size of sizes) {
    it(`size ${size} se rend sans erreur`, () => {
      const { container } = render(<Avatar name="Test User" size={size} />)
      expect(container.firstChild).not.toBeNull()
    })
  }
})

// ─── Avatar - status ──────────────────────────────────────────────────────────

describe('Avatar - status', () => {
  it('sans status : pas d\'indicateur de statut', () => {
    const { container } = render(<Avatar name="Alice" />)
    // Le wrapper interne ne doit pas avoir de span de statut
    const spans = container.querySelectorAll('span')
    // La seule span est celle du texte des initiales
    const statusSpan = Array.from(spans).find(s => s.className.includes('absolute bottom'))
    expect(statusSpan).toBeUndefined()
  })

  const statuses = ['online', 'offline', 'busy', 'away'] as const

  for (const status of statuses) {
    it(`status ${status} rend un indicateur`, () => {
      const { container } = render(<Avatar name="Alice" status={status} />)
      // Un span absolu est rendu pour le statut
      const statusSpan = container.querySelector('span.absolute')
      expect(statusSpan).not.toBeNull()
    })
  }
})

// ─── Avatar - className ───────────────────────────────────────────────────────

describe('Avatar - className', () => {
  it('applique une className personnalisée sur le cercle interne', () => {
    const { container } = render(<Avatar name="Alice" className="border-4" />)
    const inner = container.querySelector('.border-4')
    expect(inner).not.toBeNull()
  })
})

// ─── AvatarGroup ──────────────────────────────────────────────────────────────

describe('AvatarGroup - rendu de base', () => {
  const avatars = [
    { name: 'Alice Dupont' },
    { name: 'Bob Martin' },
    { name: 'Claire Petit' },
  ]

  it('affiche les avatars jusqu\'à max', () => {
    render(<AvatarGroup avatars={avatars} max={2} />)
    expect(screen.getByText('AD')).toBeInTheDocument()
    expect(screen.getByText('BM')).toBeInTheDocument()
    // Claire n'est pas visible (max=2)
    expect(screen.queryByText('CP')).toBeNull()
  })

  it('affiche le compteur "+N" pour les avatars restants', () => {
    render(<AvatarGroup avatars={avatars} max={2} />)
    expect(screen.getByText('+1')).toBeInTheDocument()
  })

  it('sans dépassement : pas de compteur', () => {
    render(<AvatarGroup avatars={avatars} max={10} />)
    expect(screen.queryByText(/^\+/)).toBeNull()
  })

  it('max par défaut = 4', () => {
    const many = Array.from({ length: 6 }, (_, i) => ({ name: `User ${i}` }))
    render(<AvatarGroup avatars={many} />)
    expect(screen.getByText('+2')).toBeInTheDocument()
  })
})
