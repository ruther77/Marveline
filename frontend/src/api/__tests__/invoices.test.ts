/**
 * Tests unitaires pour api/invoices.ts
 * Vérifie tous les appels API invoices
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { invoicesApi } from '../invoices'
import apiClient from '../client'
import type { InvoiceDetail, InvoiceListItem } from '@/types/invoice'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
  },
}))

describe('Invoices API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── GET /invoices ───────────────────────────────────────────────
  describe('getInvoices', () => {
    it('appelle GET /invoices avec pagination par défaut', async () => {
      const mockData = {
        items: [{ id: 1, invoice_number: 'INV-001' }] as InvoiceListItem[],
        total: 100,
      }
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData })

      const result = await invoicesApi.getInvoices()

      expect(apiClient.get).toHaveBeenCalledWith('/invoices', {
        params: { skip: 0, limit: 20 },
      })
      expect(result).toEqual({
        items: mockData.items,
        total: 100,
        page: 1,
        page_size: 20,
        total_pages: 5,
      })
    })

    it('passe les filtres optionnels (status, reservation_id)', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [], total: 0 } })

      await invoicesApi.getInvoices({
        page: 2,
        page_size: 10,
        status: 'PAID',
        reservation_id: 42,
      })

      expect(apiClient.get).toHaveBeenCalledWith('/invoices', {
        params: {
          skip: 10,
          limit: 10,
          status_filter: 'PAID',
          reservation_id: 42,
        },
      })
    })
  })

  // ── GET /invoices/{id} ──────────────────────────────────────────
  describe('getInvoice', () => {
    it('appelle GET /invoices/{id}', async () => {
      const mockInvoice: InvoiceDetail = {
        id: 1,
        tenant_id: 1,
        invoice_number: 'INV-001',
        status: 'SENT',
        subtotal_cents: 10000,
        total_cents: 12000,
        items: [],
        created_at: '2026-02-16T00:00:00Z',
        updated_at: '2026-02-16T00:00:00Z',
      }
      vi.mocked(apiClient.get).mockResolvedValue({ data: { data: mockInvoice } })

      const result = await invoicesApi.getInvoice(1)

      expect(apiClient.get).toHaveBeenCalledWith('/invoices/1')
      expect(result).toEqual(mockInvoice)
    })

    it('gère réponse sans wrapper data', async () => {
      const mockInvoice = { id: 1 } as InvoiceDetail
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockInvoice })

      const result = await invoicesApi.getInvoice(1)

      expect(result).toEqual(mockInvoice)
    })
  })

  // ── GET /invoices/overdue ───────────────────────────────────────
  describe('getOverdueInvoices', () => {
    it('appelle GET /invoices/overdue avec limit optionnel', async () => {
      const mockData = [{ id: 1 }] as InvoiceListItem[]
      vi.mocked(apiClient.get).mockResolvedValue({ data: { data: mockData } })

      const result = await invoicesApi.getOverdueInvoices(10)

      expect(apiClient.get).toHaveBeenCalledWith('/invoices/overdue', {
        params: { limit: 10 },
      })
      expect(result).toEqual(mockData)
    })

    it('appelle sans params si limit undefined', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { data: [] } })

      await invoicesApi.getOverdueInvoices()

      expect(apiClient.get).toHaveBeenCalledWith('/invoices/overdue', {
        params: undefined,
      })
    })
  })

  // ── POST /invoices ──────────────────────────────────────────────
  describe('createInvoice', () => {
    it('appelle POST /invoices avec payload', async () => {
      const newInvoice = {
        reservation_id: 42,
        due_date: '2026-03-01',
        notes: 'Test invoice',
      }
      const mockResponse: InvoiceDetail = {
        id: 1,
        tenant_id: 1,
        invoice_number: 'INV-001',
        status: 'DRAFT',
        subtotal_cents: 10000,
        total_cents: 10000,
        items: [],
        created_at: '2026-02-16T00:00:00Z',
        updated_at: '2026-02-16T00:00:00Z',
      }
      vi.mocked(apiClient.post).mockResolvedValue({ data: { data: mockResponse } })

      const result = await invoicesApi.createInvoice(newInvoice)

      expect(apiClient.post).toHaveBeenCalledWith('/invoices', newInvoice)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── PATCH /invoices/{id} ────────────────────────────────────────
  describe('updateInvoice', () => {
    it('appelle PATCH /invoices/{id} avec payload', async () => {
      const updates = { notes: 'Updated notes' }
      const mockResponse = { id: 1, notes: 'Updated notes' } as InvoiceDetail
      vi.mocked(apiClient.patch).mockResolvedValue({ data: { data: mockResponse } })

      const result = await invoicesApi.updateInvoice(1, updates)

      expect(apiClient.patch).toHaveBeenCalledWith('/invoices/1', updates)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── POST /invoices/{id}/add-payment ─────────────────────────────
  describe('addPayment', () => {
    it('appelle POST /invoices/{id}/add-payment avec payload', async () => {
      const payment = {
        amount_cents: 5000,
        payment_method: 'card',
        reference: 'REF-123',
      }
      const mockResponse = {
        id: 1,
        paid_amount_cents: 5000,
        status: 'PARTIAL',
      } as InvoiceDetail
      vi.mocked(apiClient.post).mockResolvedValue({ data: { data: mockResponse } })

      const result = await invoicesApi.addPayment(1, payment)

      expect(apiClient.post).toHaveBeenCalledWith('/invoices/1/add-payment', payment)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── POST /invoices/{id}/cancel ──────────────────────────────────
  describe('cancelInvoice', () => {
    it('appelle POST /invoices/{id}/cancel', async () => {
      const mockResponse = { id: 1, status: 'CANCELLED' } as InvoiceDetail
      vi.mocked(apiClient.post).mockResolvedValue({ data: { data: mockResponse } })

      const result = await invoicesApi.cancelInvoice(1)

      expect(apiClient.post).toHaveBeenCalledWith('/invoices/1/cancel')
      expect(result).toEqual(mockResponse)
    })
  })
})
