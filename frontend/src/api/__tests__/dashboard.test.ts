/**
 * Tests unitaires pour api/dashboard.ts
 * Vérifie récupération des statistiques dashboard
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { dashboardApi } from '../dashboard'
import apiClient from '../client'
import type { DashboardStats } from '@/types/dashboard'

// Mock apiClient
vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('Dashboard API - getStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('récupère toutes les statistiques dashboard', async () => {
    const mockStats: DashboardStats = {
      total_products: 150,
      total_reservations: 42,
      active_reservations: 8,
      total_revenue_cents: 2500000,
      total_revenue_euros: 25000,
      pending_invoices: 5,
      low_stock_products: 3,
      recent_activity: [
        { id: 1, type: 'reservation_confirmed', description: 'Réservation RES-001 confirmée', timestamp: '2026-02-16T10:00:00Z' },
        { id: 2, type: 'product_created', description: 'Nouveau produit ajouté', timestamp: '2026-02-16T09:30:00Z' },
      ],
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockStats })

    const result = await dashboardApi.getStats()

    expect(apiClient.get).toHaveBeenCalledWith('/dashboard/stats')
    expect(result).toEqual(mockStats)
    expect(result.total_products).toBe(150)
    expect(result.active_reservations).toBe(8)
    expect(result.recent_activity).toHaveLength(2)
  })

  it('gère statistiques vides ou partielles', async () => {
    const mockStats: DashboardStats = {
      total_products: 0,
      total_reservations: 0,
      active_reservations: 0,
      total_revenue_cents: 0,
      total_revenue_euros: 0,
      pending_invoices: 0,
      low_stock_products: 0,
      recent_activity: [],
    }
    vi.mocked(apiClient.get).mockResolvedValue({ data: mockStats })

    const result = await dashboardApi.getStats()

    expect(result.total_products).toBe(0)
    expect(result.recent_activity).toEqual([])
  })

  it('propage les erreurs 401 si non authentifié', async () => {
    const error = new Error('Unauthorized')
    vi.mocked(apiClient.get).mockRejectedValue(error)

    await expect(dashboardApi.getStats()).rejects.toThrow('Unauthorized')
  })
})
