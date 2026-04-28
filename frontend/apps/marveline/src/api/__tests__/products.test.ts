/**
 * Tests unitaires pour api/products.ts
 * Vérifie CRUD products + pagination + filtres multiples
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { productsApi } from '../products'
import { api } from '../fetchClient'
import type { Product, ProductWithRelations, ProductCreate, ProductUpdate, PaginatedProducts, ProductAvailabilityResponse } from '@/types/product'

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

describe('API Products - listProducts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère liste paginée de produits avec paramètres par défaut', async () => {
    const mockResponse = {
      items: [
        { id: 1, name: 'Table ronde', sku: 'TABLE-01', category: 'mobilier' },
        { id: 2, name: 'Chaise Napoléon', sku: 'CHAISE-01', category: 'mobilier' },
      ],
      total: 2,
      skip: 0,
      limit: 20,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await productsApi.listProducts()

    expect(api.get).toHaveBeenCalledWith('/products?skip=0&limit=20')
    expect(result.items).toHaveLength(2)
    expect(result.total).toBe(2)
    expect(result.skip).toBe(0)
    expect(result.limit).toBe(20)
  })

  it('applique pagination avec skip et limit personnalisés', async () => {
    const mockResponse = {
      items: [{ id: 3, name: 'Produit 3' }],
      total: 45,
      skip: 20,
      limit: 10,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await productsApi.listProducts({ skip: 20, limit: 10 })

    expect(api.get).toHaveBeenCalledWith('/products?skip=20&limit=10')
    expect(result.skip).toBe(20)
    expect(result.limit).toBe(10)
  })

  it('filtre produits par catégorie', async () => {
    const mockResponse = {
      items: [{ id: 1, name: 'Assiette blanche', category: 'assiettes' }],
      total: 1,
      skip: 0,
      limit: 20,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    await productsApi.listProducts({ category: 'assiettes' })

    const callArg = vi.mocked(api.get).mock.calls[0][0] as string
    expect(callArg).toContain('category=assiettes')
  })

  it('filtre produits available_only=true (stock > 0)', async () => {
    const mockResponse = {
      items: [{ id: 1, name: 'Produit disponible', available_quantity: 5 }],
      total: 1,
      skip: 0,
      limit: 20,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    await productsApi.listProducts({ available_only: true })

    const callArg = vi.mocked(api.get).mock.calls[0][0] as string
    expect(callArg).toContain('available_only=true')
  })

  it('filtre produits active_only=false (inclure inactifs)', async () => {
    const mockResponse = {
      items: [
        { id: 1, name: 'Produit actif', is_active: true },
        { id: 2, name: 'Produit inactif', is_active: false },
      ],
      total: 2,
      skip: 0,
      limit: 20,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    await productsApi.listProducts({ active_only: false })

    const callArg = vi.mocked(api.get).mock.calls[0][0] as string
    expect(callArg).toContain('is_active=false')
  })

  it('gère liste vide (0 produits)', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      skip: 0,
      limit: 20,
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await productsApi.listProducts()

    expect(result.items).toEqual([])
    expect(result.total).toBe(0)
  })
})

describe('API Products - getProduct', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère un produit par ID avec relations', async () => {
    const mockProduct: ProductWithRelations = {
      id: 1,
      name: 'Table ronde 150cm',
      sku: 'TABLE-RONDE-150',
      category: 'mobilier',
      description: 'Table pour 8 personnes',
      price_per_day_cents: 2000,
      price_per_day_euros: 20,
      deposit_amount_cents: 5000,
      deposit_amount_euros: 50,
      stock_quantity: 10,
      available_quantity: 7,
      condition: 'excellent',
      image_url: 'https://example.com/table.jpg',
      is_active: true,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }
    vi.mocked(api.get).mockResolvedValue(mockProduct)

    const result = await productsApi.getProduct(1)

    expect(api.get).toHaveBeenCalledWith('/products/1')
    expect(result).toEqual(mockProduct)
    expect(result.sku).toBe('TABLE-RONDE-150')
  })

  it('propage les erreurs 404 si produit non trouvé', async () => {
    const error = new Error('Product not found')
    vi.mocked(api.get).mockRejectedValue(error)

    await expect(productsApi.getProduct(999)).rejects.toThrow('Product not found')
  })
})

describe('API Products - createProduct', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('crée un nouveau produit', async () => {
    const newProduct: ProductCreate = {
      name: 'Nouveau Produit',
      sku: 'NEW-PROD-01',
      category: 'mobilier',
      description: 'Description nouveau produit',
      price_per_day_cents: 1500,
      deposit_amount_cents: 3000,
      stock_quantity: 20,
      available_quantity: 20,
      condition: 'excellent',
    }
    const mockResponse: Product = {
      id: 5,
      name: 'Nouveau Produit',
      sku: 'NEW-PROD-01',
      category: 'mobilier',
      description: 'Description nouveau produit',
      price_per_day_cents: 1500,
      price_per_day_euros: 15,
      deposit_amount_cents: 3000,
      deposit_amount_euros: 30,
      stock_quantity: 20,
      available_quantity: 20,
      condition: 'excellent',
      image_url: null,
      is_active: true,
      tenant_id: 1,
      created_at: '2026-02-16T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(api.post).mockResolvedValue(mockResponse)

    const result = await productsApi.createProduct(newProduct)

    expect(api.post).toHaveBeenCalledWith('/products', newProduct)
    expect(result).toEqual(mockResponse)
    expect(result.id).toBe(5)
  })

  it('propage les erreurs 400 si SKU déjà existant', async () => {
    const error = new Error('Product with SKU already exists')
    vi.mocked(api.post).mockRejectedValue(error)

    const newProduct: ProductCreate = {
      name: 'Produit',
      sku: 'DUPLICATE-SKU',
      category: 'mobilier',
      price_per_day_cents: 1000,
      deposit_amount_cents: 2000,
      stock_quantity: 10,
      available_quantity: 10,
    }

    await expect(productsApi.createProduct(newProduct)).rejects.toThrow('Product with SKU already exists')
  })
})

describe('API Products - updateProduct', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('met à jour un produit existant (PATCH partiel)', async () => {
    const updateData: ProductUpdate = {
      price_per_day_cents: 2500,
      stock_quantity: 25,
    }
    const mockResponse: Product = {
      id: 1,
      name: 'Table ronde 150cm',
      sku: 'TABLE-RONDE-150',
      category: 'mobilier',
      description: 'Table pour 8 personnes',
      price_per_day_cents: 2500,
      price_per_day_euros: 25,
      deposit_amount_cents: 5000,
      deposit_amount_euros: 50,
      stock_quantity: 25,
      available_quantity: 7,
      condition: 'excellent',
      image_url: null,
      is_active: true,
      tenant_id: 1,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-02-16T00:00:00Z',
    }
    vi.mocked(api.patch).mockResolvedValue(mockResponse)

    const result = await productsApi.updateProduct(1, updateData)

    expect(api.patch).toHaveBeenCalledWith('/products/1', updateData)
    expect(result.price_per_day_cents).toBe(2500)
    expect(result.stock_quantity).toBe(25)
  })

  it('propage les erreurs 404 si produit non trouvé', async () => {
    const error = new Error('Product not found')
    vi.mocked(api.patch).mockRejectedValue(error)

    await expect(productsApi.updateProduct(999, { name: 'Test' })).rejects.toThrow('Product not found')
  })
})

describe('API Products - deleteProduct', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('supprime un produit (soft delete)', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await productsApi.deleteProduct(1)

    expect(api.delete).toHaveBeenCalledWith('/products/1')
  })

  it('propage les erreurs 404 si produit non trouvé', async () => {
    const error = new Error('Product not found')
    vi.mocked(api.delete).mockRejectedValue(error)

    await expect(productsApi.deleteProduct(999)).rejects.toThrow('Product not found')
  })
})

describe('API Products - getAvailability', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('appelle GET /products/{id}/availability avec dates', async () => {
    const mockResponse: ProductAvailabilityResponse = {
      product_id: 1,
      total_quantity: 5,
      date_from: '2026-03-01',
      date_to: '2026-03-31',
      busy_slots: [
        {
          date_from: '2026-03-10',
          date_to: '2026-03-12',
          reserved_quantity: 2,
          reservation_id: 42,
          reservation_ref: 'RES-0042',
        },
      ],
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await productsApi.getAvailability(1, '2026-03-01', '2026-03-31')

    expect(api.get).toHaveBeenCalledWith(
      '/products/1/availability?date_from=2026-03-01&date_to=2026-03-31',
    )
    expect(result.product_id).toBe(1)
    expect(result.total_quantity).toBe(5)
    expect(result.busy_slots).toHaveLength(1)
    expect(result.busy_slots[0].reservation_ref).toBe('RES-0042')
  })

  it('retourne une liste vide de busy_slots si produit disponible', async () => {
    const mockResponse: ProductAvailabilityResponse = {
      product_id: 2,
      total_quantity: 10,
      date_from: '2026-04-01',
      date_to: '2026-04-30',
      busy_slots: [],
    }
    vi.mocked(api.get).mockResolvedValue(mockResponse)

    const result = await productsApi.getAvailability(2, '2026-04-01', '2026-04-30')

    expect(result.busy_slots).toHaveLength(0)
  })

  it('propage les erreurs 404 si produit non trouvé', async () => {
    const error = new Error('Produit introuvable')
    vi.mocked(api.get).mockRejectedValue(error)

    await expect(
      productsApi.getAvailability(999, '2026-03-01', '2026-03-31'),
    ).rejects.toThrow('Produit introuvable')
  })
})

describe('API Products - maintenances / images / audit', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('liste les maintenances d\'un produit', async () => {
    vi.mocked(api.get).mockResolvedValue([{ id: 1, product_id: 1 }])

    const result = await productsApi.listMaintenances(1)

    expect(api.get).toHaveBeenCalledWith('/products/1/maintenances')
    expect(result).toHaveLength(1)
  })

  it('crée une maintenance', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 2, product_id: 1, scheduled_date: '2026-04-01' })

    await productsApi.createMaintenance(1, { scheduled_date: '2026-04-01' } as Parameters<typeof productsApi.createMaintenance>[1])

    expect(api.post).toHaveBeenCalledWith('/products/1/maintenances', expect.any(Object))
  })

  it('supprime une maintenance', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await productsApi.deleteMaintenance(1, 2)

    expect(api.delete).toHaveBeenCalledWith('/products/1/maintenances/2')
  })

  it('liste les images', async () => {
    vi.mocked(api.get).mockResolvedValue([{ id: 1, url: 'https://cdn.example.com/img.jpg', is_primary: true }])

    const result = await productsApi.listImages(1)

    expect(api.get).toHaveBeenCalledWith('/products/1/images')
    expect(result).toHaveLength(1)
  })

  it('supprime une image', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await productsApi.deleteImage(1, 3)

    expect(api.delete).toHaveBeenCalledWith('/products/1/images/3')
  })

  it('définit l\'image principale', async () => {
    vi.mocked(api.patch).mockResolvedValue({ id: 3, is_primary: true })

    await productsApi.setPrimaryImage(1, 3)

    expect(api.patch).toHaveBeenCalledWith('/products/1/images/3/set-primary', {})
  })

  it('récupère l\'audit d\'un produit', async () => {
    vi.mocked(api.get).mockResolvedValue([{ action: 'update', created_at: '2026-02-10T10:00:00' }])

    const result = await productsApi.getProductAudit(1)

    expect(api.get).toHaveBeenCalledWith('/products/1/audit?limit=50')
    expect(result).toHaveLength(1)
  })

  it('crée un produit', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 5, name: 'Nouveau produit' })

    await productsApi.createProduct({ name: 'Nouveau produit' } as Parameters<typeof productsApi.createProduct>[0])

    expect(api.post).toHaveBeenCalledWith('/products', expect.any(Object))
  })

  it('met à jour un produit', async () => {
    vi.mocked(api.patch).mockResolvedValue({ id: 1, name: 'Produit modifié' })

    await productsApi.updateProduct(1, { name: 'Produit modifié' })

    expect(api.patch).toHaveBeenCalledWith('/products/1', expect.any(Object))
  })

  it('supprime un produit', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await productsApi.deleteProduct(1)

    expect(api.delete).toHaveBeenCalledWith('/products/1')
  })
})
