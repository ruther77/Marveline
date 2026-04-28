/**
 * Tests unitaires pour api/search.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { searchApi } from '../search'
import { api } from '../fetchClient'
import type { SearchResponse } from '@/types/search'

vi.mock('../fetchClient', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  fetchBlob: vi.fn(),
  fetchFormData: vi.fn(),
}))

const mockResponse: SearchResponse = {
  results: [
    { type: 'customer', id: 1, label: 'Dupont SAS', sub: 'client@dupont.fr', url: '/customers/1' },
    { type: 'product', id: 2, label: 'Table ronde', sub: 'REF-002', url: '/catalogue/products/2' },
  ],
  total: 2,
}

describe('searchApi - search', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('effectue une recherche simple', async () => {
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await searchApi.search('dupont')

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain('/search?')
    expect(url).toContain('q=dupont')
    expect(result.results).toHaveLength(2)
    expect(result.total).toBe(2)
  })

  it('inclut le paramètre limit par défaut (20)', async () => {
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    await searchApi.search('table')

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain('limit=20')
  })

  it('applique un limit personnalisé', async () => {
    vi.mocked(api.get).mockResolvedValue({ results: [], total: 0 })

    await searchApi.search('test', undefined, 5)

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain('limit=5')
  })

  it('filtre par types uniques', async () => {
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    await searchApi.search('dupont', ['customer'])

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain('types=customer')
  })

  it('filtre par types multiples', async () => {
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    await searchApi.search('res', ['customer', 'reservation'])

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain('types=customer')
    expect(url).toContain('types=reservation')
  })

  it('n\'ajoute pas "types" si tableau vide', async () => {
    vi.mocked(api.get).mockResolvedValue({ results: [], total: 0 })

    await searchApi.search('test', [])

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).not.toContain('types=')
  })

  it('gère résultats vides', async () => {
    vi.mocked(api.get).mockResolvedValue({ results: [], total: 0 })

    const result = await searchApi.search('inconnu')
    expect(result.results).toHaveLength(0)
    expect(result.total).toBe(0)
  })

  it('propage les erreurs réseau', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Network error'))
    await expect(searchApi.search('test')).rejects.toThrow('Network error')
  })
})
