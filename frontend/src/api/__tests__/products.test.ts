/**
 * Tests unitaires pour api/products.ts
 * Vérifie CRUD products + pagination + filtres multiples
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { productsApi } from '../products'
import apiClient from '../client'
import type { Product, ProductWithRelations, ProductCreate, ProductUpdate, PaginatedProducts } from '@/types/product'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('API Products - getProducts', () => {
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
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await productsApi.getProducts()

    expect(apiClient.get).toHaveBeenCalledWith('/products', {
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
      items: [{ id: 3, name: 'Produit 3' }],
      total: 45,
      skip: 20,
      limit: 10,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await productsApi.getProducts({ page: 3, page_size: 10 })

    expect(apiClient.get).toHaveBeenCalledWith('/products', {
      params: { skip: 20, limit: 10 },
    })
    expect(result.page).toBe(3)
    expect(result.page_size).toBe(10)
    expect(result.total_pages).toBe(5)
  })

  it('filtre produits par catégorie', async () => {
    const mockResponse = {
      items: [{ id: 1, name: 'Assiette blanche', category: 'assiettes' }],
      total: 1,
      skip: 0,
      limit: 20,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    await productsApi.getProducts({ category: 'assiettes' })

    expect(apiClient.get).toHaveBeenCalledWith('/products', {
      params: { skip: 0, limit: 20, category: 'assiettes' },
    })
  })

  it('filtre produits available_only=true (stock > 0)', async () => {
    const mockResponse = {
      items: [{ id: 1, name: 'Produit disponible', available_quantity: 5 }],
      total: 1,
      skip: 0,
      limit: 20,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    await productsApi.getProducts({ available_only: true })

    expect(apiClient.get).toHaveBeenCalledWith('/products', {
      params: { skip: 0, limit: 20, available_only: true },
    })
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
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    await productsApi.getProducts({ active_only: false })

    expect(apiClient.get).toHaveBeenCalledWith('/products', {
      params: { skip: 0, limit: 20, is_active: false },
    })
  })

  it('gère liste vide (0 produits)', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      skip: 0,
      limit: 20,
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockResponse })

    const result = await productsApi.getProducts()

    expect(result.items).toEqual([])
    expect(result.total).toBe(0)
    expect(result.total_pages).toBe(0)
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
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockProduct })

    const result = await productsApi.getProduct(1)

    expect(apiClient.get).toHaveBeenCalledWith('/products/1')
    expect(result).toEqual(mockProduct)
    expect(result.sku).toBe('TABLE-RONDE-150')
  })

  it('propage les erreurs 404 si produit non trouvé', async () => {
    const error = new Error('Product not found')
    vi.mocked(apiClient.get).mockRejectedValue(error)

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
    vi.mocked(apiClient.post).mockResolvedValue({ data: mockResponse })

    const result = await productsApi.createProduct(newProduct)

    expect(apiClient.post).toHaveBeenCalledWith('/products', newProduct)
    expect(result).toEqual(mockResponse)
    expect(result.id).toBe(5)
  })

  it('propage les erreurs 400 si SKU déjà existant', async () => {
    const error = new Error('Product with SKU already exists')
    vi.mocked(apiClient.post).mockRejectedValue(error)

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
    vi.mocked(apiClient.patch).mockResolvedValue({ data: mockResponse })

    const result = await productsApi.updateProduct(1, updateData)

    expect(apiClient.patch).toHaveBeenCalledWith('/products/1', updateData)
    expect(result.price_per_day_cents).toBe(2500)
    expect(result.stock_quantity).toBe(25)
  })

  it('propage les erreurs 404 si produit non trouvé', async () => {
    const error = new Error('Product not found')
    vi.mocked(apiClient.patch).mockRejectedValue(error)

    await expect(productsApi.updateProduct(999, { name: 'Test' })).rejects.toThrow('Product not found')
  })
})

describe('API Products - deleteProduct', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('supprime un produit (soft delete)', async () => {
    vi.mocked(apiClient.delete).mockResolvedValue({})

    await productsApi.deleteProduct(1)

    expect(apiClient.delete).toHaveBeenCalledWith('/products/1')
  })

  it('propage les erreurs 404 si produit non trouvé', async () => {
    const error = new Error('Product not found')
    vi.mocked(apiClient.delete).mockRejectedValue(error)

    await expect(productsApi.deleteProduct(999)).rejects.toThrow('Product not found')
  })
})
