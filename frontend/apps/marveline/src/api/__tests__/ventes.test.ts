/**
 * Tests unitaires pour api/ventes.ts
 * Vérifie list, get, create, addPayment, refund, cancel
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ventesApi } from '../ventes'
import { api, fetchBlob } from '../fetchClient'
import type { VenteListItem, VenteDetail, VenteDetailFull, VentePayment } from '@/types/vente'

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

const mockItem: VenteListItem = {
  id: 1,
  reference: 'VENTE-0001',
  customer_id: 10,
  customer_name: 'Dupont SAS',
  status: 'pending',
  created_at: '2026-02-10T10:00:00Z',
  total_cents: 150000,
  paid_cents: 0,
  balance_cents: 150000,
}

describe('ventesApi - listVentes', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère liste paginée par défaut', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [mockItem], total: 1, skip: 0, limit: 20 })

    const result = await ventesApi.listVentes()

    expect(api.get).toHaveBeenCalledWith(expect.stringContaining('/ventes?'))
    expect(result.items).toHaveLength(1)
    expect(result.total).toBe(1)
    expect(result.skip).toBe(0)
    expect(result.limit).toBe(20)
  })

  it('applique filtres status, customer_id, dates', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, skip: 5, limit: 5 })

    await ventesApi.listVentes({ status: 'fully_paid', customer_id: 5, date_from: '2026-01-01', date_to: '2026-01-31', skip: 5, limit: 5 })

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain('status=fully_paid')
    expect(url).toContain('customer_id=5')
    expect(url).toContain('date_from=2026-01-01')
    expect(url).toContain('date_to=2026-01-31')
    expect(url).toContain('skip=5')
  })

  it('gère liste vide', async () => {
    vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, skip: 0, limit: 20 })
    const result = await ventesApi.listVentes()
    expect(result.total).toBe(0)
  })
})

describe('ventesApi - get', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère une vente par ID', async () => {
    const full = { ...mockItem, lignes: [] } as unknown as VenteDetailFull
    vi.mocked(api.get).mockResolvedValue(full)

    const result = await ventesApi.get(1)

    expect(api.get).toHaveBeenCalledWith('/ventes/1')
    expect(result.id).toBe(1)
  })

  it('propage les erreurs 404', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Vente introuvable'))
    await expect(ventesApi.get(999)).rejects.toThrow('Vente introuvable')
  })
})

describe('ventesApi - create', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('crée une nouvelle vente avec lignes', async () => {
    const mockDetail = { id: 2, reference: 'VENTE-0002', status: 'pending' } as unknown as VenteDetail
    vi.mocked(api.post).mockResolvedValue(mockDetail)

    const payload = {
      customer_id: 10,
      lines: [{ product_id: 1, label: 'Chaise dorée', quantity: 2, unit_price_cents: 5000 }],
    }
    const result = await ventesApi.create(payload)

    expect(api.post).toHaveBeenCalledWith('/ventes', payload)
    expect(result.id).toBe(2)
  })
})

describe('ventesApi - addPayment', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('ajoute un paiement à une vente', async () => {
    const mockPayment = { id: 1, amount_cents: 60000, payment_method: 'card' } as unknown as VentePayment
    vi.mocked(api.post).mockResolvedValue(mockPayment)

    const result = await ventesApi.addPayment(1, {
      amount_cents: 60000,
      payment_method: 'card',
      payment_date: '2026-03-10',
      is_deposit: true,
    })

    expect(api.post).toHaveBeenCalledWith('/ventes/1/payments', expect.any(Object))
    expect(result.amount_cents).toBe(60000)
  })
})

describe('ventesApi - cancel', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('annule une vente', async () => {
    const mockDetail = { id: 1, status: 'refunded' } as unknown as VenteDetail
    vi.mocked(api.post).mockResolvedValue(mockDetail)

    const result = await ventesApi.cancel(1)

    expect(api.post).toHaveBeenCalledWith('/ventes/1/cancel')
    expect(result.status).toBe('refunded')
  })
})

describe('ventesApi - getPdf', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('télécharge le PDF d\'une vente', async () => {
    const mockBlob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
    vi.mocked(fetchBlob).mockResolvedValue(mockBlob)

    const result = await ventesApi.getPdf(1)

    expect(fetchBlob).toHaveBeenCalledWith('/ventes/1/pdf')
    expect(result).toBeInstanceOf(Blob)
  })
})
