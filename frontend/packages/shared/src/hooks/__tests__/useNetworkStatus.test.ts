/**
 * Tests unitaires pour hooks/useNetworkStatus.ts
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useNetworkStatus } from '../useNetworkStatus'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('useNetworkStatus', () => {
  it('isOnline = true si navigator.onLine = true', () => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true })
    const { result } = renderHook(() => useNetworkStatus())
    expect(result.current.isOnline).toBe(true)
    expect(result.current.wasOffline).toBe(false)
  })

  it('isOnline = false si navigator.onLine = false', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, writable: true, configurable: true })
    const { result } = renderHook(() => useNetworkStatus())
    expect(result.current.isOnline).toBe(false)
  })

  it('passe offline quand événement "offline" est émis', () => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true })
    const { result } = renderHook(() => useNetworkStatus())

    act(() => {
      window.dispatchEvent(new Event('offline'))
    })

    expect(result.current.isOnline).toBe(false)
  })

  it('repasse online quand événement "online" est émis', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, writable: true, configurable: true })
    const { result } = renderHook(() => useNetworkStatus())

    act(() => {
      window.dispatchEvent(new Event('online'))
    })

    expect(result.current.isOnline).toBe(true)
    expect(result.current.wasOffline).toBe(true) // signal "reconnecté"
  })

  it('wasOffline redevient false après 5s', () => {
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true })
    const { result } = renderHook(() => useNetworkStatus())

    act(() => { window.dispatchEvent(new Event('offline')) })
    act(() => { window.dispatchEvent(new Event('online')) })
    expect(result.current.wasOffline).toBe(true)

    act(() => { vi.advanceTimersByTime(5000) })
    expect(result.current.wasOffline).toBe(false)
  })
})
