/**
 * Tests unitaires pour components/ui/SwipeActions.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SwipeActions } from '../SwipeActions'

const rightActions = [
  { icon: <span>✏️</span>, label: 'Modifier',   color: 'bg-blue-600', onClick: vi.fn() },
]
const leftActions = [
  { icon: <span>🗑</span>, label: 'Supprimer', color: 'bg-red-600',  onClick: vi.fn() },
]

// ── Rendu de base ─────────────────────────────────────────────────────────────

describe('SwipeActions - rendu de base', () => {
  it('affiche les children', () => {
    render(
      <SwipeActions actions={rightActions}>
        <div>Contenu principal</div>
      </SwipeActions>
    )
    expect(screen.getByText('Contenu principal')).toBeInTheDocument()
  })

  it('affiche les boutons d\'action (prop actions rétrocompat)', () => {
    render(
      <SwipeActions actions={rightActions}>
        <div>Item</div>
      </SwipeActions>
    )
    expect(screen.getByRole('button', { name: 'Modifier' })).toBeInTheDocument()
  })

  it('affiche les rightActions', () => {
    render(
      <SwipeActions rightActions={rightActions}>
        <div>Item</div>
      </SwipeActions>
    )
    expect(screen.getByRole('button', { name: 'Modifier' })).toBeInTheDocument()
  })

  it('affiche les leftActions', () => {
    render(
      <SwipeActions leftActions={leftActions}>
        <div>Item</div>
      </SwipeActions>
    )
    expect(screen.getByRole('button', { name: 'Supprimer' })).toBeInTheDocument()
  })

  it('affiche rightActions et leftActions simultanément', () => {
    render(
      <SwipeActions rightActions={rightActions} leftActions={leftActions}>
        <div>Item</div>
      </SwipeActions>
    )
    expect(screen.getByRole('button', { name: 'Modifier' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Supprimer' })).toBeInTheDocument()
  })
})

// ── Clic sur actions ──────────────────────────────────────────────────────────

describe('SwipeActions - clic sur actions', () => {
  it('clic sur rightAction appelle onClick', () => {
    const onClick = vi.fn()
    render(
      <SwipeActions rightActions={[{ icon: <span>X</span>, label: 'Action', color: 'bg-red-600', onClick }]}>
        <div>Item</div>
      </SwipeActions>
    )
    fireEvent.click(screen.getByRole('button', { name: 'Action' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('clic sur leftAction appelle onClick', () => {
    const onClick = vi.fn()
    render(
      <SwipeActions leftActions={[{ icon: <span>X</span>, label: 'Gauche', color: 'bg-blue-600', onClick }]}>
        <div>Item</div>
      </SwipeActions>
    )
    fireEvent.click(screen.getByRole('button', { name: 'Gauche' }))
    expect(onClick).toHaveBeenCalledOnce()
  })
})

// ── Rétrocompatibilité prop actions ──────────────────────────────────────────

describe('SwipeActions - rétrocompatibilité', () => {
  it('prop actions seule fonctionne sans rightActions ni leftActions', () => {
    const onClick = vi.fn()
    render(
      <SwipeActions actions={[{ icon: <span>A</span>, label: 'Legacy', color: 'bg-dark-600', onClick }]}>
        <div>Item</div>
      </SwipeActions>
    )
    fireEvent.click(screen.getByRole('button', { name: 'Legacy' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('rightActions prend la priorité sur actions si les deux sont fournies', () => {
    const onRight = vi.fn()
    const onLegacy = vi.fn()
    render(
      <SwipeActions
        actions={[{ icon: <span>A</span>, label: 'Legacy', color: 'bg-dark-600', onClick: onLegacy }]}
        rightActions={[{ icon: <span>R</span>, label: 'Right', color: 'bg-blue-600', onClick: onRight }]}
      >
        <div>Item</div>
      </SwipeActions>
    )
    // rightActions prend la priorité → seul 'Right' visible
    expect(screen.getByRole('button', { name: 'Right' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Legacy' })).not.toBeInTheDocument()
  })
})
