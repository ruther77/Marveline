/**
 * Tests unitaires pour hooks/useLocalStorage.ts
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useLocalStorage, useSessionStorage } from '../useLocalStorage'

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

// ─── useLocalStorage ──────────────────────────────────────────────────────────

describe('useLocalStorage', () => {
  it('retourne la valeur initiale si localStorage vide', () => {
    const { result } = renderHook(() => useLocalStorage('test-key', 'default'))
    expect(result.current[0]).toBe('default')
  })

  it('lit une valeur déjà présente dans localStorage', () => {
    localStorage.setItem('existing-key', JSON.stringify('stored-value'))
    const { result } = renderHook(() => useLocalStorage('existing-key', 'default'))
    expect(result.current[0]).toBe('stored-value')
  })

  it('setValue met à jour l\'état et localStorage', () => {
    const { result } = renderHook(() => useLocalStorage('my-key', 0))
    act(() => { result.current[1](42) })
    expect(result.current[0]).toBe(42)
    expect(JSON.parse(localStorage.getItem('my-key')!)).toBe(42)
  })

  it('setValue accepte une fonction updater', () => {
    const { result } = renderHook(() => useLocalStorage('counter', 5))
    act(() => { result.current[1]((prev) => prev + 1) })
    expect(result.current[0]).toBe(6)
  })

  it('removeValue efface localStorage et remet la valeur initiale', () => {
    const { result } = renderHook(() => useLocalStorage('key-to-remove', 'initial'))
    act(() => { result.current[1]('changed') })
    act(() => { result.current[2]() }) // removeValue
    expect(result.current[0]).toBe('initial')
    expect(localStorage.getItem('key-to-remove')).toBeNull()
  })

  it('fonctionne avec des objets', () => {
    const { result } = renderHook(() =>
      useLocalStorage<{ name: string }>('obj-key', { name: 'default' })
    )
    act(() => { result.current[1]({ name: 'updated' }) })
    expect(result.current[0].name).toBe('updated')
    expect(JSON.parse(localStorage.getItem('obj-key')!).name).toBe('updated')
  })
})

// ─── useSessionStorage ────────────────────────────────────────────────────────

describe('useSessionStorage', () => {
  it('retourne la valeur initiale si sessionStorage vide', () => {
    const { result } = renderHook(() => useSessionStorage('sess-key', false))
    expect(result.current[0]).toBe(false)
  })

  it('setValue persiste dans sessionStorage', () => {
    const { result } = renderHook(() => useSessionStorage('sess-flag', false))
    act(() => { result.current[1](true) })
    expect(result.current[0]).toBe(true)
    expect(JSON.parse(sessionStorage.getItem('sess-flag')!)).toBe(true)
  })

  it('removeValue efface sessionStorage', () => {
    const { result } = renderHook(() => useSessionStorage('sess-remove', 'init'))
    act(() => { result.current[1]('changed') })
    act(() => { result.current[2]() })
    expect(result.current[0]).toBe('init')
    expect(sessionStorage.getItem('sess-remove')).toBeNull()
  })
})
