/**
 * Tests unitaires pour api/pricing.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { pricingApi } from '../pricing'
import { api } from '../fetchClient'
import type { PricingRule } from '@/types/pricing'

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

const mockRule: PricingRule = {
  id: 1,
  name: 'Weekend +20%',
  rule_type: 'percentage',
  value: 20,
  is_active: true,
} as unknown as PricingRule

describe('pricingApi - list', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('retourne une PaginatedResponse avec les règles', async () => {
    const mockPage = { items: [mockRule], total: 1, skip: 0, limit: 20 }
    vi.mocked(api.get).mockResolvedValue(mockPage)

    const result = await pricingApi.list()

    expect(api.get).toHaveBeenCalledWith('/pricing/rules')
    expect(result.items).toHaveLength(1)
    expect(result.items[0].name).toBe('Weekend +20%')
    expect(result.total).toBe(1)
  })

  it('retourne une PaginatedResponse vide', async () => {
    const mockPage = { items: [], total: 0, skip: 0, limit: 20 }
    vi.mocked(api.get).mockResolvedValue(mockPage)

    const result = await pricingApi.list()
    expect(result.items).toHaveLength(0)
    expect(result.total).toBe(0)
  })
})

describe('pricingApi - get', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère une règle par ID', async () => {
    vi.mocked(api.get).mockResolvedValue(mockRule)

    const result = await pricingApi.get(1)

    expect(api.get).toHaveBeenCalledWith('/pricing/rules/1')
    expect(result.id).toBe(1)
  })
})

describe('pricingApi - create', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('crée une règle de tarification', async () => {
    vi.mocked(api.post).mockResolvedValue(mockRule)

    const result = await pricingApi.create({ name: 'Weekend +20%', rule_type: 'percentage', value: 20 } as Parameters<typeof pricingApi.create>[0])

    expect(api.post).toHaveBeenCalledWith('/pricing/rules', expect.any(Object))
    expect(result.id).toBe(1)
  })
})

describe('pricingApi - update', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('met à jour partiellement une règle', async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...mockRule, value: 25 })

    const result = await pricingApi.update(1, { value: 25 })

    expect(api.patch).toHaveBeenCalledWith('/pricing/rules/1', { value: 25 })
    expect(result.value).toBe(25)
  })
})

describe('pricingApi - delete', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('supprime une règle', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await pricingApi.delete(1)

    expect(api.delete).toHaveBeenCalledWith('/pricing/rules/1')
  })
})

describe('pricingApi - simulate', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('simule un prix avec règle appliquée', async () => {
    vi.mocked(api.post).mockResolvedValue({
      unit_price_cents: 6000,
      total_cents: 12000,
      rule_applied: 'Weekend +20%',
    })

    const result = await pricingApi.simulate({
      product_id: 1,
      quantity: 2,
      date_from: '2026-03-14',
      date_to: '2026-03-15',
    })

    expect(api.post).toHaveBeenCalledWith('/pricing/simulate', expect.any(Object))
    expect(result.total_cents).toBe(12000)
    expect(result.rule_applied).toBe('Weekend +20%')
  })

  it('simule sans règle appliquée', async () => {
    vi.mocked(api.post).mockResolvedValue({ unit_price_cents: 5000, total_cents: 10000 })

    const result = await pricingApi.simulate({ product_id: 1, quantity: 2, date_from: '2026-03-10', date_to: '2026-03-11' })

    expect(result.rule_applied).toBeUndefined()
  })
})
