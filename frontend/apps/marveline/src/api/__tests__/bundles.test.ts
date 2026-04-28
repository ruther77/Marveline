/**
 * Tests unitaires pour api/bundles.ts
 * Vérifie CRUD bundles + items + calcul prix
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { bundlesApi } from '../bundles'
import { api } from '../fetchClient'
import type { BundleCreate, BundleUpdate, BundleItemCreate, BundlePriceCalc } from '@/types/product'

// Mock fetchClient
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

describe('API Bundles - listBundles', () => {
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
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await bundlesApi.listBundles()

    expect(api.get).toHaveBeenCalledWith('/bundles?skip=0&limit=20')
    expect(result.items).toHaveLength(2)
    expect(result.total).toBe(2)
    expect(result.skip).toBe(0)
    expect(result.limit).toBe(20)
  })

  it('applique pagination avec skip et limit personnalisés', async () => {
    const mockResponse = {
      items: [{ id: 3, name: 'Bundle 3' }],
      total: 25,
      skip: 10,
      limit: 10,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await bundlesApi.listBundles({ skip: 10, limit: 10 })

    expect(api.get).toHaveBeenCalledWith('/bundles?skip=10&limit=10')
    expect(result.skip).toBe(10)
    expect(result.limit).toBe(10)
  })

  it('filtre bundles featured=true', async () => {
    const mockResponse = {
      items: [{ id: 1, name: 'Bundle Featured', featured: true }],
      total: 1,
      skip: 0,
      limit: 20,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    await bundlesApi.listBundles({ featured: true })

    const callArg = vi.mocked(api.get).mock.calls[0][0] as string
    expect(callArg).toContain('featured=true')
  })

  it('filtre bundles active_only=true', async () => {
    const mockResponse = {
      items: [{ id: 1, name: 'Bundle Actif' }],
      total: 1,
      skip: 0,
      limit: 20,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    await bundlesApi.listBundles({ active_only: true })

    const callArg = vi.mocked(api.get).mock.calls[0][0] as string
    expect(callArg).toContain('active_only=true')
  })

  it('gère liste vide (0 bundles)', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      skip: 0,
      limit: 20,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await bundlesApi.listBundles()

    expect(result.items).toEqual([])
    expect(result.total).toBe(0)
  })
})

describe('API Bundles - getBundle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère un bundle par ID avec items', async () => {
    const mockBundle = {
      id: 1,
      name: 'Bundle Complet',
      slug: 'bundle-complet',
      description: 'Description',
      bundle_price_cents: 50000,
      bundle_price_euros: 500,
      cleaning_fee_cents: 5000,
      cleaning_fee_euros: 50,
      featured: true,
      display_order: 0,
      image_url: 'https://example.com/image.jpg',
      is_active: true,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      total_items: 1,
      individual_price_cents: 62500,
      savings_cents: 12500,
      individual_price_euros: 625,
      savings_euros: 125,
      items: [
        {
          id: 1,
          bundle_id: 1,
          product_id: 10,
          quantity: 5,
          display_order: 0,
          product: {
            id: 10,
            tenant_id: 1,
            name: 'Assiette',
            sku: 'ASS-01',
            category: 'assiette',
            price_per_day_cents: 250,
            stock_quantity: 100,
            available_quantity: 80,
            condition: 'bon',
            image_url: null,
            is_active: true,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
            tva_rate: 0.20,
            price_per_day_euros: 2.50,
            is_available: true,
          },
        },
      ],
    }
    vi.mocked(api.get).mockResolvedValue(mockBundle)

    const result = await bundlesApi.getBundle(1)

    expect(api.get).toHaveBeenCalledWith('/bundles/1')
    expect(result).toEqual(mockBundle)
    expect(result.items).toHaveLength(1)
  })

  it('propage les erreurs 404 si bundle non trouvé', async () => {
    const error = new Error('Bundle not found')
    vi.mocked(api.get).mockRejectedValue(error)

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
    const mockResponse = {
      id: 5,
      name: 'Nouveau Bundle',
      slug: 'nouveau-bundle',
      description: 'Description nouveau',
      bundle_price_cents: 30000,
      bundle_price_euros: 300,
      cleaning_fee_cents: 3000,
      cleaning_fee_euros: 30,
      featured: false,
      display_order: 0,
      image_url: null,
      is_active: true,
      tenant_id: 1,
      created_at: '2026-02-16T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const result = await bundlesApi.createBundle(newBundle)

    expect(api.post).toHaveBeenCalledWith('/bundles', newBundle)
    expect(result).toEqual(mockResponse)
    expect(result.id).toBe(5)
  })

  it('propage les erreurs 403 si non autorisé', async () => {
    const error = new Error('Forbidden')
    vi.mocked(api.post).mockRejectedValue(error)

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
    const mockResponse = {
      id: 1,
      name: 'Bundle Modifié',
      slug: 'bundle-modifie',
      description: 'Description originale',
      bundle_price_cents: 40000,
      bundle_price_euros: 400,
      cleaning_fee_cents: 4000,
      cleaning_fee_euros: 40,
      featured: true,
      display_order: 0,
      image_url: null,
      is_active: true,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(api.patch).mockResolvedValue(mockResponse)

    const result = await bundlesApi.updateBundle(1, updateData)

    expect(api.patch).toHaveBeenCalledWith('/bundles/1', updateData)
    expect(result.name).toBe('Bundle Modifié')
    expect(result.featured).toBe(true)
  })

  it('propage les erreurs 404 si bundle non trouvé', async () => {
    const error = new Error('Bundle not found')
    vi.mocked(api.patch).mockRejectedValue(error)

    await expect(bundlesApi.updateBundle(999, { name: 'Test' })).rejects.toThrow('Bundle not found')
  })
})

describe('API Bundles - deleteBundle', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('supprime un bundle (soft delete)', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await bundlesApi.deleteBundle(1)

    expect(api.delete).toHaveBeenCalledWith('/bundles/1')
  })

  it('propage les erreurs 404 si bundle non trouvé', async () => {
    const error = new Error('Bundle not found')
    vi.mocked(api.delete).mockRejectedValue(error)

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
    const mockResponse = {
      id: 3,
      bundle_id: 1,
      product_id: 20,
      quantity: 10,
      display_order: 0,
      product: {
        id: 20,
        tenant_id: 1,
        name: 'Verre',
        sku: 'VER-01',
        category: 'verre',
        price_per_day_cents: 150,
        stock_quantity: 200,
        available_quantity: 180,
        condition: 'bon',
        image_url: null,
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        tva_rate: 0.20,
        price_per_day_euros: 1.50,
        is_available: true,
      },
    }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const result = await bundlesApi.addItem(1, newItem)

    expect(api.post).toHaveBeenCalledWith('/bundles/1/items', newItem)
    expect(result).toEqual(mockResponse)
  })

  it('met à jour la quantité d\'un item', async () => {
    const mockResponse = {
      id: 3,
      bundle_id: 1,
      product_id: 20,
      quantity: 15,
      display_order: 0,
      product: {
        id: 20,
        tenant_id: 1,
        name: 'Verre',
        sku: 'VER-01',
        category: 'verre',
        price_per_day_cents: 150,
        stock_quantity: 200,
        available_quantity: 180,
        condition: 'bon',
        image_url: null,
        is_active: true,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
        tva_rate: 0.20,
        price_per_day_euros: 1.50,
        is_available: true,
      },
    }
    vi.mocked(api.patch).mockResolvedValue(mockResponse)

    const result = await bundlesApi.updateItem(1, 3, { quantity: 15 })

    expect(api.patch).toHaveBeenCalledWith('/bundles/1/items/3', { quantity: 15 })
    expect(result.quantity).toBe(15)
  })

  it('supprime un item d\'un bundle', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await bundlesApi.removeItem(1, 3)

    expect(api.delete).toHaveBeenCalledWith('/bundles/1/items/3')
  })

  it('propage les erreurs 404 si item non trouvé lors de la suppression', async () => {
    const error = new Error('Bundle item not found')
    vi.mocked(api.delete).mockRejectedValue(error)

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
      individual_price_cents: 62500,
      savings_cents: 12500,
      savings_percent: 20.0,
      items: [
        { product_id: 10, product_name: 'Assiette', quantity: 5, unit_price_cents: 250, line_total_cents: 1250 },
      ],
    }
    vi.mocked(api.get).mockResolvedValue(mockCalc)

    const result = await bundlesApi.calculatePrice(1)

    expect(api.get).toHaveBeenCalledWith('/bundles/1/calculate-price')
    expect(result.bundle_price_cents).toBe(50000)
    expect(result.savings_cents).toBe(12500)
    expect(result.savings_percent).toBe(20.0)
  })

  it('propage les erreurs 404 si bundle non trouvé pour calcul', async () => {
    const error = new Error('Bundle not found')
    vi.mocked(api.get).mockRejectedValue(error)

    await expect(bundlesApi.calculatePrice(999)).rejects.toThrow('Bundle not found')
  })
})
