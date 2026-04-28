/**
 * Tests unitaires pour hooks/useDebounce.ts
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDebounce } from '../useDebounce'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('useDebounce', () => {
  it('retourne la valeur initiale immédiatement', () => {
    const { result } = renderHook(() => useDebounce('initial', 300))
    expect(result.current).toBe('initial')
  })

  it('ne met pas à jour avant le délai', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'a' } }
    )

    rerender({ value: 'b' })
    act(() => { vi.advanceTimersByTime(200) })

    expect(result.current).toBe('a') // pas encore mis à jour
  })

  it('met à jour après le délai', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'a' } }
    )

    rerender({ value: 'b' })
    act(() => { vi.advanceTimersByTime(300) })

    expect(result.current).toBe('b')
  })

  it('repart le timer si la valeur change à nouveau', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'a' } }
    )

    rerender({ value: 'b' })
    act(() => { vi.advanceTimersByTime(200) })
    rerender({ value: 'c' })
    act(() => { vi.advanceTimersByTime(200) })

    expect(result.current).toBe('a') // 200ms seulement depuis 'c'

    act(() => { vi.advanceTimersByTime(100) })
    expect(result.current).toBe('c') // 300ms depuis 'c'
  })

  it('fonctionne avec un délai personnalisé', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 1000),
      { initialProps: { value: 1 } }
    )

    rerender({ value: 2 })
    act(() => { vi.advanceTimersByTime(999) })
    expect(result.current).toBe(1)

    act(() => { vi.advanceTimersByTime(1) })
    expect(result.current).toBe(2)
  })

  it('fonctionne avec des types génériques (objet)', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 200),
      { initialProps: { value: { id: 1 } } }
    )

    rerender({ value: { id: 2 } })
    act(() => { vi.advanceTimersByTime(200) })

    expect(result.current.id).toBe(2)
  })
})
