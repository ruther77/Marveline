/**
 * Tests unitaires pour api/collections.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { collectionsApi } from '../collections'
import { api } from '../fetchClient'
import type { Collection, CollectionWithProducts, CollectionListResponse } from '@/types/collection'

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

const mockCollection: Collection = {
  id: 1,
  name: 'Mariage champêtre',
  description: 'Collection mariage',
  is_active: true,
} as unknown as Collection

const mockWithProducts: CollectionWithProducts = {
  ...mockCollection,
  products: [],
} as unknown as CollectionWithProducts

describe('collectionsApi - list', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère la liste sans paramètres', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [mockCollection], total: 1 } as unknown as CollectionListResponse)

    const result = await collectionsApi.list()

    expect(api.get).toHaveBeenCalledWith('/collections')
    expect(result.total).toBe(1)
  })

  it('applique pagination (skip + limit)', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0 } as unknown as CollectionListResponse)

    await collectionsApi.list({ skip: 10, limit: 5 })

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain('skip=10')
    expect(url).toContain('limit=5')
  })
})

describe('collectionsApi - get', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère une collection avec ses produits', async () => {
    vi.mocked(api.get).mockResolvedValue(mockWithProducts)

    const result = await collectionsApi.get(1)

    expect(api.get).toHaveBeenCalledWith('/collections/1')
    expect(result.id).toBe(1)
  })
})

describe('collectionsApi - create / update / delete', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('crée une collection', async () => {
    vi.mocked(api.post).mockResolvedValue(mockCollection)

    const result = await collectionsApi.create({ name: 'Mariage champêtre' } as Parameters<typeof collectionsApi.create>[0])

    expect(api.post).toHaveBeenCalledWith('/collections', expect.any(Object))
    expect(result.name).toBe('Mariage champêtre')
  })

  it('met à jour une collection', async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...mockCollection, name: 'Mariage bohème' })

    const result = await collectionsApi.update(1, { name: 'Mariage bohème' })

    expect(api.patch).toHaveBeenCalledWith('/collections/1', { name: 'Mariage bohème' })
    expect(result.name).toBe('Mariage bohème')
  })

  it('supprime une collection', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await collectionsApi.delete(1)

    expect(api.delete).toHaveBeenCalledWith('/collections/1')
  })
})

describe('collectionsApi - produits', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('ajoute des produits à une collection', async () => {
    vi.mocked(api.post).mockResolvedValue(mockWithProducts)

    await collectionsApi.addProducts(1, [3, 5, 7])

    expect(api.post).toHaveBeenCalledWith('/collections/1/products', { product_ids: [3, 5, 7] })
  })

  it('retire un produit d\'une collection', async () => {
    vi.mocked(api.delete).mockResolvedValue(mockWithProducts)

    await collectionsApi.removeProduct(1, 5)

    expect(api.delete).toHaveBeenCalledWith('/collections/1/products/5')
  })
})
