/**
 * Tests unitaires pour api/product_variants.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { productVariantsApi } from '../product_variants'
import { api } from '../fetchClient'
import type { ProductVariant } from '@/types/product_variant'

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

const mockVariant: ProductVariant = {
  id: 10,
  product_id: 1,
  name: 'Bleu royal',
  sku: 'TABLE-RONDE-BLEU',
  stock_quantity: 5,
  is_active: true,
} as unknown as ProductVariant

describe('productVariantsApi - getVariants', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('retourne un tableau direct', async () => {
    vi.mocked(api.get).mockResolvedValue([mockVariant])

    const result = await productVariantsApi.getVariants(1)

    expect(api.get).toHaveBeenCalledWith('/products/1/variants')
    expect(result).toHaveLength(1)
    expect(result[0].name).toBe('Bleu royal')
  })

  it('retourne items si réponse enveloppée', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [mockVariant] })

    const result = await productVariantsApi.getVariants(1)
    expect(result).toHaveLength(1)
  })

  it('gère liste vide', async () => {
    vi.mocked(api.get).mockResolvedValue([])
    const result = await productVariantsApi.getVariants(1)
    expect(result).toHaveLength(0)
  })
})

describe('productVariantsApi - getVariant', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère une variante par IDs produit + variante', async () => {
    vi.mocked(api.get).mockResolvedValue(mockVariant)

    const result = await productVariantsApi.getVariant(1, 10)

    expect(api.get).toHaveBeenCalledWith('/products/1/variants/10')
    expect(result.id).toBe(10)
  })
})

describe('productVariantsApi - createVariant', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('crée une variante pour un produit', async () => {
    vi.mocked(api.post).mockResolvedValue(mockVariant)

    const result = await productVariantsApi.createVariant(1, { name: 'Bleu royal', sku: 'TABLE-RONDE-BLEU' } as Parameters<typeof productVariantsApi.createVariant>[1])

    expect(api.post).toHaveBeenCalledWith('/products/1/variants', expect.any(Object))
    expect(result.product_id).toBe(1)
  })
})

describe('productVariantsApi - updateVariant', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('met à jour une variante', async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...mockVariant, stock_quantity: 8 })

    const result = await productVariantsApi.updateVariant(1, 10, { stock_quantity: 8 })

    expect(api.patch).toHaveBeenCalledWith('/products/1/variants/10', { stock_quantity: 8 })
    expect(result.stock_quantity).toBe(8)
  })
})

describe('productVariantsApi - deleteVariant', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('supprime une variante', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await productVariantsApi.deleteVariant(1, 10)

    expect(api.delete).toHaveBeenCalledWith('/products/1/variants/10')
  })
})
