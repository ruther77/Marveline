/**
 * Tests unitaires pour api/bundles.ts
 * Vérifie CRUD bundles + items + calcul prix
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { bundlesApi } from '../bundles'
import apiClient from '../client'
import type { Bundle, BundleWithItems, BundleCreate, BundleUpdate, BundleItem, BundleItemCreate, PaginatedBundles, BundlePriceCalc } from '@/types/product'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('API Bundles - getBundles', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère liste paginée de bundles avec paramètres par défaut', async () => {
    const mockResponse = {
      items: [
        { id: 1, name: 'Bundle Mariage', featured: true },
        { id: 2, name: 'Bundle Anniversaire', featured: false },
      ],
      total: 2,
      skip: 0,
      limit: 20,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await bundlesApi.getBundles()

    expect(apiClient.get).toHaveBeenCalledWith('/bundles', {
      params: { skip: 0, limit: 20 },
    })
    expect(result.items).toHaveLength(2)
    expect(result.total).toBe(2)
    expect(result.page).toBe(1)
    expect(result.page_size).toBe(20)
    expect(result.total_pages).toBe(1)
  })

  it('applique pagination avec page et page_size personnalisés', async () => {
    const mockResponse = {
      items: [{ id: 3, name: 'Bundle 3' }],
      total: 25,
      skip: 10,
      limit: 10,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await bundlesApi.getBundles({ page: 2, page_size: 10 })

    expect(apiClient.get).toHaveBeenCalledWith('/bundles', {
      params: { skip: 10, limit: 10 },
    })
    expect(result.page).toBe(2)
    expect(result.page_size).toBe(10)
    expect(result.total_pages).toBe(3)
  })

  it('filtre bundles featured=true', async () => {
    const mockResponse = {
      items: [{ id: 1, name: 'Bundle Featured', featured: true }],
      total: 1,
      skip: 0,
      limit: 20,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    await bundlesApi.getBundles({ featured: true })

    expect(apiClient.get).toHaveBeenCalledWith('/bundles', {
      params: { skip: 0, limit: 20, featured: true },
    })
  })

  it('filtre bundles active_only=true', async () => {
    const mockResponse = {
      items: [{ id: 1, name: 'Bundle Actif' }],
      total: 1,
      skip: 0,
      limit: 20,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    await bundlesApi.getBundles({ active_only: true })

    expect(apiClient.get).toHaveBeenCalledWith('/bundles', {
      params: { skip: 0, limit: 20, active_only: true },
    })
  })

  it('gère liste vide (0 bundles)', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      skip: 0,
      limit: 20,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await bundlesApi.getBundles()

    expect(result.items).toEqual([])
    expect(result.total).toBe(0)
    expect(result.total_pages).toBe(0)
  })
})

describe('API Bundles - getBundle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère un bundle par ID avec items', async () => {
    const mockBundle: BundleWithItems = {
      id: 1,
      name: 'Bundle Complet',
      slug: 'bundle-complet',
      description: 'Description',
      bundle_price_cents: 50000,
      bundle_price_euros: 500,
      cleaning_fee_cents: 5000,
      cleaning_fee_euros: 50,
      featured: true,
      image_url: 'https://example.com/image.jpg',
      is_active: true,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      items: [
        {
          id: 1,
          bundle_id: 1,
          product_id: 10,
          quantity: 5,
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockBundle })

    const result = await bundlesApi.getBundle(1)

    expect(apiClient.get).toHaveBeenCalledWith('/bundles/1')
    expect(result).toEqual(mockBundle)
    expect(result.items).toHaveLength(1)
  })

  it('propage les erreurs 404 si bundle non trouvé', async () => {
    const error = new Error('Bundle not found')
    vi.mocked(apiClient.get).mockRejectedValue(error)

    await expect(bundlesApi.getBundle(999)).rejects.toThrow('Bundle not found')
  })
})

describe('API Bundles - createBundle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('crée un nouveau bundle', async () => {
    const newBundle: BundleCreate = {
      name: 'Nouveau Bundle',
      description: 'Description nouveau',
      bundle_price_cents: 30000,
      cleaning_fee_cents: 3000,
      featured: false,
    }
    const mockResponse: Bundle = {
      id: 5,
      name: 'Nouveau Bundle',
      slug: 'nouveau-bundle',
      description: 'Description nouveau',
      bundle_price_cents: 30000,
      bundle_price_euros: 300,
      cleaning_fee_cents: 3000,
      cleaning_fee_euros: 30,
      featured: false,
      image_url: null,
      is_active: true,
      tenant_id: 1,
      created_at: '2026-02-16T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await bundlesApi.createBundle(newBundle)

    expect(apiClient.post).toHaveBeenCalledWith('/bundles', newBundle)
    expect(result).toEqual(mockResponse)
    expect(result.id).toBe(5)
  })

  it('propage les erreurs 403 si non autorisé', async () => {
    const error = new Error('Forbidden')
    vi.mocked(apiClient.post).mockRejectedValue(error)

    const newBundle: BundleCreate = {
      name: 'Bundle',
      bundle_price_cents: 10000,
      cleaning_fee_cents: 1000,
    }

    await expect(bundlesApi.createBundle(newBundle)).rejects.toThrow('Forbidden')
  })
})

describe('API Bundles - updateBundle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('met à jour un bundle existant (PATCH partiel)', async () => {
    const updateData: BundleUpdate = {
      name: 'Bundle Modifié',
      featured: true,
    }
    const mockResponse: Bundle = {
      id: 1,
      name: 'Bundle Modifié',
      slug: 'bundle-modifie',
      description: 'Description originale',
      bundle_price_cents: 40000,
      bundle_price_euros: 400,
      cleaning_fee_cents: 4000,
      cleaning_fee_euros: 40,
      featured: true,
      image_url: null,
      is_active: true,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(apiClient.patch).mockResolvedValue({ data: mockResponse })

    const result = await bundlesApi.updateBundle(1, updateData)

    expect(apiClient.patch).toHaveBeenCalledWith('/bundles/1', updateData)
    expect(result.name).toBe('Bundle Modifié')
    expect(result.featured).toBe(true)
  })

  it('propage les erreurs 404 si bundle non trouvé', async () => {
    const error = new Error('Bundle not found')
    vi.mocked(apiClient.patch).mockRejectedValue(error)

    await expect(bundlesApi.updateBundle(999, { name: 'Test' })).rejects.toThrow('Bundle not found')
  })
})

describe('API Bundles - deleteBundle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('supprime un bundle (soft delete)', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({})

    await bundlesApi.deleteBundle(1)

    expect(apiClient.delete).toHaveBeenCalledWith('/bundles/1')
  })

  it('propage les erreurs 404 si bundle non trouvé', async () => {
    const error = new Error('Bundle not found')
    vi.mocked(apiClient.delete).mockRejectedValue(error)

    await expect(bundlesApi.deleteBundle(999)).rejects.toThrow('Bundle not found')
  })
})

describe('API Bundles - Items Management', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ajoute un item à un bundle', async () => {
    const newItem: BundleItemCreate = {
      product_id: 20,
      quantity: 10,
    }
    const mockResponse: BundleItem = {
      id: 3,
      bundle_id: 1,
      product_id: 20,
      quantity: 10,
      created_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await bundlesApi.addItem(1, newItem)

    expect(apiClient.post).toHaveBeenCalledWith('/bundles/1/items', newItem)
    expect(result).toEqual(mockResponse)
  })

  it('met à jour la quantité d\'un item', async () => {
    const mockResponse: BundleItem = {
      id: 3,
      bundle_id: 1,
      product_id: 20,
      quantity: 15,
      created_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(apiClient.patch).mockResolvedValue({ data: mockResponse })

    const result = await bundlesApi.updateItem(1, 3, { quantity: 15 })

    expect(apiClient.patch).toHaveBeenCalledWith('/bundles/1/items/3', { quantity: 15 })
    expect(result.quantity).toBe(15)
  })

  it('supprime un item d\'un bundle', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({})

    await bundlesApi.removeItem(1, 3)

    expect(apiClient.delete).toHaveBeenCalledWith('/bundles/1/items/3')
  })

  it('propage les erreurs 404 si item non trouvé lors de la suppression', async () => {
    const error = new Error('Bundle item not found')
    vi.mocked(apiClient.delete).mockRejectedValue(error)

    await expect(bundlesApi.removeItem(1, 999)).rejects.toThrow('Bundle item not found')
  })
})

describe('API Bundles - Calculate Price', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calcule le prix total d\'un bundle avec items', async () => {
    const mockCalc: BundlePriceCalc = {
      bundle_price_cents: 50000,
      bundle_price_euros: 500,
      cleaning_fee_cents: 5000,
      cleaning_fee_euros: 50,
      total_cents: 55000,
      total_euros: 550,
      items_count: 5,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockCalc })

    const result = await bundlesApi.calculatePrice(1)

    expect(apiClient.get).toHaveBeenCalledWith('/bundles/1/calculate-price')
    expect(result.total_euros).toBe(550)
    expect(result.items_count).toBe(5)
  })

  it('propage les erreurs 404 si bundle non trouvé pour calcul', async () => {
    const error = new Error('Bundle not found')
    vi.mocked(apiClient.get).mockRejectedValue(error)

    await expect(bundlesApi.calculatePrice(999)).rejects.toThrow('Bundle not found')
  })
})
