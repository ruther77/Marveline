/**
 * Tests unitaires pour hooks/useSort.ts
 */
import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSort, useClientSort } from '../useSort'

describe('useSort - état initial', () => {
  it('pas de tri par défaut', () => {
    const { result } = renderHook(() => useSort())
    expect(result.current.sortKey).toBeNull()
    expect(result.current.sortDirection).toBeNull()
  })

  it('accepte des valeurs initiales', () => {
    const { result } = renderHook(() =>
      useSort({ initialKey: 'name', initialDirection: 'asc' })
    )
    expect(result.current.sortKey).toBe('name')
    expect(result.current.sortDirection).toBe('asc')
  })
})

describe('useSort - setSort (toggle cycle)', () => {
  it('null → asc sur première clé', () => {
    const { result } = renderHook(() => useSort())
    act(() => { result.current.setSort('name') })
    expect(result.current.sortKey).toBe('name')
    expect(result.current.sortDirection).toBe('asc')
  })

  it('asc → desc sur même clé', () => {
    const { result } = renderHook(() => useSort())
    act(() => { result.current.setSort('name') })
    act(() => { result.current.setSort('name') })
    expect(result.current.sortDirection).toBe('desc')
  })

  it('desc → null (reset) sur même clé', () => {
    const { result } = renderHook(() => useSort())
    act(() => { result.current.setSort('name') })
    act(() => { result.current.setSort('name') })
    act(() => { result.current.setSort('name') })
    expect(result.current.sortKey).toBeNull()
    expect(result.current.sortDirection).toBeNull()
  })

  it('changement de clé → repart à asc', () => {
    const { result } = renderHook(() => useSort())
    act(() => { result.current.setSort('name') })
    act(() => { result.current.setSort('name') }) // desc
    act(() => { result.current.setSort('date') }) // nouvelle clé → asc
    expect(result.current.sortKey).toBe('date')
    expect(result.current.sortDirection).toBe('asc')
  })
})

describe('useSort - clearSort', () => {
  it('remet sortKey et sortDirection à null', () => {
    const { result } = renderHook(() => useSort({ initialKey: 'name', initialDirection: 'asc' }))
    act(() => { result.current.clearSort() })
    expect(result.current.sortKey).toBeNull()
    expect(result.current.sortDirection).toBeNull()
  })
})

describe('useSort - getSortParams', () => {
  it('retourne {} sans tri actif', () => {
    const { result } = renderHook(() => useSort())
    expect(result.current.getSortParams()).toEqual({})
  })

  it('retourne sort_by et sort_order avec tri actif', () => {
    const { result } = renderHook(() => useSort({ initialKey: 'price', initialDirection: 'desc' }))
    expect(result.current.getSortParams()).toEqual({ sort_by: 'price', sort_order: 'desc' })
  })
})

describe('useSort - isSortedBy / getSortDirection', () => {
  it('isSortedBy retourne true pour la clé active', () => {
    const { result } = renderHook(() => useSort({ initialKey: 'name' }))
    expect(result.current.isSortedBy('name')).toBe(true)
    expect(result.current.isSortedBy('date')).toBe(false)
  })

  it('getSortDirection retourne la direction pour la clé active', () => {
    const { result } = renderHook(() => useSort({ initialKey: 'name', initialDirection: 'asc' }))
    expect(result.current.getSortDirection('name')).toBe('asc')
    expect(result.current.getSortDirection('other')).toBeNull()
  })
})

// ─── useClientSort ────────────────────────────────────────────────────────────

describe('useClientSort', () => {
  const data = [
    { name: 'Chaise', price: 30 },
    { name: 'Table', price: 150 },
    { name: 'Armoire', price: 80 },
  ]

  it('trie par string asc (localeCompare)', () => {
    const { result } = renderHook(() =>
      useClientSort(data, { initialKey: 'name', initialDirection: 'asc' })
    )
    expect(result.current.data[0].name).toBe('Armoire')
    expect(result.current.data[2].name).toBe('Table')
  })

  it('trie par nombre desc', () => {
    const { result } = renderHook(() =>
      useClientSort(data, { initialKey: 'price', initialDirection: 'desc' })
    )
    expect(result.current.data[0].price).toBe(150)
    expect(result.current.data[2].price).toBe(30)
  })

  it('retourne les données non triées si pas de tri actif', () => {
    const { result } = renderHook(() => useClientSort(data))
    expect(result.current.data).toEqual(data)
  })
})
