/**
 * Tests unitaires pour api/customers.ts
 * Vérifie tous les appels API customers
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { customersApi } from '../customers'
import { api } from '../fetchClient'
import type { CustomerResponse, CustomerList } from '@/types/customer'

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

describe('Customers API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── GET /customers ───────────────────────────────────────────────
  describe('listCustomers', () => {
    it('appelle GET /customers avec pagination par défaut', async () => {
      const mockData = {
        items: [
          { id: 1, email: 'john@example.com', display_name: 'John Doe' },
        ] as CustomerList[],
        total: 120,
        skip: 0,
        limit: 20,
      }
      vi.mocked(api.get).mockResolvedValue(mockData)

      const result = await customersApi.listCustomers()

      expect(api.get).toHaveBeenCalledWith('/customers?skip=0&limit=20')
      expect(result).toEqual(mockData)
    })

    it('passe les filtres optionnels (search_query, customer_type, is_active)', async () => {
      vi.mocked(api.get).mockResolvedValue({ items: [], total: 0, skip: 30, limit: 15 })

      await customersApi.listCustomers({
        skip: 30,
        limit: 15,
        search_query: 'john',
        customer_type: 'individual',
        is_active: true,
      })

      const callArg = vi.mocked(api.get).mock.calls[0][0] as string
      expect(callArg).toContain('skip=30')
      expect(callArg).toContain('limit=15')
      expect(callArg).toContain('search_query=john')
      expect(callArg).toContain('customer_type=individual')
      expect(callArg).toContain('is_active=true')
    })
  })

  // ── GET /customers/{id} ──────────────────────────────────────────
  describe('getCustomer', () => {
    it('appelle GET /customers/{id}', async () => {
      const mockCustomer: CustomerResponse = {
        id: 1,
        tenant_id: 1,
        customer_type: 'individual',
        email: 'john@example.com',
        phone: '+33612345678',
        first_name: 'John',
        last_name: 'Doe',
        address: '123 Main St',
        city: 'Paris',
        postal_code: '75001',
        country: 'FR',
        display_name: 'John Doe',
        is_active: true,
        created_at: '2026-02-16T00:00:00Z',
        updated_at: '2026-02-16T00:00:00Z',
      }
      vi.mocked(api.get).mockResolvedValue(mockCustomer)

      const result = await customersApi.getCustomer(1)

      expect(api.get).toHaveBeenCalledWith('/customers/1')
      expect(result).toEqual(mockCustomer)
    })
  })

  // ── POST /customers ──────────────────────────────────────────────
  describe('createCustomer', () => {
    it('appelle POST /customers avec payload', async () => {
      const newCustomer = {
        customer_type: 'individual' as const,
        email: 'jane@example.com',
        phone: '+33623456789',
        first_name: 'Jane',
        last_name: 'Smith',
        address: '456 Oak Ave',
        city: 'Lyon',
        postal_code: '69001',
        country: 'FR',
      }
      const mockResponse: CustomerResponse = {
        id: 1,
        tenant_id: 1,
        ...newCustomer,
        display_name: 'Jane Smith',
        is_active: true,
        created_at: '2026-02-16T00:00:00Z',
        updated_at: '2026-02-16T00:00:00Z',
      }
      vi.mocked(api.post).mockResolvedValue(mockResponse)

      const result = await customersApi.createCustomer(newCustomer)

      expect(api.post).toHaveBeenCalledWith('/customers', newCustomer)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── PATCH /customers/{id} ────────────────────────────────────────
  describe('updateCustomer', () => {
    it('appelle PATCH /customers/{id} avec payload', async () => {
      const updates = {
        phone: '+33634567890',
        address: '789 New St',
      }
      const mockResponse = {
        id: 1,
        phone: '+33634567890',
        address: '789 New St',
      } as CustomerResponse
      vi.mocked(api.patch).mockResolvedValue(mockResponse)

      const result = await customersApi.updateCustomer(1, updates)

      expect(api.patch).toHaveBeenCalledWith('/customers/1', updates)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── DELETE /customers/{id} ───────────────────────────────────────
  describe('deleteCustomer', () => {
    it('appelle DELETE /customers/{id}', async () => {
      vi.mocked(api.delete).mockResolvedValue(undefined)

      await customersApi.deleteCustomer(1)

      expect(api.delete).toHaveBeenCalledWith('/customers/1')
    })
  })

  // ── GET /customers/rfm ───────────────────────────────────────────
  describe('getRFM', () => {
    it('appelle GET /customers/rfm', async () => {
      const mockData = {
        total: 1,
        items: [{
          customer_id: 1,
          customer_name: 'Jean Dupont',
          recency_days: 12,
          frequency: 4,
          monetary_cents: 129000,
          segment: 'Loyal' as const,
        }],
      }
      vi.mocked(api.get).mockResolvedValue(mockData)

      const result = await customersApi.getRFM()

      expect(api.get).toHaveBeenCalledWith('/customers/rfm')
      expect(result).toEqual(mockData)
    })
  })

  // ── POST /customers/rfm/campaign ────────────────────────────────
  describe('sendRfmCampaign', () => {
    it('appelle POST /customers/rfm/campaign avec payload', async () => {
      const payload = {
        segment: 'Champions',
        subject: 'Offre VIP mars',
        message: 'Profitez de 10% sur votre prochaine réservation.',
      }
      const mockResponse = {
        segment: 'Champions',
        recipients_count: 8,
        sent_count: 8,
        failed_count: 0,
      }
      vi.mocked(api.post).mockResolvedValue(mockResponse)

      const result = await customersApi.sendRfmCampaign(payload)

      expect(api.post).toHaveBeenCalledWith('/customers/rfm/campaign', payload)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── POST /customers/import ──────────────────────────────────────
  describe('importCsv', () => {
    it('appelle POST /customers/import avec FormData', async () => {
      const mockReport = {
        created: 3,
        skipped: 1,
        errors: [{ row: 4, field: 'email', message: 'email est obligatoire' }],
      }
      vi.mocked(api.post).mockResolvedValue(mockReport)

      const file = new File(['customer_type,email\nindividual,test@example.com'], 'clients.csv', {
        type: 'text/csv',
      })

      const result = await customersApi.importCsv(file)

      expect(api.post).toHaveBeenCalledTimes(1)
      const [path, body] = vi.mocked(api.post).mock.calls[0]
      expect(path).toBe('/customers/import')
      expect(body).toBeInstanceOf(FormData)
      expect(result).toEqual(mockReport)
    })
  })
})
