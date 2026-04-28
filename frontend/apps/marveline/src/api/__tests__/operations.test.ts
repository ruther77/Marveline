/**
 * Tests unitaires pour api/operations.ts
 * Vérifie départ, retour, QR, photos
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { operationsApi } from '../operations'
import { api } from '../fetchClient'
import type { DepartureState, ReturnState, DamageReportResponse, QrResult } from '@/types/operations'

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

const mockDeparture = { reservation_id: 1, status: 'pending', items: [] } as unknown as DepartureState
const mockReturn = { reservation_id: 1, status: 'pending', items: [] } as unknown as ReturnState

describe('operationsApi - départ', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère l\'état de départ d\'une réservation', async () => {
    vi.mocked(api.get).mockResolvedValue(mockDeparture)

    const result = await operationsApi.getDepartureState(1)

    expect(api.get).toHaveBeenCalledWith('/operations/departure/1')
    expect(result.reservation_id).toBe(1)
  })

  it('valide un départ sans items ni signature', async () => {
    vi.mocked(api.post).mockResolvedValue({ ...mockDeparture, status: 'validated' })

    await operationsApi.validateDeparture(1)

    expect(api.post).toHaveBeenCalledWith('/operations/departure/1', {
      signature_url: null,
      items: [],
    })
  })

  it('valide un départ avec signature', async () => {
    vi.mocked(api.post).mockResolvedValue(mockDeparture)

    await operationsApi.validateDeparture(1, [], 'https://cdn.example.com/sig.png')

    expect(api.post).toHaveBeenCalledWith('/operations/departure/1', {
      signature_url: 'https://cdn.example.com/sig.png',
      items: [],
    })
  })

  it('bloque un départ', async () => {
    vi.mocked(api.post).mockResolvedValue({ ...mockDeparture, status: 'blocked' })

    await operationsApi.blockDeparture(1, { reason: 'Paiement manquant', item_ids: [3] })

    expect(api.post).toHaveBeenCalledWith('/operations/departure/1/block', {
      reason: 'Paiement manquant',
      item_ids: [3],
    })
  })
})

describe('operationsApi - retour', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('récupère l\'état de retour', async () => {
    vi.mocked(api.get).mockResolvedValue(mockReturn)

    const result = await operationsApi.getReturnState(1)

    expect(api.get).toHaveBeenCalledWith('/operations/return/1')
    expect(result.reservation_id).toBe(1)
  })

  it('valide un retour sans items ni signature', async () => {
    vi.mocked(api.post).mockResolvedValue({ ...mockReturn, status: 'returned' })

    await operationsApi.validateReturn(1)

    expect(api.post).toHaveBeenCalledWith('/operations/return/1', {
      signature_url: null,
      items: [],
    })
  })

  it('déclare des dommages au retour', async () => {
    const mockReport = { id: 5, reservation_id: 1, items: [] } as unknown as DamageReportResponse
    vi.mocked(api.post).mockResolvedValue(mockReport)

    await operationsApi.declareDamage(1, { items: [{ item_id: 3, damage_type_id: 1, notes: 'Rayure' }] })

    expect(api.post).toHaveBeenCalledWith('/operations/return/1/damage', expect.any(Object))
  })
})

describe('operationsApi - QR', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('résout un code QR produit', async () => {
    const mockQr = { type: 'product', id: 7, label: 'Chaise noire' } as unknown as QrResult
    vi.mocked(api.get).mockResolvedValue(mockQr)

    const result = await operationsApi.resolveQr('PROD-007')

    expect(api.get).toHaveBeenCalledWith('/operations/qr/PROD-007')
    expect(result.type).toBe('product')
  })

  it('encode les caractères spéciaux dans le QR', async () => {
    vi.mocked(api.get).mockResolvedValue({})

    await operationsApi.resolveQr('code/avec/slash')

    const url = vi.mocked(api.get).mock.calls[0][0] as string
    expect(url).toContain(encodeURIComponent('code/avec/slash'))
  })
})
