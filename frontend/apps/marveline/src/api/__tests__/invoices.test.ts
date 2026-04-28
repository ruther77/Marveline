/**
 * Tests unitaires pour api/invoices.ts
 * Vérifie tous les appels API invoices
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { invoicesApi } from '../invoices'
import { api, fetchBlob } from '../fetchClient'
import type { InvoiceDetail, InvoiceListItem } from '@/types/invoice'

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

describe('Invoices API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── GET /invoices ───────────────────────────────────────────────
  describe('listInvoices', () => {
    it('appelle GET /invoices avec pagination par défaut', async () => {
      const mockData = {
        items: [{ id: 1, invoice_number: 'INV-001' }] as InvoiceListItem[],
        total: 100,
        skip: 0,
        limit: 20,
      }
      vi.mocked(api.get).mockResolvedValue(mockData)

      const result = await invoicesApi.listInvoices()

      expect(api.get).toHaveBeenCalledWith('/invoices?skip=0&limit=20')
      expect(result).toEqual(mockData)
    })

    it('passe les filtres optionnels (status, reservation_id)', async () => {
      vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, skip: 10, limit: 10 })

      await invoicesApi.listInvoices({
        skip: 10,
        limit: 10,
        status: 'PAID',
        reservation_id: 42,
      })

      const callArg = vi.mocked(api.get).mock.calls[0][0] as string
      expect(callArg).toContain('skip=10')
      expect(callArg).toContain('limit=10')
      expect(callArg).toContain('status_filter=PAID')
      expect(callArg).toContain('reservation_id=42')
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
      vi.mocked(api.get).mockResolvedValue(mockInvoice)

      const result = await invoicesApi.getInvoice(1)

      expect(api.get).toHaveBeenCalledWith('/invoices/1')
      expect(result).toEqual(mockInvoice)
    })
  })

  // ── GET /invoices/overdue ───────────────────────────────────────
  describe('getOverdueInvoices', () => {
    it('appelle GET /invoices/overdue avec limit', async () => {
      const mockData = [{ id: 1 }] as InvoiceListItem[]
      vi.mocked(api.get).mockResolvedValue(mockData)

      const result = await invoicesApi.getOverdueInvoices(10)

      expect(api.get).toHaveBeenCalledWith('/invoices/overdue?limit=10')
      expect(result).toEqual(mockData)
    })

    it('appelle sans params si limit undefined', async () => {
      vi.mocked(api.get).mockResolvedValue([])

      await invoicesApi.getOverdueInvoices()

      expect(api.get).toHaveBeenCalledWith('/invoices/overdue')
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
      vi.mocked(api.post).mockResolvedValue(mockResponse)

      const result = await invoicesApi.createInvoice(newInvoice)

      expect(api.post).toHaveBeenCalledWith('/invoices', newInvoice)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── PATCH /invoices/{id} ────────────────────────────────────────
  describe('updateInvoice', () => {
    it('appelle PATCH /invoices/{id} avec payload', async () => {
      const updates = { notes: 'Updated notes' }
      const mockResponse = { id: 1, notes: 'Updated notes' } as InvoiceDetail
      vi.mocked(api.patch).mockResolvedValue(mockResponse)

      const result = await invoicesApi.updateInvoice(1, updates)

      expect(api.patch).toHaveBeenCalledWith('/invoices/1', updates)
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
      vi.mocked(api.post).mockResolvedValue(mockResponse)

      const result = await invoicesApi.addPayment(1, payment)

      expect(api.post).toHaveBeenCalledWith('/invoices/1/add-payment', payment)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── POST /invoices/{id}/cancel ──────────────────────────────────
  describe('cancelInvoice', () => {
    it('appelle POST /invoices/{id}/cancel', async () => {
      const mockResponse = { id: 1, status: 'CANCELLED' } as InvoiceDetail
      vi.mocked(api.post).mockResolvedValue(mockResponse)

      const result = await invoicesApi.cancelInvoice(1)

      expect(api.post).toHaveBeenCalledWith('/invoices/1/cancel')
      expect(result).toEqual(mockResponse)
    })
  })

  // ── GET /invoices/{id}/pdf — fetchBlob ──────────────────────────
  describe('getPdf', () => {
    it('appelle fetchBlob pour télécharger le PDF', async () => {
      const mockBlob = new Blob(['%PDF-fake'], { type: 'application/pdf' })
      vi.mocked(fetchBlob).mockResolvedValue(mockBlob)

      const result = await invoicesApi.getPdf(1)

      expect(fetchBlob).toHaveBeenCalledWith('/invoices/1/pdf')
      expect(result).toBeInstanceOf(Blob)
    })

    it('propage les erreurs si le PDF n\'est pas disponible', async () => {
      const error = new Error('PDF not found')
      vi.mocked(fetchBlob).mockRejectedValue(error)

      await expect(invoicesApi.getPdf(999)).rejects.toThrow('PDF not found')
    })
  })
})

  // ── GET /invoices/overdue ────────────────────────────────────────
  describe('getOverdueInvoices', () => {
    it('récupère les factures en retard sans limit', async () => {
      vi.mocked(api.get).mockResolvedValue([{ id: 1, status: 'overdue' }])

      const result = await invoicesApi.getOverdueInvoices()

      expect(api.get).toHaveBeenCalledWith('/invoices/overdue')
      expect(result).toHaveLength(1)
    })

    it('applique le limit', async () => {
      vi.mocked(api.get).mockResolvedValue([])

      await invoicesApi.getOverdueInvoices(5)

      expect(api.get).toHaveBeenCalledWith('/invoices/overdue?limit=5')
    })

    it('retourne un tableau vide si aucune facture en retard', async () => {
      vi.mocked(api.get).mockResolvedValue([])

      const result = await invoicesApi.getOverdueInvoices()
      expect(result).toHaveLength(0)
    })
  })

  // ── Charges / Payments / CreditNotes / markSent ──────────────────
  describe('addCharge', () => {
    it('ajoute un frais à une facture', async () => {
      vi.mocked(api.post).mockResolvedValue({ id: 3, amount_cents: 5000 })

      await invoicesApi.addCharge(1, { description: 'Frais livraison', amount_cents: 5000 } as Parameters<typeof invoicesApi.addCharge>[1])

      expect(api.post).toHaveBeenCalledWith('/invoices/1/add-charge', expect.any(Object))
    })
  })

  describe('addPaymentRecord / listPayments', () => {
    it('enregistre un paiement', async () => {
      vi.mocked(api.post).mockResolvedValue({ id: 4, amount_cents: 100000 })

      await invoicesApi.addPaymentRecord(1, { amount_cents: 100000, payment_date: '2026-03-10' } as Parameters<typeof invoicesApi.addPaymentRecord>[1])

      expect(api.post).toHaveBeenCalledWith('/invoices/1/payments', expect.any(Object))
    })

    it('liste les paiements (PaginatedResponse)', async () => {
      const mockPage = { items: [{ id: 4, amount_cents: 100000 }], total: 1, skip: 0, limit: 1 }
      vi.mocked(api.get).mockResolvedValue(mockPage)

      const result = await invoicesApi.listPayments(1)

      expect(api.get).toHaveBeenCalledWith('/invoices/1/payments')
      expect(result.items).toHaveLength(1)
      expect(result.total).toBe(1)
    })
  })

  describe('listCreditNotes / createCreditNote', () => {
    it('liste les avoirs (PaginatedResponse)', async () => {
      const mockPage = { items: [{ id: 2, amount_cents: 30000 }], total: 1, skip: 0, limit: 1 }
      vi.mocked(api.get).mockResolvedValue(mockPage)

      const result = await invoicesApi.listCreditNotes(1)

      expect(api.get).toHaveBeenCalledWith('/invoices/1/credit-notes')
      expect(result.items).toHaveLength(1)
      expect(result.total).toBe(1)
    })

    it('crée un avoir', async () => {
      vi.mocked(api.post).mockResolvedValue({ id: 2, amount_cents: 30000 })

      await invoicesApi.createCreditNote(1, { amount_cents: 30000, reason: 'Annulation partielle', issue_date: '2026-03-15' })

      expect(api.post).toHaveBeenCalledWith('/invoices/1/credit-note', expect.any(Object))
    })
  })

  describe('markSent', () => {
    it('marque une facture comme envoyée', async () => {
      vi.mocked(api.post).mockResolvedValue({ id: 1, status: 'sent' })

      await invoicesApi.markSent(1)

      expect(api.post).toHaveBeenCalledWith('/invoices/1/mark-sent', {})
    })

    it('marque comme envoyée avec notes', async () => {
      vi.mocked(api.post).mockResolvedValue({ id: 1, status: 'sent' })

      await invoicesApi.markSent(1, { sent_at: '2026-03-10T09:00:00', notes: 'Envoyé par email' })

      expect(api.post).toHaveBeenCalledWith('/invoices/1/mark-sent', expect.any(Object))
    })
  })
