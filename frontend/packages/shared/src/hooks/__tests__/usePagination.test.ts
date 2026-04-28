/**
 * Tests unitaires pour hooks/usePagination.ts
 */
import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { usePagination, useClientPagination } from '../usePagination'

// ─── usePagination ────────────────────────────────────────────────────────────

describe('usePagination - état initial', () => {
  it('valeurs par défaut', () => {
    const { result } = renderHook(() => usePagination())
    expect(result.current.page).toBe(1)
    expect(result.current.perPage).toBe(10)
    expect(result.current.total).toBe(0)
    expect(result.current.totalPages).toBe(1)
  })

  it('accepte des valeurs initiales', () => {
    const { result } = renderHook(() =>
      usePagination({ initialPage: 2, initialPerPage: 25, initialTotal: 100 })
    )
    expect(result.current.page).toBe(2)
    expect(result.current.perPage).toBe(25)
    expect(result.current.totalPages).toBe(4)
  })
})

describe('usePagination - navigation', () => {
  it('nextPage incrémente la page', () => {
    const { result } = renderHook(() =>
      usePagination({ initialTotal: 30, initialPerPage: 10 })
    )
    act(() => { result.current.setTotal(30) })
    act(() => { result.current.nextPage() })
    expect(result.current.page).toBe(2)
  })

  it('nextPage ne dépasse pas totalPages', () => {
    const { result } = renderHook(() =>
      usePagination({ initialTotal: 10, initialPerPage: 10 })
    )
    act(() => { result.current.nextPage() })
    expect(result.current.page).toBe(1) // seule 1 page
  })

  it('prevPage décrémente la page', () => {
    const { result } = renderHook(() =>
      usePagination({ initialPage: 3, initialTotal: 50, initialPerPage: 10 })
    )
    act(() => { result.current.prevPage() })
    expect(result.current.page).toBe(2)
  })

  it('prevPage ne descend pas sous 1', () => {
    const { result } = renderHook(() => usePagination())
    act(() => { result.current.prevPage() })
    expect(result.current.page).toBe(1)
  })

  it('firstPage revient en page 1', () => {
    const { result } = renderHook(() =>
      usePagination({ initialPage: 5, initialTotal: 100, initialPerPage: 10 })
    )
    act(() => { result.current.firstPage() })
    expect(result.current.page).toBe(1)
  })

  it('lastPage va à la dernière page', () => {
    const { result } = renderHook(() =>
      usePagination({ initialTotal: 50, initialPerPage: 10 })
    )
    act(() => { result.current.lastPage() })
    expect(result.current.page).toBe(5)
  })
})

describe('usePagination - setPage clamping', () => {
  it('clamp à 1 si page < 1', () => {
    const { result } = renderHook(() =>
      usePagination({ initialTotal: 50, initialPerPage: 10 })
    )
    act(() => { result.current.setPage(-5) })
    expect(result.current.page).toBe(1)
  })

  it('clamp à totalPages si page > totalPages', () => {
    const { result } = renderHook(() =>
      usePagination({ initialTotal: 30, initialPerPage: 10 })
    )
    act(() => { result.current.setPage(99) })
    expect(result.current.page).toBe(3)
  })
})

describe('usePagination - setPerPage', () => {
  it('reset à page 1 quand perPage change', () => {
    const { result } = renderHook(() =>
      usePagination({ initialPage: 3, initialTotal: 100, initialPerPage: 10 })
    )
    act(() => { result.current.setPerPage(25) })
    expect(result.current.page).toBe(1)
    expect(result.current.perPage).toBe(25)
  })
})

describe('usePagination - paginationParams', () => {
  it('calcule skip et limit correctement', () => {
    const { result } = renderHook(() =>
      usePagination({ initialPage: 2, initialPerPage: 15, initialTotal: 100 })
    )
    expect(result.current.paginationParams.skip).toBe(15)
    expect(result.current.paginationParams.limit).toBe(15)
  })
})

describe('usePagination - flags booléens', () => {
  it('hasNextPage / hasPrevPage / isFirstPage / isLastPage', () => {
    const { result } = renderHook(() =>
      usePagination({ initialPage: 2, initialTotal: 30, initialPerPage: 10 })
    )
    expect(result.current.hasNextPage).toBe(true)
    expect(result.current.hasPrevPage).toBe(true)
    expect(result.current.isFirstPage).toBe(false)
    expect(result.current.isLastPage).toBe(false)
  })
})

// ─── useClientPagination ──────────────────────────────────────────────────────

describe('useClientPagination', () => {
  const data = Array.from({ length: 25 }, (_, i) => ({ id: i + 1 }))

  it('pagine correctement la page 1', () => {
    const { result } = renderHook(() =>
      useClientPagination(data, { initialPerPage: 10 })
    )
    expect(result.current.data).toHaveLength(10)
    expect(result.current.data[0].id).toBe(1)
  })

  it('pagine correctement la page 3 (5 items restants)', () => {
    const { result } = renderHook(() =>
      useClientPagination(data, { initialPage: 3, initialPerPage: 10 })
    )
    expect(result.current.data).toHaveLength(5)
    expect(result.current.data[0].id).toBe(21)
  })
})
