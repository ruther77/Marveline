/**
 * Tests unitaires pour hooks/useAsync.ts
 * useAsync, useAsyncRetry, usePolling
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useAsync, useAsyncRetry, usePolling } from '../useAsync'

// ─── useAsync ────────────────────────────────────────────────────────────────

describe('useAsync - état initial', () => {
  it('status = idle par défaut', () => {
    const fn = vi.fn().mockResolvedValue('ok')
    const { result } = renderHook(() => useAsync(fn))
    expect(result.current.status).toBe('idle')
    expect(result.current.isIdle).toBe(true)
    expect(result.current.isPending).toBe(false)
    expect(result.current.isSuccess).toBe(false)
    expect(result.current.isError).toBe(false)
    expect(result.current.data).toBeNull()
    expect(result.current.error).toBeNull()
  })
})

describe('useAsync - execute succès', () => {
  it('passe pending → success avec data', async () => {
    const fn = vi.fn().mockResolvedValue({ id: 1 })
    const { result } = renderHook(() => useAsync(fn))

    await act(async () => {
      await result.current.execute()
    })

    expect(result.current.status).toBe('success')
    expect(result.current.isSuccess).toBe(true)
    expect(result.current.data).toEqual({ id: 1 })
    expect(result.current.error).toBeNull()
  })

  it('appelle onSuccess avec la data', async () => {
    const fn = vi.fn().mockResolvedValue('result')
    const onSuccess = vi.fn()
    const { result } = renderHook(() => useAsync(fn, { onSuccess }))

    await act(async () => {
      await result.current.execute()
    })

    expect(onSuccess).toHaveBeenCalledWith('result')
  })

  it('passe les arguments à la fonction', async () => {
    const fn = vi.fn().mockResolvedValue('ok')
    const { result } = renderHook(() => useAsync(fn))

    await act(async () => {
      await result.current.execute('arg1', 42)
    })

    expect(fn).toHaveBeenCalledWith('arg1', 42)
  })
})

describe('useAsync - execute erreur', () => {
  it('passe pending → error avec error', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useAsync(fn))

    await act(async () => {
      await result.current.execute()
    })

    expect(result.current.status).toBe('error')
    expect(result.current.isError).toBe(true)
    expect(result.current.error?.message).toBe('boom')
    expect(result.current.data).toBeNull()
  })

  it('appelle onError avec l\'erreur', async () => {
    const err = new Error('oops')
    const fn = vi.fn().mockRejectedValue(err)
    const onError = vi.fn()
    const { result } = renderHook(() => useAsync(fn, { onError }))

    await act(async () => {
      await result.current.execute()
    })

    expect(onError).toHaveBeenCalledWith(err)
  })

  it('convert une erreur non-Error en Error', async () => {
    const fn = vi.fn().mockRejectedValue('string error')
    const { result } = renderHook(() => useAsync(fn))

    await act(async () => {
      await result.current.execute()
    })

    expect(result.current.error).toBeInstanceOf(Error)
    expect(result.current.error?.message).toBe('string error')
  })
})

describe('useAsync - reset', () => {
  it('reset() remet l\'état à idle', async () => {
    const fn = vi.fn().mockResolvedValue('val')
    const { result } = renderHook(() => useAsync(fn))

    await act(async () => {
      await result.current.execute()
    })
    expect(result.current.status).toBe('success')

    act(() => { result.current.reset() })
    expect(result.current.status).toBe('idle')
    expect(result.current.data).toBeNull()
  })
})

describe('useAsync - setData', () => {
  it('setData met à jour data sans changer le status', async () => {
    const fn = vi.fn().mockResolvedValue('initial')
    const { result } = renderHook(() => useAsync(fn))

    await act(async () => { await result.current.execute() })
    act(() => { result.current.setData('patched') })

    expect(result.current.data).toBe('patched')
    expect(result.current.status).toBe('success')
  })
})

describe('useAsync - immediate', () => {
  it('exécute automatiquement si immediate=true', async () => {
    const fn = vi.fn().mockResolvedValue('auto')
    renderHook(() => useAsync(fn, { immediate: true }))

    await waitFor(() => {
      expect(fn).toHaveBeenCalledTimes(1)
    })
  })
})

// ─── useAsyncRetry ────────────────────────────────────────────────────────────

describe('useAsyncRetry', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('succès au premier essai : retryCount = 0', async () => {
    const fn = vi.fn().mockResolvedValue('ok')
    const { result } = renderHook(() => useAsyncRetry(fn, { maxRetries: 2, retryDelay: 100 }))

    await act(async () => { await result.current.execute() })
    expect(result.current.retryCount).toBe(0)
    expect(result.current.status).toBe('success')
  })

  it('retente et réussit finalement', async () => {
    const fn = vi.fn()
      .mockRejectedValueOnce(new Error('fail 1'))
      .mockRejectedValueOnce(new Error('fail 2'))
      .mockResolvedValue('ok')

    const { result } = renderHook(() =>
      useAsyncRetry(fn, { maxRetries: 3, retryDelay: 100, backoff: false })
    )

    const executePromise = act(async () => {
      const p = result.current.execute()
      // Avancer les timers pour les délais
      await vi.runAllTimersAsync()
      await p
    })

    await executePromise
    expect(result.current.status).toBe('success')
    expect(fn).toHaveBeenCalledTimes(3)
  })

  it('status = error après épuisement des retries', async () => {
    const fn = vi.fn().mockRejectedValue(new Error('always fail'))
    const { result } = renderHook(() =>
      useAsyncRetry(fn, { maxRetries: 2, retryDelay: 50, backoff: false })
    )

    await act(async () => {
      const p = result.current.execute()
      await vi.runAllTimersAsync()
      await p
    })

    expect(result.current.status).toBe('error')
    expect(fn).toHaveBeenCalledTimes(3) // 1 initial + 2 retries
  })
})

// ─── usePolling ───────────────────────────────────────────────────────────────

describe('usePolling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('appelle la fonction immédiatement puis à intervalle', async () => {
    const fn = vi.fn().mockResolvedValue('data')
    renderHook(() => usePolling(fn, 1000))

    // Appel initial
    await act(async () => { await Promise.resolve() })
    expect(fn).toHaveBeenCalledTimes(1)

    // Après 1 intervalle
    await act(async () => {
      vi.advanceTimersByTime(1000)
      await Promise.resolve()
    })
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('ne poll pas si enabled=false', async () => {
    const fn = vi.fn().mockResolvedValue('data')
    renderHook(() => usePolling(fn, 1000, { enabled: false }))

    await act(async () => {
      vi.advanceTimersByTime(3000)
      await Promise.resolve()
    })
    expect(fn).not.toHaveBeenCalled()
  })
})
