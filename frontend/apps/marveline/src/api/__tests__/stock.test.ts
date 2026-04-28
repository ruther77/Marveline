/**
 * Tests unitaires pour api/stock.ts
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { stockApi } from '../stock'
import { api } from '../fetchClient'
import type { InventaireSessionResponse, StockAdjustmentResponse, StockLevelItem, ReorderItem } from '@/types/stock_management'

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

const mockSession = { id: 1, status: 'in_progress', entries: [] } as unknown as InventaireSessionResponse

describe('stockApi - inventaire', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('démarre un inventaire', async () => {
    vi.mocked(api.post).mockResolvedValue(mockSession)

    const result = await stockApi.startInventaire()

    expect(api.post).toHaveBeenCalledWith('/stock/inventaire')
    expect(result.status).toBe('in_progress')
  })

  it('récupère une session d\'inventaire', async () => {
    vi.mocked(api.get).mockResolvedValue(mockSession)

    const result = await stockApi.getInventaire(1)

    expect(api.get).toHaveBeenCalledWith('/stock/inventaire/1')
    expect(result.id).toBe(1)
  })

  it('met à jour les comptages', async () => {
    vi.mocked(api.patch).mockResolvedValue(mockSession)

    await stockApi.updateInventaire(1, [{ product_id: 3, counted_quantity: 10 }])

    expect(api.patch).toHaveBeenCalledWith('/stock/inventaire/1', {
      entries: [{ product_id: 3, counted_quantity: 10 }],
    })
  })

  it('finalise un inventaire', async () => {
    vi.mocked(api.post).mockResolvedValue({ ...mockSession, status: 'completed' })

    const result = await stockApi.completeInventaire(1)

    expect(api.post).toHaveBeenCalledWith('/stock/inventaire/1/complete')
    expect(result.status).toBe('completed')
  })
})

describe('stockApi - ajustements', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('liste les ajustements sans filtre', async () => {
    vi.mocked(api.get).mockResolvedValue([])

    await stockApi.listAdjustments()

    expect(api.get).toHaveBeenCalledWith('/stock/adjustments')
  })

  it('liste les ajustements par product_id', async () => {
    vi.mocked(api.get).mockResolvedValue([])

    await stockApi.listAdjustments(5)

    expect(api.get).toHaveBeenCalledWith('/stock/adjustments?product_id=5')
  })

  it('crée un ajustement', async () => {
    const mockAdj = { id: 1, product_id: 5, delta: -2 } as unknown as StockAdjustmentResponse
    vi.mocked(api.post).mockResolvedValue(mockAdj)

    const result = await stockApi.createAdjustment({ product_id: 5, delta: -2, reason: 'Casse' } as Parameters<typeof stockApi.createAdjustment>[0])

    expect(api.post).toHaveBeenCalledWith('/stock/adjustments', expect.any(Object))
    expect(result.product_id).toBe(5)
  })
})

describe('stockApi - niveaux et réassort', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère les niveaux de stock', async () => {
    vi.mocked(api.get).mockResolvedValue([{ product_id: 1, current_stock: 8 }] as unknown as StockLevelItem[])

    const result = await stockApi.getLevels()

    expect(api.get).toHaveBeenCalledWith('/stock/levels')
    expect(result).toHaveLength(1)
  })

  it('récupère la liste de réassort', async () => {
    vi.mocked(api.get).mockResolvedValue([{ product_id: 3, suggested_quantity: 20 }] as unknown as ReorderItem[])

    const result = await stockApi.getReorderList()

    expect(api.get).toHaveBeenCalledWith('/stock/reorder')
    expect(result[0].suggested_quantity).toBe(20)
  })

  it('récupère la couverture de stock', async () => {
    vi.mocked(api.get).mockResolvedValue({ coverage_days: 45, at_risk: [] })

    const result = await stockApi.getCoverage()

    expect(api.get).toHaveBeenCalledWith('/stock/coverage')
    expect(result.coverage_days).toBe(45)
  })
})
