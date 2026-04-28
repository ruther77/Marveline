/**
 * Tests unitaires pour hooks/useClipboard.ts
 * useClipboard, useClipboardRead
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useClipboard, useClipboardRead } from '../useClipboard'

// ─── useClipboard ─────────────────────────────────────────────────────────────

describe('useClipboard - état initial', () => {
  it('copied = false, error = null', () => {
    const { result } = renderHook(() => useClipboard())
    expect(result.current.copied).toBe(false)
    expect(result.current.error).toBeNull()
  })
})

describe('useClipboard - copy via navigator.clipboard (contexte sécurisé)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    Object.defineProperty(window, 'isSecureContext', { value: true, writable: true, configurable: true })
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
      configurable: true,
    })
  })
  afterEach(() => vi.useRealTimers())

  it('copy() retourne true et passe copied = true', async () => {
    const { result } = renderHook(() => useClipboard())
    let success: boolean | undefined

    await act(async () => {
      success = await result.current.copy('hello')
    })

    expect(success).toBe(true)
    expect(result.current.copied).toBe(true)
    expect(result.current.error).toBeNull()
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('hello')
  })

  it('copied repasse à false après timeout (2000ms par défaut)', async () => {
    const { result } = renderHook(() => useClipboard())

    await act(async () => { await result.current.copy('text') })
    expect(result.current.copied).toBe(true)

    act(() => { vi.advanceTimersByTime(2000) })
    expect(result.current.copied).toBe(false)
  })

  it('timeout personnalisé', async () => {
    const { result } = renderHook(() => useClipboard({ timeout: 500 }))

    await act(async () => { await result.current.copy('text') })
    expect(result.current.copied).toBe(true)

    act(() => { vi.advanceTimersByTime(499) })
    expect(result.current.copied).toBe(true)

    act(() => { vi.advanceTimersByTime(1) })
    expect(result.current.copied).toBe(false)
  })

  it('appelle onSuccess avec le texte copié', async () => {
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useClipboard({ onSuccess }))

    await act(async () => { await result.current.copy('my text') })
    expect(onSuccess).toHaveBeenCalledWith('my text')
  })
})

describe('useClipboard - erreur', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'isSecureContext', { value: true, writable: true, configurable: true })
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockRejectedValue(new Error('permission denied')) },
      writable: true,
      configurable: true,
    })
  })

  it('copy() retourne false et set error', async () => {
    const { result } = renderHook(() => useClipboard())
    let success: boolean | undefined

    await act(async () => {
      success = await result.current.copy('text')
    })

    expect(success).toBe(false)
    expect(result.current.copied).toBe(false)
    expect(result.current.error?.message).toBe('permission denied')
  })

  it('appelle onError', async () => {
    const onError = vi.fn()
    const { result } = renderHook(() => useClipboard({ onError }))

    await act(async () => { await result.current.copy('text') })
    expect(onError).toHaveBeenCalled()
  })
})

// ─── useClipboardRead ─────────────────────────────────────────────────────────

describe('useClipboardRead', () => {
  it('read() retourne le texte du presse-papier', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { readText: vi.fn().mockResolvedValue('clipboard content') },
      writable: true,
      configurable: true,
    })

    const { result } = renderHook(() => useClipboardRead())
    expect(result.current.isSupported).toBe(true)

    let text: string | null = null
    await act(async () => {
      text = await result.current.read()
    })

    expect(text).toBe('clipboard content')
    expect(result.current.text).toBe('clipboard content')
    expect(result.current.error).toBeNull()
  })

  it('read() set error si readText rejette', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { readText: vi.fn().mockRejectedValue(new Error('not allowed')) },
      writable: true,
      configurable: true,
    })

    const { result } = renderHook(() => useClipboardRead())

    await act(async () => { await result.current.read() })
    expect(result.current.error?.message).toBe('not allowed')
    expect(result.current.text).toBeNull()
  })
})
