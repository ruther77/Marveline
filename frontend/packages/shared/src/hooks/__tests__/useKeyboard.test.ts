/**
 * Tests unitaires pour hooks/useKeyboard.ts
 * useKeyPress, useKeyboardShortcuts, useEscapeKey, useEnterKey, useListNavigation
 */
import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import {
  useKeyPress,
  useKeyboardShortcuts,
  useEscapeKey,
  useEnterKey,
  useListNavigation,
} from '../useKeyboard'

// Helper pour dispatcher un événement clavier
const fireKey = (key: string, opts: Partial<KeyboardEventInit> = {}) => {
  window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...opts }))
}

// ─── useKeyPress ──────────────────────────────────────────────────────────────

describe('useKeyPress', () => {
  it('appelle le handler quand la touche est pressée', () => {
    const handler = vi.fn()
    renderHook(() => useKeyPress('a', handler))

    act(() => { fireKey('a') })
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('n\'appelle pas le handler sur une autre touche', () => {
    const handler = vi.fn()
    renderHook(() => useKeyPress('a', handler))

    act(() => { fireKey('b') })
    expect(handler).not.toHaveBeenCalled()
  })

  it('case-insensitive (A = a)', () => {
    const handler = vi.fn()
    renderHook(() => useKeyPress('a', handler))

    act(() => { fireKey('A') })
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('enabled=false : ne réagit pas', () => {
    const handler = vi.fn()
    renderHook(() => useKeyPress('a', handler, { enabled: false }))

    act(() => { fireKey('a') })
    expect(handler).not.toHaveBeenCalled()
  })

  it('exige Ctrl si ctrl=true', () => {
    const handler = vi.fn()
    renderHook(() => useKeyPress('s', handler, { ctrl: true }))

    act(() => { fireKey('s') }) // sans Ctrl
    expect(handler).not.toHaveBeenCalled()

    act(() => { fireKey('s', { ctrlKey: true }) }) // avec Ctrl
    expect(handler).toHaveBeenCalledTimes(1)
  })
})

// ─── useKeyboardShortcuts ─────────────────────────────────────────────────────

describe('useKeyboardShortcuts', () => {
  it('exécute le bon handler selon la touche', () => {
    const onSave = vi.fn()
    const onCancel = vi.fn()
    renderHook(() =>
      useKeyboardShortcuts([
        { key: 's', ctrl: true, handler: onSave },
        { key: 'Escape', handler: onCancel },
      ])
    )

    act(() => { fireKey('s', { ctrlKey: true }) })
    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onCancel).not.toHaveBeenCalled()

    act(() => { fireKey('Escape') })
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('enabled=false : aucun handler appelé', () => {
    const handler = vi.fn()
    renderHook(() => useKeyboardShortcuts([{ key: 'a', handler }], false))

    act(() => { fireKey('a') })
    expect(handler).not.toHaveBeenCalled()
  })

  it('ne déclenche qu\'un seul handler (break après le premier match)', () => {
    const h1 = vi.fn()
    const h2 = vi.fn()
    renderHook(() =>
      useKeyboardShortcuts([
        { key: 'a', handler: h1 },
        { key: 'a', handler: h2 }, // doublon
      ])
    )

    act(() => { fireKey('a') })
    expect(h1).toHaveBeenCalledTimes(1)
    expect(h2).not.toHaveBeenCalled()
  })
})

// ─── useEscapeKey ─────────────────────────────────────────────────────────────

describe('useEscapeKey', () => {
  it('appelle le handler sur Escape', () => {
    const handler = vi.fn()
    renderHook(() => useEscapeKey(handler))

    act(() => { fireKey('Escape') })
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('n\'appelle pas le handler sur une autre touche', () => {
    const handler = vi.fn()
    renderHook(() => useEscapeKey(handler))

    act(() => { fireKey('Enter') })
    expect(handler).not.toHaveBeenCalled()
  })
})

// ─── useEnterKey ──────────────────────────────────────────────────────────────

describe('useEnterKey', () => {
  it('appelle le handler sur Enter', () => {
    const handler = vi.fn()
    renderHook(() => useEnterKey(handler))

    act(() => { fireKey('Enter') })
    expect(handler).toHaveBeenCalledTimes(1)
  })
})

// ─── useListNavigation ────────────────────────────────────────────────────────

describe('useListNavigation', () => {
  const items = ['pomme', 'banane', 'cerise']

  it('activeIndex = 0 par défaut', () => {
    const { result } = renderHook(() => useListNavigation(items))
    expect(result.current.activeIndex).toBe(0)
    expect(result.current.activeItem).toBe('pomme')
  })

  it('ArrowDown incrémente activeIndex', () => {
    const { result } = renderHook(() => useListNavigation(items))

    act(() => { fireKey('ArrowDown') })
    expect(result.current.activeIndex).toBe(1)

    act(() => { fireKey('ArrowDown') })
    expect(result.current.activeIndex).toBe(2)
  })

  it('ArrowUp décrémente activeIndex', () => {
    const { result } = renderHook(() => useListNavigation(items))

    act(() => { fireKey('ArrowDown') })
    act(() => { fireKey('ArrowUp') })
    expect(result.current.activeIndex).toBe(0)
  })

  it('loop=true : ArrowDown à la fin revient au début', () => {
    const { result } = renderHook(() => useListNavigation(items, { loop: true }))

    act(() => { fireKey('ArrowDown') }) // 1
    act(() => { fireKey('ArrowDown') }) // 2
    act(() => { fireKey('ArrowDown') }) // → 0 (loop)
    expect(result.current.activeIndex).toBe(0)
  })

  it('loop=false : ArrowDown bloqué à la fin', () => {
    const { result } = renderHook(() => useListNavigation(items, { loop: false }))

    act(() => { fireKey('ArrowDown') }) // 1
    act(() => { fireKey('ArrowDown') }) // 2
    act(() => { fireKey('ArrowDown') }) // reste à 2
    expect(result.current.activeIndex).toBe(2)
  })

  it('Enter appelle onSelect avec l\'item actif', () => {
    const onSelect = vi.fn()
    const { result } = renderHook(() => useListNavigation(items, { onSelect }))

    act(() => { fireKey('ArrowDown') })
    act(() => { fireKey('Enter') })

    expect(onSelect).toHaveBeenCalledWith('banane', 1)
  })

  it('setActiveIndex change l\'index directement', () => {
    const { result } = renderHook(() => useListNavigation(items))

    act(() => { result.current.setActiveIndex(2) })
    expect(result.current.activeIndex).toBe(2)
    expect(result.current.activeItem).toBe('cerise')
  })
})
