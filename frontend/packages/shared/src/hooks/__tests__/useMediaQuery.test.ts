/**
 * Tests unitaires pour hooks/useMediaQuery.ts
 * useMediaQuery, useBreakpoint, useCurrentBreakpoint, useResponsive
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useMediaQuery, useBreakpoint, useResponsive } from '../useMediaQuery'

// Helper pour créer un mock MediaQueryList
type MQListener = (event: MediaQueryListEvent) => void

function createMqlMock(matches: boolean) {
  const listeners: MQListener[] = []
  const mql = {
    matches,
    media: '',
    addEventListener: vi.fn((_: string, cb: MQListener) => { listeners.push(cb) }),
    removeEventListener: vi.fn((_: string, cb: MQListener) => {
      const idx = listeners.indexOf(cb)
      if (idx !== -1) listeners.splice(idx, 1)
    }),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    // Helper pour déclencher un changement
    _trigger: (newMatches: boolean) => {
      listeners.forEach(cb => cb({ matches: newMatches } as MediaQueryListEvent))
    },
  }
  return mql
}

// ─── useMediaQuery ────────────────────────────────────────────────────────────

describe('useMediaQuery', () => {
  it('retourne true si matchMedia retourne matches=true', () => {
    const mql = createMqlMock(true)
    vi.spyOn(window, 'matchMedia').mockReturnValue(mql as unknown as MediaQueryList)

    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))
    expect(result.current).toBe(true)
  })

  it('retourne false si matchMedia retourne matches=false', () => {
    const mql = createMqlMock(false)
    vi.spyOn(window, 'matchMedia').mockReturnValue(mql as unknown as MediaQueryList)

    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))
    expect(result.current).toBe(false)
  })

  it('met à jour quand la media query change', () => {
    const mql = createMqlMock(false)
    vi.spyOn(window, 'matchMedia').mockReturnValue(mql as unknown as MediaQueryList)

    const { result } = renderHook(() => useMediaQuery('(min-width: 768px)'))
    expect(result.current).toBe(false)

    act(() => { mql._trigger(true) })
    expect(result.current).toBe(true)
  })

  it('s\'abonne avec addEventListener', () => {
    const mql = createMqlMock(false)
    vi.spyOn(window, 'matchMedia').mockReturnValue(mql as unknown as MediaQueryList)

    renderHook(() => useMediaQuery('(min-width: 768px)'))
    expect(mql.addEventListener).toHaveBeenCalledWith('change', expect.any(Function))
  })
})

// ─── useBreakpoint ────────────────────────────────────────────────────────────

describe('useBreakpoint', () => {
  it('retourne true pour le breakpoint sm si la query correspond', () => {
    const mql = createMqlMock(true)
    vi.spyOn(window, 'matchMedia').mockReturnValue(mql as unknown as MediaQueryList)

    const { result } = renderHook(() => useBreakpoint('sm'))
    expect(result.current).toBe(true)
  })

  it('retourne false si la query ne correspond pas', () => {
    const mql = createMqlMock(false)
    vi.spyOn(window, 'matchMedia').mockReturnValue(mql as unknown as MediaQueryList)

    const { result } = renderHook(() => useBreakpoint('lg'))
    expect(result.current).toBe(false)
  })
})

// ─── useResponsive ────────────────────────────────────────────────────────────

describe('useResponsive', () => {
  beforeEach(() => {
    // Mobile : (max-width: 767px) = true, tout le reste = false
    vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => {
      const matches = query === '(max-width: 767px)'
      return createMqlMock(matches) as unknown as MediaQueryList
    })
  })

  it('isMobile = true si max-width: 767px correspond', () => {
    const { result } = renderHook(() => useResponsive())
    expect(result.current.isMobile).toBe(true)
    expect(result.current.isDesktop).toBe(false)
  })

  it('retourne les champs attendus', () => {
    const { result } = renderHook(() => useResponsive())
    expect(result.current).toHaveProperty('isMobile')
    expect(result.current).toHaveProperty('isTablet')
    expect(result.current).toHaveProperty('isDesktop')
    expect(result.current).toHaveProperty('isLargeDesktop')
    expect(result.current).toHaveProperty('prefersReducedMotion')
    expect(result.current).toHaveProperty('prefersDarkMode')
    expect(result.current).toHaveProperty('isPortrait')
    expect(result.current).toHaveProperty('isLandscape')
    expect(result.current).toHaveProperty('isTouchDevice')
    expect(result.current).toHaveProperty('breakpoint')
  })
})
