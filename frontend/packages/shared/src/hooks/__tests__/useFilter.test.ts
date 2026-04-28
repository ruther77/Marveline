/**
 * Tests unitaires pour hooks/useFilter.ts
 */
import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useFilter, useClientFilter, filterUtils } from '../useFilter'

// ─── useFilter ────────────────────────────────────────────────────────────────

describe('useFilter - état initial', () => {
  it('filtres vides par défaut', () => {
    const { result } = renderHook(() => useFilter())
    expect(result.current.filters).toEqual({})
    expect(result.current.activeFiltersCount).toBe(0)
    expect(result.current.hasActiveFilters).toBe(false)
  })

  it('accepte des filtres initiaux', () => {
    const { result } = renderHook(() =>
      useFilter({ initialFilters: { status: 'active', page: 1 } })
    )
    expect(result.current.activeFiltersCount).toBe(2)
    expect(result.current.hasActiveFilters).toBe(true)
  })
})

describe('useFilter - setFilter', () => {
  it('ajoute un filtre', () => {
    const { result } = renderHook(() => useFilter())
    act(() => { result.current.setFilter('status', 'active') })
    expect(result.current.filters.status).toBe('active')
    expect(result.current.activeFiltersCount).toBe(1)
  })

  it('ne compte pas null comme filtre actif', () => {
    const { result } = renderHook(() => useFilter())
    act(() => { result.current.setFilter('status', null) })
    expect(result.current.activeFiltersCount).toBe(0)
  })

  it('ne compte pas string vide comme filtre actif', () => {
    const { result } = renderHook(() => useFilter())
    act(() => { result.current.setFilter('search', '') })
    expect(result.current.activeFiltersCount).toBe(0)
  })

  it('ne compte pas un tableau vide comme filtre actif', () => {
    const { result } = renderHook(() => useFilter())
    act(() => { result.current.setFilter('tags', []) })
    expect(result.current.activeFiltersCount).toBe(0)
  })
})

describe('useFilter - setFilters / removeFilter / clearFilters', () => {
  it('setFilters fusionne avec les filtres existants', () => {
    const { result } = renderHook(() => useFilter())
    act(() => { result.current.setFilter('status', 'active') })
    act(() => { result.current.setFilters({ search: 'table', page: 2 }) })
    expect(result.current.filters.status).toBe('active')
    expect(result.current.filters.search).toBe('table')
  })

  it('removeFilter supprime un seul filtre', () => {
    const { result } = renderHook(() =>
      useFilter({ initialFilters: { status: 'active', search: 'test' } })
    )
    act(() => { result.current.removeFilter('status') })
    expect(result.current.filters.status).toBeUndefined()
    expect(result.current.filters.search).toBe('test')
  })

  it('clearFilters vide tout', () => {
    const { result } = renderHook(() =>
      useFilter({ initialFilters: { status: 'active', search: 'test' } })
    )
    act(() => { result.current.clearFilters() })
    expect(result.current.filters).toEqual({})
    expect(result.current.activeFiltersCount).toBe(0)
  })
})

describe('useFilter - resetFilters', () => {
  it('remet les filtres initiaux', () => {
    const { result } = renderHook(() =>
      useFilter({ initialFilters: { status: 'active' } })
    )
    act(() => { result.current.clearFilters() })
    act(() => { result.current.resetFilters() })
    expect(result.current.filters.status).toBe('active')
  })
})

describe('useFilter - getFilterParams', () => {
  it('exclut les valeurs null/vides', () => {
    const { result } = renderHook(() => useFilter())
    act(() => {
      result.current.setFilter('status', 'active')
      result.current.setFilter('search', null)
    })
    const params = result.current.getFilterParams()
    expect(params.status).toBe('active')
    expect('search' in params).toBe(false)
  })

  it('sérialise les booléens en string', () => {
    const { result } = renderHook(() => useFilter())
    act(() => { result.current.setFilter('is_active', true) })
    expect(result.current.getFilterParams().is_active).toBe('true')
  })

  it('passe les tableaux tels quels', () => {
    const { result } = renderHook(() => useFilter())
    act(() => { result.current.setFilter('tags', ['promo', 'new']) })
    expect(result.current.getFilterParams().tags).toEqual(['promo', 'new'])
  })
})

// ─── filterUtils ──────────────────────────────────────────────────────────────

describe('filterUtils', () => {
  it('textContains : case-insensitive', () => {
    expect(filterUtils.textContains('Table ronde', 'table')).toBe(true)
    expect(filterUtils.textContains('Chaise', 'table')).toBe(false)
    expect(filterUtils.textContains('Produit', '')).toBe(true) // search vide → tout passe
  })

  it('equals : correspondance exacte', () => {
    expect(filterUtils.equals('active', 'active')).toBe(true)
    expect(filterUtils.equals('active', 'inactive')).toBe(false)
    expect(filterUtils.equals('anything', null)).toBe(true) // filtre null → tout passe
  })

  it('inList : inclus dans la liste', () => {
    expect(filterUtils.inList('a', ['a', 'b'])).toBe(true)
    expect(filterUtils.inList('c', ['a', 'b'])).toBe(false)
    expect(filterUtils.inList('x', [])).toBe(true) // liste vide → tout passe
  })

  it('inRange : plage numérique', () => {
    expect(filterUtils.inRange(50, 10, 100)).toBe(true)
    expect(filterUtils.inRange(5, 10, 100)).toBe(false)
    expect(filterUtils.inRange(150, 10, 100)).toBe(false)
  })

  it('dateInRange : plage de dates', () => {
    expect(filterUtils.dateInRange('2026-06-15', '2026-01-01', '2026-12-31')).toBe(true)
    expect(filterUtils.dateInRange('2025-12-31', '2026-01-01', '2026-12-31')).toBe(false)
  })
})

// ─── useClientFilter ─────────────────────────────────────────────────────────

describe('useClientFilter', () => {
  const data = [
    { id: 1, name: 'Table ronde', status: 'active' },
    { id: 2, name: 'Chaise pliante', status: 'inactive' },
    { id: 3, name: 'Table carrée', status: 'active' },
  ]

  it('retourne toutes les données sans filtre actif', () => {
    const { result } = renderHook(() =>
      useClientFilter(data, (item, filters) => filterUtils.textContains(item.name, filters.search as string || ''))
    )
    expect(result.current.data).toHaveLength(3)
  })

  it('filtre correctement avec filtre actif', () => {
    const { result } = renderHook(() =>
      useClientFilter(
        data,
        (item, filters) => filterUtils.textContains(item.name, filters.search as string || ''),
        { initialFilters: { search: 'table' } }
      )
    )
    expect(result.current.data).toHaveLength(2)
    expect(result.current.data.every(item => item.name.toLowerCase().includes('table'))).toBe(true)
  })
})
