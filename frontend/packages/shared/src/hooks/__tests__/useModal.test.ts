/**
 * Tests unitaires pour hooks/useModal.ts
 * useModal, useMultiModal, useConfirmModal
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useModal, useMultiModal, useConfirmModal } from '../useModal'

// ─── useModal ─────────────────────────────────────────────────────────────────

describe('useModal', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('fermé par défaut', () => {
    const { result } = renderHook(() => useModal())
    expect(result.current.isOpen).toBe(false)
    expect(result.current.data).toBeNull()
  })

  it('ouvert si initialOpen=true', () => {
    const { result } = renderHook(() => useModal(true))
    expect(result.current.isOpen).toBe(true)
  })

  it('open() ouvre le modal', () => {
    const { result } = renderHook(() => useModal<{ id: number }>())
    act(() => { result.current.open({ id: 42 }) })
    expect(result.current.isOpen).toBe(true)
    expect(result.current.data).toEqual({ id: 42 })
  })

  it('close() ferme et efface data (après 200ms)', () => {
    const { result } = renderHook(() => useModal<{ id: number }>())
    act(() => { result.current.open({ id: 5 }) })
    act(() => { result.current.close() })

    expect(result.current.isOpen).toBe(false)
    // data encore présente avant 200ms
    expect(result.current.data).toEqual({ id: 5 })

    act(() => { vi.advanceTimersByTime(200) })
    expect(result.current.data).toBeNull()
  })

  it('toggle() alterne l\'état', () => {
    const { result } = renderHook(() => useModal())
    act(() => { result.current.toggle() })
    expect(result.current.isOpen).toBe(true)
    act(() => { result.current.toggle() })
    expect(result.current.isOpen).toBe(false)
  })
})

// ─── useMultiModal ────────────────────────────────────────────────────────────

describe('useMultiModal', () => {
  it('aucun modal actif par défaut', () => {
    const { result } = renderHook(() => useMultiModal())
    expect(result.current.activeModal).toBeNull()
    expect(result.current.isOpen('edit')).toBe(false)
  })

  it('open() active le bon modal avec data', () => {
    const { result } = renderHook(() => useMultiModal<{ id: number }>())
    act(() => { result.current.open('edit', { id: 7 }) })
    expect(result.current.activeModal).toBe('edit')
    expect(result.current.isOpen('edit')).toBe(true)
    expect(result.current.isOpen('delete')).toBe(false)
    expect(result.current.data).toEqual({ id: 7 })
  })

  it('close() remet activeModal à null', () => {
    const { result } = renderHook(() => useMultiModal())
    act(() => { result.current.open('edit') })
    act(() => { result.current.close() })
    expect(result.current.activeModal).toBeNull()
  })

  it('toggle() ferme si même id est déjà ouvert', () => {
    const { result } = renderHook(() => useMultiModal())
    act(() => { result.current.open('edit') })
    act(() => { result.current.toggle('edit') })
    expect(result.current.activeModal).toBeNull()
  })

  it('toggle() ouvre si id différent', () => {
    const { result } = renderHook(() => useMultiModal())
    act(() => { result.current.open('edit') })
    act(() => { result.current.toggle('delete') })
    expect(result.current.activeModal).toBe('delete')
  })
})

// ─── useConfirmModal ──────────────────────────────────────────────────────────

describe('useConfirmModal', () => {
  it('fermé par défaut', () => {
    const { result } = renderHook(() => useConfirmModal())
    expect(result.current.isOpen).toBe(false)
  })

  it('confirm() ouvre le modal et résout true sur handleConfirm', async () => {
    const { result } = renderHook(() => useConfirmModal<{ label: string }>())

    let confirmed: boolean | undefined
    act(() => {
      result.current.confirm({ label: 'Supprimer ?' }).then((v) => { confirmed = v })
    })

    expect(result.current.isOpen).toBe(true)
    expect(result.current.data).toEqual({ label: 'Supprimer ?' })

    act(() => { result.current.handleConfirm() })

    await vi.waitFor(() => expect(confirmed).toBe(true))
    expect(result.current.isOpen).toBe(false)
  })

  it('handleCancel résout false', async () => {
    const { result } = renderHook(() => useConfirmModal())

    let confirmed: boolean | undefined
    act(() => {
      result.current.confirm().then((v) => { confirmed = v })
    })

    act(() => { result.current.handleCancel() })

    await vi.waitFor(() => expect(confirmed).toBe(false))
  })
})
