/**
 * Tests unitaires pour components/ui/FilterBar.tsx
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FilterBar } from '../FilterBar'

describe('FilterBar - rendu de base', () => {
  it('rend sans chips ni children', () => {
    const { container } = render(<FilterBar />)
    expect(container.firstChild).not.toBeNull()
  })

  it('affiche les children', () => {
    render(<FilterBar><button>Filtrer</button></FilterBar>)
    expect(screen.getByText('Filtrer')).toBeInTheDocument()
  })
})

describe('FilterBar - chips', () => {
  const chips = [
    { key: 'status', label: 'Statut', value: 'Actif', onRemove: vi.fn() },
    { key: 'cat', label: 'Catégorie', value: 'Audio', onRemove: vi.fn() },
  ]

  it('affiche les valeurs des chips', () => {
    render(<FilterBar chips={chips} />)
    expect(screen.getByText('Actif')).toBeInTheDocument()
    expect(screen.getByText('Audio')).toBeInTheDocument()
  })

  it('affiche les labels des chips', () => {
    render(<FilterBar chips={chips} />)
    expect(screen.getByText('Statut:')).toBeInTheDocument()
    expect(screen.getByText('Catégorie:')).toBeInTheDocument()
  })

  it('bouton supprimer pour chaque chip', () => {
    render(<FilterBar chips={chips} />)
    const btns = screen.getAllByRole('button', { name: /supprimer filtre/i })
    expect(btns).toHaveLength(2)
  })

  it('clic sur supprimer appelle onRemove du chip', () => {
    const onRemove = vi.fn()
    render(<FilterBar chips={[{ key: 'x', label: 'X', value: 'Y', onRemove }]} />)
    fireEvent.click(screen.getByRole('button', { name: /supprimer filtre/i }))
    expect(onRemove).toHaveBeenCalledOnce()
  })
})

describe('FilterBar - Effacer tout', () => {
  it('bouton "Effacer tout" visible si chips > 0 et onClearAll fourni', () => {
    render(
      <FilterBar
        chips={[{ key: 'a', label: 'A', value: 'B', onRemove: vi.fn() }]}
        onClearAll={vi.fn()}
      />
    )
    expect(screen.getByText('Effacer tout')).toBeInTheDocument()
  })

  it('"Effacer tout" absent si chips=[]', () => {
    render(<FilterBar chips={[]} onClearAll={vi.fn()} />)
    expect(screen.queryByText('Effacer tout')).toBeNull()
  })

  it('"Effacer tout" absent si onClearAll absent', () => {
    render(
      <FilterBar chips={[{ key: 'a', label: 'A', value: 'B', onRemove: vi.fn() }]} />
    )
    expect(screen.queryByText('Effacer tout')).toBeNull()
  })

  it('clic "Effacer tout" appelle onClearAll', () => {
    const onClearAll = vi.fn()
    render(
      <FilterBar
        chips={[{ key: 'a', label: 'A', value: 'B', onRemove: vi.fn() }]}
        onClearAll={onClearAll}
      />
    )
    fireEvent.click(screen.getByText('Effacer tout'))
    expect(onClearAll).toHaveBeenCalledOnce()
  })
})
