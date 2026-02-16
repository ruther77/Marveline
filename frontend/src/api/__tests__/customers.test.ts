/**
 * Tests unitaires pour api/customers.ts
 * Vérifie tous les appels API customers
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { customersApi } from '../customers'
import apiClient from '../client'
import type { CustomerResponse, CustomerList } from '@/types/customer'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('Customers API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── GET /customers ───────────────────────────────────────────────
  describe('getCustomers', () => {
    it('appelle GET /customers avec pagination par défaut', async () => {
      const mockData = {
        items: [
          { id: 1, email: 'john@example.com', display_name: 'John Doe' },
        ] as CustomerList[],
        total: 120,
      }
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData })

      const result = await customersApi.getCustomers()

      expect(apiClient.get).toHaveBeenCalledWith('/customers', {
        params: { skip: 0, limit: 20 },
      })
      expect(result).toEqual({
        items: mockData.items,
        total: 120,
        page: 1,
        page_size: 20,
        total_pages: 6,
      })
    })

    it('passe les filtres optionnels (search_query, customer_type, is_active)', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [], total: 0 } })

      await customersApi.getCustomers({
        page: 3,
        page_size: 15,
        search_query: 'john',
        customer_type: 'individual',
        is_active: true,
      })

      expect(apiClient.get).toHaveBeenCalledWith('/customers', {
        params: {
          skip: 30,
          limit: 15,
          search_query: 'john',
          customer_type: 'individual',
          is_active: true,
        },
      })
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
      vi.mocked(apiClient.get).mockResolvedValue({ data: { data: mockCustomer } })

      const result = await customersApi.getCustomer(1)

      expect(apiClient.get).toHaveBeenCalledWith('/customers/1')
      expect(result).toEqual(mockCustomer)
    })

    it('gère réponse sans wrapper data', async () => {
      const mockCustomer = { id: 1 } as CustomerResponse
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockCustomer })

      const result = await customersApi.getCustomer(1)

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
      vi.mocked(apiClient.post).mockResolvedValue({ data: { data: mockResponse } })

      const result = await customersApi.createCustomer(newCustomer)

      expect(apiClient.post).toHaveBeenCalledWith('/customers', newCustomer)
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
      vi.mocked(apiClient.patch).mockResolvedValue({ data: { data: mockResponse } })

      const result = await customersApi.updateCustomer(1, updates)

      expect(apiClient.patch).toHaveBeenCalledWith('/customers/1', updates)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── DELETE /customers/{id} ───────────────────────────────────────
  describe('deleteCustomer', () => {
    it('appelle DELETE /customers/{id}', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined })

      await customersApi.deleteCustomer(1)

      expect(apiClient.delete).toHaveBeenCalledWith('/customers/1')
    })
  })
})
