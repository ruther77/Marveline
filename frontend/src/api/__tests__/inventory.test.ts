/**
 * Tests unitaires pour api/inventory.ts
 * Vérifie tous les appels API inventory movements
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { inventoryApi } from '../inventory'
import apiClient from '../client'
import type { InventoryMovement, InventoryMovementListItem, MovementStats } from '@/types/inventory'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('Inventory API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ── GET /inventory-movements ────────────────────────────────────
  describe('getMovements', () => {
    it('appelle GET /inventory-movements avec pagination par défaut', async () => {
      const mockData = {
        items: [{ id: 1, movement_type: 'LIVRAISON' }] as InventoryMovementListItem[],
        total: 50,
      }
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData })

      const result = await inventoryApi.getMovements()

      expect(apiClient.get).toHaveBeenCalledWith('/inventory-movements', {
        params: { skip: 0, limit: 20 },
      })
      expect(result).toEqual({
        items: mockData.items,
        total: 50,
        page: 1,
        page_size: 20,
        total_pages: 3,
      })
    })

    it('calcule skip et limit correctement pour page 2', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [], total: 0 } })

      await inventoryApi.getMovements({ page: 2, page_size: 10 })

      expect(apiClient.get).toHaveBeenCalledWith('/inventory-movements', {
        params: { skip: 10, limit: 10 },
      })
    })

    it('passe les filtres optionnels (type, status, event_id)', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({ data: { items: [], total: 0 } })

      await inventoryApi.getMovements({
        movement_type: 'LIVRAISON',
        status: 'TERMINE',
        event_id: 42,
      })

      expect(apiClient.get).toHaveBeenCalledWith('/inventory-movements', {
        params: {
          skip: 0,
          limit: 20,
          movement_type: 'LIVRAISON',
          status: 'TERMINE',
          event_id: 42,
        },
      })
    })
  })

  // ── GET /inventory-movements/late ───────────────────────────────
  describe('getLateMovements', () => {
    it('appelle GET /inventory-movements/late', async () => {
      const mockData = [{ id: 1, movement_type: 'RETRAIT' }] as InventoryMovementListItem[]
      vi.mocked(apiClient.get).mockResolvedValue({ data: { data: mockData } })

      const result = await inventoryApi.getLateMovements()

      expect(apiClient.get).toHaveBeenCalledWith('/inventory-movements/late')
      expect(result).toEqual(mockData)
    })

    it('gère réponse directe sans wrapper data', async () => {
      const mockData = [{ id: 2 }] as InventoryMovementListItem[]
      vi.mocked(apiClient.get).mockResolvedValue({ data: mockData })

      const result = await inventoryApi.getLateMovements()

      expect(result).toEqual(mockData)
    })
  })

  // ── GET /inventory-movements/pending-inspections ────────────────
  describe('getPendingInspections', () => {
    it('appelle GET /inventory-movements/pending-inspections', async () => {
      const mockData = [{ id: 3 }] as InventoryMovementListItem[]
      vi.mocked(apiClient.get).mockResolvedValue({ data: { data: mockData } })

      const result = await inventoryApi.getPendingInspections()

      expect(apiClient.get).toHaveBeenCalledWith('/inventory-movements/pending-inspections')
      expect(result).toEqual(mockData)
    })
  })

  // ── GET /inventory-movements/statistics ─────────────────────────
  describe('getStatistics', () => {
    it('appelle GET /inventory-movements/statistics avec dates optionnelles', async () => {
      const mockStats: MovementStats = {
        total_movements: 100,
        by_type: { LIVRAISON: 50, RETRAIT: 50 },
        by_status: { TERMINE: 80, EN_COURS: 20 },
      }
      vi.mocked(apiClient.get).mockResolvedValue({ data: { data: mockStats } })

      const result = await inventoryApi.getStatistics('2026-01-01', '2026-01-31')

      expect(apiClient.get).toHaveBeenCalledWith('/inventory-movements/statistics', {
        params: { start_date: '2026-01-01', end_date: '2026-01-31' },
      })
      expect(result).toEqual(mockStats)
    })
  })

  // ── GET /inventory-movements/{id} ───────────────────────────────
  describe('getMovement', () => {
    it('appelle GET /inventory-movements/{id}', async () => {
      const mockMovement: InventoryMovement = {
        id: 1,
        tenant_id: 1,
        movement_type: 'LIVRAISON',
        status: 'PLANIFIE',
        expected_date: '2026-02-20',
        items: [],
        created_at: '2026-02-16T00:00:00Z',
        updated_at: '2026-02-16T00:00:00Z',
      }
      vi.mocked(apiClient.get).mockResolvedValue({ data: { data: mockMovement } })

      const result = await inventoryApi.getMovement(1)

      expect(apiClient.get).toHaveBeenCalledWith('/inventory-movements/1')
      expect(result).toEqual(mockMovement)
    })
  })

  // ── POST /inventory-movements ───────────────────────────────────
  describe('createMovement', () => {
    it('appelle POST /inventory-movements avec payload', async () => {
      const newMovement = {
        movement_type: 'LIVRAISON',
        expected_date: '2026-02-20',
        notes: 'Test',
      }
      const mockResponse: InventoryMovement = {
        id: 1,
        tenant_id: 1,
        ...newMovement,
        status: 'PLANIFIE',
        items: [],
        created_at: '2026-02-16T00:00:00Z',
        updated_at: '2026-02-16T00:00:00Z',
      }
      vi.mocked(apiClient.post).mockResolvedValue({ data: { data: mockResponse } })

      const result = await inventoryApi.createMovement(newMovement)

      expect(apiClient.post).toHaveBeenCalledWith('/inventory-movements', newMovement)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── PATCH /inventory-movements/{id} ─────────────────────────────
  describe('updateMovement', () => {
    it('appelle PATCH /inventory-movements/{id} avec payload', async () => {
      const updates = { notes: 'Updated notes' }
      const mockResponse = { id: 1, notes: 'Updated notes' } as InventoryMovement
      vi.mocked(apiClient.patch).mockResolvedValue({ data: { data: mockResponse } })

      const result = await inventoryApi.updateMovement(1, updates)

      expect(apiClient.patch).toHaveBeenCalledWith('/inventory-movements/1', updates)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── DELETE /inventory-movements/{id} ────────────────────────────
  describe('deleteMovement', () => {
    it('appelle DELETE /inventory-movements/{id}', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined })

      await inventoryApi.deleteMovement(1)

      expect(apiClient.delete).toHaveBeenCalledWith('/inventory-movements/1')
    })
  })

  // ── PATCH /inventory-movements/{id}/complete ────────────────────
  describe('completeMovement', () => {
    it('appelle PATCH /inventory-movements/{id}/complete', async () => {
      const mockResponse = { id: 1, status: 'TERMINE' } as InventoryMovement
      vi.mocked(apiClient.patch).mockResolvedValue({ data: { data: mockResponse } })

      const result = await inventoryApi.completeMovement(1)

      expect(apiClient.patch).toHaveBeenCalledWith('/inventory-movements/1/complete')
      expect(result).toEqual(mockResponse)
    })
  })

  // ── POST /inventory-movements/{id}/items ────────────────────────
  describe('addItem', () => {
    it('appelle POST /inventory-movements/{id}/items avec payload', async () => {
      const itemData = { product_id: 10, quantity: 5 }
      const mockResponse = { id: 1, movement_id: 1, product_id: 10, quantity: 5 }
      vi.mocked(apiClient.post).mockResolvedValue({ data: { data: mockResponse } })

      const result = await inventoryApi.addItem(1, itemData)

      expect(apiClient.post).toHaveBeenCalledWith('/inventory-movements/1/items', itemData)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── PATCH /inventory-movements/{movement_id}/items/{item_id} ────
  describe('updateItem', () => {
    it('appelle PATCH /inventory-movements/{movement_id}/items/{item_id}', async () => {
      const updates = { quantity_actual: 10, condition: 'GOOD' }
      const mockResponse = { id: 1, quantity_actual: 10, condition: 'GOOD' }
      vi.mocked(apiClient.patch).mockResolvedValue({ data: { data: mockResponse } })

      const result = await inventoryApi.updateItem(5, 1, updates)

      expect(apiClient.patch).toHaveBeenCalledWith('/inventory-movements/5/items/1', updates)
      expect(result).toEqual(mockResponse)
    })
  })

  // ── DELETE /inventory-movements/{movement_id}/items/{item_id} ───
  describe('removeItem', () => {
    it('appelle DELETE /inventory-movements/{movement_id}/items/{item_id}', async () => {
      vi.mocked(apiClient.delete).mockResolvedValue({ data: undefined })

      await inventoryApi.removeItem(5, 1)

      expect(apiClient.delete).toHaveBeenCalledWith('/inventory-movements/5/items/1')
    })
  })
})
