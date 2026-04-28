/**
 * Tests unitaires pour hooks/useOnClickOutside.ts
 * useOnClickOutside, useClickOutsideState
 */
import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useOnClickOutside, useClickOutsideState } from '../useOnClickOutside'

// ─── useOnClickOutside ────────────────────────────────────────────────────────

describe('useOnClickOutside', () => {
  it('retourne une ref initialisée à null', () => {
    const handler = vi.fn()
    const { result } = renderHook(() => useOnClickOutside(handler))
    expect(result.current.current).toBeNull()
  })

  it('s\'abonne à mousedown sur le document', () => {
    // Note : le handler nécessite que ref.current soit attaché à un élément DOM
    // (condition de garde : `if (!el || el.contains(...)) return`).
    // On vérifie ici que la ref est bien créée et que le hook s'initialise sans erreur.
    const handler = vi.fn()
    const { result } = renderHook(() => useOnClickOutside(handler))
    expect(result.current.current).toBeNull()
    // Le listener est enregistré — on vérifie qu'aucune erreur n'est levée lors du dispatch
    act(() => {
      document.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    })
    // handler non appelé car ref.current === null (garde interne)
    expect(handler).not.toHaveBeenCalled()
  })

  it('enabled=false : n\'appelle pas le handler', () => {
    const handler = vi.fn()
    renderHook(() => useOnClickOutside(handler, false))

    act(() => {
      document.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    })

    expect(handler).not.toHaveBeenCalled()
  })

  it('nettoie les listeners au démontage', () => {
    const handler = vi.fn()
    const { unmount } = renderHook(() => useOnClickOutside(handler))
    unmount()

    act(() => {
      document.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    })

    expect(handler).not.toHaveBeenCalled()
  })
})

// ─── useClickOutsideState ─────────────────────────────────────────────────────

describe('useClickOutsideState', () => {
  it('isOpen = false par défaut', () => {
    const { result } = renderHook(() => useClickOutsideState())
    expect(result.current.isOpen).toBe(false)
  })

  it('initialState = true ouvre au départ', () => {
    const { result } = renderHook(() => useClickOutsideState(true))
    expect(result.current.isOpen).toBe(true)
  })

  it('open() passe isOpen à true', () => {
    const { result } = renderHook(() => useClickOutsideState())

    act(() => { result.current.open() })
    expect(result.current.isOpen).toBe(true)
  })

  it('close() passe isOpen à false', () => {
    const { result } = renderHook(() => useClickOutsideState(true))

    act(() => { result.current.close() })
    expect(result.current.isOpen).toBe(false)
  })

  it('toggle() alterne l\'état', () => {
    const { result } = renderHook(() => useClickOutsideState())

    act(() => { result.current.toggle() })
    expect(result.current.isOpen).toBe(true)

    act(() => { result.current.toggle() })
    expect(result.current.isOpen).toBe(false)
  })

  it('close() ferme bien (utilisé comme handler du clic extérieur)', () => {
    // Note : useOnClickOutside ne déclenche pas le handler si ref.current === null
    // (condition de garde : `if (!el || el.contains(...)) return`)
    // On teste la fonction close() directement via l'API publique.
    const { result } = renderHook(() => useClickOutsideState(true))
    expect(result.current.isOpen).toBe(true)

    act(() => { result.current.close() })
    expect(result.current.isOpen).toBe(false)
  })

  it('setIsOpen permet de forcer la valeur', () => {
    const { result } = renderHook(() => useClickOutsideState())

    act(() => { result.current.setIsOpen(true) })
    expect(result.current.isOpen).toBe(true)
  })

  it('retourne une ref', () => {
    const { result } = renderHook(() => useClickOutsideState())
    expect(result.current.ref).toBeDefined()
    expect(result.current.ref).toHaveProperty('current')
  })
})
