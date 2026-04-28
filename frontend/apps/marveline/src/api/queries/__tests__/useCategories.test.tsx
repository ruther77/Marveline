import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createTestQueryClient } from '@/test/test-utils'
import { useCategoriesList } from '../useCategories'

const getCategoriesMock = vi.fn()

vi.mock('../../categories', () => ({
  categoriesApi: {
    getCategories: (...args: unknown[]) => getCategoriesMock(...args),
  },
}))

function createWrapper() {
  const queryClient = createTestQueryClient()

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useCategoriesList', () => {
  beforeEach(() => {
    getCategoriesMock.mockReset()
  })

  it('sépare les caches active_only=true et active_only=false', async () => {
    getCategoriesMock
      .mockResolvedValueOnce([{ id: 1, name: 'Actives' }])
      .mockResolvedValueOnce([{ id: 1, name: 'Actives' }, { id: 2, name: 'Inactives' }])

    const wrapper = createWrapper()

    const first = renderHook(() => useCategoriesList(true), { wrapper })
    await waitFor(() => {
      expect(first.result.current.data).toEqual([{ id: 1, name: 'Actives' }])
    })

    const second = renderHook(() => useCategoriesList(false), { wrapper })
    await waitFor(() => {
      expect(second.result.current.data).toEqual([
        { id: 1, name: 'Actives' },
        { id: 2, name: 'Inactives' },
      ])
    })

    expect(getCategoriesMock).toHaveBeenNthCalledWith(1, true)
    expect(getCategoriesMock).toHaveBeenNthCalledWith(2, false)
    expect(getCategoriesMock).toHaveBeenCalledTimes(2)
  })
})
