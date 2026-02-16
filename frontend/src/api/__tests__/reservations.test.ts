/**
 * Tests unitaires pour api/reservations.ts
 * Vérifie tous les appels API reservations
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reservationsApi } from '../reservations'
import apiClient from '../client'
import type { ReservationDetail, ReservationList } from '@/types/reservation'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}))

describe('Reservations API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── GET /reservations ────────────────────────────────────────────
  describe('getReservations', () => {
    it('appelle GET /reservations avec pagination par défaut', async () => {
      const mockData = {
        items: [{ id: 1, reference: 'RES-001', status: 'confirmed' }] as ReservationList[],
        total: 75,
      }
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData })

      const result = await reservationsApi.getReservations()

      expect(apiClient.get).toHaveBeenCalledWith('/reservations', {
        params: { skip: 0, limit: 20 },
      })
      expect(result).toEqual({
        items: mockData.items,
        total: 75,
        page: 1,
        page_size: 20,
        total_pages: 4,
      })
    })

    it('passe les filtres optionnels (status, dates, customer_id)', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [], total: 0 } })

      await reservationsApi.getReservations({
        page: 2,
        page_size: 10,
        status: 'confirmed',
        start_date: '2026-02-01',
        end_date: '2026-02-28',
        customer_id: 42,
      })

      expect(apiClient.get).toHaveBeenCalledWith('/reservations', {
        params: {
          skip: 10,
          limit: 10,
          status_filter: 'confirmed',
          start_date: '2026-02-01',
          end_date: '2026-02-28',
          customer_id: 42,
        },
      })
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
      vi.mocked(apiClient.get).mockResolvedValue({ data: { data: mockReservation } })

      const result = await reservationsApi.getReservation(1)

      expect(apiClient.get).toHaveBeenCalledWith('/reservations/1')
      expect(result).toEqual(mockReservation)
    })

    it('gère réponse sans wrapper data', async () => {
      const mockReservation = { id: 1 } as ReservationDetail
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockReservation })

      const result = await reservationsApi.getReservation(1)

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
      vi.mocked(apiClient.post).mockResolvedValue({ data: { data: mockResponse } })

      const result = await reservationsApi.createReservation(newReservation)

      expect(apiClient.post).toHaveBeenCalledWith('/reservations', newReservation)
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
      vi.mocked(apiClient.patch).mockResolvedValue({ data: { data: mockResponse } })

      const result = await reservationsApi.updateReservation(1, updates)

      expect(apiClient.patch).toHaveBeenCalledWith('/reservations/1', updates)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── POST /reservations/{id}/confirm ──────────────────────────────
  describe('confirmReservation', () => {
    it('appelle POST /reservations/{id}/confirm', async () => {
      const mockResponse = { id: 1, status: 'confirmed' } as ReservationDetail
      vi.mocked(apiClient.post).mockResolvedValue({ data: { data: mockResponse } })

      const result = await reservationsApi.confirmReservation(1)

      expect(apiClient.post).toHaveBeenCalledWith('/reservations/1/confirm')
      expect(result).toEqual(mockResponse)
    })
  })

  // ── POST /reservations/{id}/cancel ───────────────────────────────
  describe('cancelReservation', () => {
    it('appelle POST /reservations/{id}/cancel', async () => {
      const mockResponse = { id: 1, status: 'cancelled' } as ReservationDetail
      vi.mocked(apiClient.post).mockResolvedValue({ data: { data: mockResponse } })

      const result = await reservationsApi.cancelReservation(1)

      expect(apiClient.post).toHaveBeenCalledWith('/reservations/1/cancel')
      expect(result).toEqual(mockResponse)
    })
  })
})
