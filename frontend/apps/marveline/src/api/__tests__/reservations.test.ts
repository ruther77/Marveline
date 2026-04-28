/**
 * Tests unitaires pour api/reservations.ts
 * Vérifie tous les appels API reservations
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reservationsApi } from '../reservations'
import { api } from '../fetchClient'
import type { ReservationDetail, ReservationList } from '@/types/reservation'

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

describe('Reservations API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── GET /reservations ────────────────────────────────────────────
  describe('listReservations', () => {
    it('appelle GET /reservations avec pagination par défaut', async () => {
      const mockData = {
        items: [{ id: 1, reference: 'RES-001', status: 'confirmed' }] as ReservationList[],
        total: 75,
        skip: 0,
        limit: 20,
      }
      vi.mocked(api.get).mockResolvedValue(mockData)

      const result = await reservationsApi.listReservations()

      expect(api.get).toHaveBeenCalledWith('/reservations?skip=0&limit=20')
      expect(result).toEqual(mockData)
    })

    it('passe les filtres optionnels (status, dates, customer_id)', async () => {
      vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, skip: 10, limit: 10 })

      await reservationsApi.listReservations({
        skip: 10,
        limit: 10,
        status: 'confirmed',
        start_date: '2026-02-01',
        end_date: '2026-02-28',
        customer_id: 42,
      })

      const callArg = vi.mocked(api.get).mock.calls[0][0] as string
      expect(callArg).toContain('skip=10')
      expect(callArg).toContain('limit=10')
      expect(callArg).toContain('status_filter=confirmed')
      expect(callArg).toContain('start_date=2026-02-01')
      expect(callArg).toContain('end_date=2026-02-28')
      expect(callArg).toContain('customer_id=42')
    })
  })

  // ── GET /reservations/{id} ───────────────────────────────────────
  describe('getReservation', () => {
    it('appelle GET /reservations/{id}', async () => {
      const mockReservation: ReservationDetail = {
        id: 1,
        tenant_id: 1,
        customer_id: 10,
        reference: 'RES-001',
        event_date: '2026-03-15',
        delivery_date: '2026-03-14',
        return_date: '2026-03-16',
        status: 'confirmed',
        total_amount_cents: 50000,
        total_amount_euros: 500,
        deposit_amount_cents: 10000,
        deposit_amount_euros: 100,
        deposit_paid: true,
        rental_days: 2,
        lines: [],
        created_at: '2026-02-16T00:00:00Z',
        updated_at: '2026-02-16T00:00:00Z',
        is_active: true,
      }
      vi.mocked(api.get).mockResolvedValue(mockReservation)

      const result = await reservationsApi.getReservation(1)

      expect(api.get).toHaveBeenCalledWith('/reservations/1')
      expect(result).toEqual(mockReservation)
    })
  })

  // ── POST /reservations ───────────────────────────────────────────
  describe('createReservation', () => {
    it('appelle POST /reservations avec payload', async () => {
      const newReservation = {
        customer_id: 10,
        event_date: '2026-03-15',
        delivery_date: '2026-03-14',
        return_date: '2026-03-16',
        event_location: 'Paris',
        notes: 'Test reservation',
        lines: [
          { product_id: 1, quantity: 10 },
          { product_id: 2, quantity: 5 },
        ],
      }
      const mockResponse: ReservationDetail = {
        id: 1,
        tenant_id: 1,
        customer_id: 10,
        reference: 'RES-001',
        event_date: '2026-03-15',
        delivery_date: '2026-03-14',
        return_date: '2026-03-16',
        status: 'draft',
        total_amount_cents: 50000,
        total_amount_euros: 500,
        deposit_amount_cents: 10000,
        deposit_amount_euros: 100,
        deposit_paid: false,
        rental_days: 2,
        lines: [],
        created_at: '2026-02-16T00:00:00Z',
        updated_at: '2026-02-16T00:00:00Z',
        is_active: true,
      }
      vi.mocked(api.post).mockResolvedValue(mockResponse)

      const result = await reservationsApi.createReservation(newReservation)

      expect(api.post).toHaveBeenCalledWith('/reservations', newReservation)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── PATCH /reservations/{id} ─────────────────────────────────────
  describe('updateReservation', () => {
    it('appelle PATCH /reservations/{id} avec payload', async () => {
      const updates = {
        event_location: 'Lyon',
        deposit_paid: true,
      }
      const mockResponse = {
        id: 1,
        event_location: 'Lyon',
        deposit_paid: true,
      } as ReservationDetail
      vi.mocked(api.patch).mockResolvedValue(mockResponse)

      const result = await reservationsApi.updateReservation(1, updates)

      expect(api.patch).toHaveBeenCalledWith('/reservations/1', updates)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── POST /reservations/{id}/confirm ──────────────────────────────
  describe('confirmReservation', () => {
    it('appelle POST /reservations/{id}/confirm', async () => {
      const mockResponse = { id: 1, status: 'confirmed' } as ReservationDetail
      vi.mocked(api.post).mockResolvedValue(mockResponse)

      const result = await reservationsApi.confirmReservation(1)

      expect(api.post).toHaveBeenCalledWith('/reservations/1/confirm')
      expect(result).toEqual(mockResponse)
    })
  })

  // ── POST /reservations/{id}/cancel ───────────────────────────────
  describe('cancelReservation', () => {
    it('appelle POST /reservations/{id}/cancel', async () => {
      const mockResponse = { id: 1, status: 'cancelled' } as ReservationDetail
      vi.mocked(api.post).mockResolvedValue(mockResponse)

      const result = await reservationsApi.cancelReservation(1)

      expect(api.post).toHaveBeenCalledWith('/reservations/1/cancel')
      expect(result).toEqual(mockResponse)
    })
  })
})

describe('reservationsApi - deposits / signature / lines', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('liste les acomptes (array direct)', async () => {
    vi.mocked(api.get).mockResolvedValue([{ id: 1, amount_cents: 40000 }])

    const result = await reservationsApi.listDeposits(1)

    expect(api.get).toHaveBeenCalledWith('/reservations/1/deposits')
    expect(result).toHaveLength(1)
  })

  it('liste les acomptes (objet non-array → [])', async () => {
    vi.mocked(api.get).mockResolvedValue({ id: 1 })

    const result = await reservationsApi.listDeposits(1)
    expect(result).toHaveLength(0)
  })

  it('crée un acompte', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 2, amount_cents: 30000 })

    await reservationsApi.createDeposit(1, { amount_cents: 30000 } as Parameters<typeof reservationsApi.createDeposit>[1])

    expect(api.post).toHaveBeenCalledWith('/reservations/1/deposits', expect.any(Object))
  })

  it('met à jour un acompte', async () => {
    vi.mocked(api.patch).mockResolvedValue({ id: 2, amount_cents: 35000 })

    await reservationsApi.updateDeposit(1, 2, { amount_cents: 35000 })

    expect(api.patch).toHaveBeenCalledWith('/reservations/1/deposits/2', { amount_cents: 35000 })
  })

  it('upload une signature', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 1, status: 'confirmed' } as ReservationDetail)

    await reservationsApi.uploadSignature(1, 'data:image/png;base64,abc')

    expect(api.post).toHaveBeenCalledWith('/reservations/1/signature', { signature_data: 'data:image/png;base64,abc' })
  })

  it('ajoute une ligne', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 5, product_id: 3, quantity: 2 })

    await reservationsApi.addLine(1, { product_id: 3, quantity: 2 } as Parameters<typeof reservationsApi.addLine>[1])

    expect(api.post).toHaveBeenCalledWith('/reservations/1/lines', expect.any(Object))
  })

  it('supprime une ligne', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await reservationsApi.removeLine(1, 5)

    expect(api.delete).toHaveBeenCalledWith('/reservations/1/lines/5')
  })
})

describe('reservationsApi - pre-check / risques / extension', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('liste les items pre-check', async () => {
    vi.mocked(api.get).mockResolvedValue([{ id: 1, label: 'Vérifier câbles' }])

    const result = await reservationsApi.listPreCheck(1)

    expect(api.get).toHaveBeenCalledWith('/reservations/1/pre-check')
    expect(result).toHaveLength(1)
  })

  it('crée un item pre-check', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 2, label: 'Test son' })

    await reservationsApi.createPreCheckItem(1, { label: 'Test son' } as Parameters<typeof reservationsApi.createPreCheckItem>[1])

    expect(api.post).toHaveBeenCalledWith('/reservations/1/pre-check', expect.any(Object))
  })

  it('coche un item pre-check', async () => {
    vi.mocked(api.patch).mockResolvedValue({ id: 2, checked: true })

    await reservationsApi.updatePreCheckItem(1, 2, { checked: true })

    expect(api.patch).toHaveBeenCalledWith('/reservations/1/pre-check/2', { checked: true })
  })

  it('finalise le pre-check', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 1, status: 'confirmed' } as ReservationDetail)

    await reservationsApi.completePreCheck(1)

    expect(api.post).toHaveBeenCalledWith('/reservations/1/pre-check/complete')
  })

  it('crée un risque', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 3, severity: 'high', description: 'Accès difficile' })

    await reservationsApi.createRisk(1, { description: 'Accès difficile', severity: 'high' } as Parameters<typeof reservationsApi.createRisk>[1])

    expect(api.post).toHaveBeenCalledWith('/reservations/1/risks', expect.any(Object))
  })

  it('supprime un risque', async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined)

    await reservationsApi.deleteRisk(1, 3)

    expect(api.delete).toHaveBeenCalledWith('/reservations/1/risks/3')
  })

  it('étend une réservation', async () => {
    vi.mocked(api.post).mockResolvedValue({ id: 1, new_end_date: '2026-04-05' })

    await reservationsApi.extendReservation(1, { new_end_date: '2026-04-05' })

    expect(api.post).toHaveBeenCalledWith('/reservations/1/extend', { new_end_date: '2026-04-05' })
  })

  it('clôture un litige via POST /reservations/:id/close-dispute', async () => {
    const mockReservation = { id: 1, status: 'returned' } as ReservationDetail
    vi.mocked(api.post).mockResolvedValue(mockReservation)

    const result = await reservationsApi.closeDispute(1, 'Résolu amiablement')

    expect(api.post).toHaveBeenCalledWith(
      '/reservations/1/close-dispute',
      { resolution_notes: 'Résolu amiablement' }
    )
    expect(result).toEqual(mockReservation)
  })
})
