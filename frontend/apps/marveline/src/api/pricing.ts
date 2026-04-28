import { api } from './fetchClient'
import type { PricingRule, PricingRuleCreate } from '../types/pricing'
import type { PaginatedResponse } from '@/types'

export const pricingApi = {
  list: async (): Promise<PaginatedResponse<PricingRule>> => {
    return api.get<PaginatedResponse<PricingRule>>('/pricing/rules')
  },

  get: async (id: number): Promise<PricingRule> => {
    return api.get<PricingRule>(`/pricing/rules/${id}`)
  },

  create: async (payload: PricingRuleCreate): Promise<PricingRule> => {
    return api.post<PricingRule>('/pricing/rules', payload)
  },

  update: async (id: number, payload: Partial<PricingRuleCreate>): Promise<PricingRule> => {
    return api.patch<PricingRule>(`/pricing/rules/${id}`, payload)
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/pricing/rules/${id}`)
  },

  /** Règles de tarification applicables à un produit spécifique (globales + catégorie + produit). */
  getByProduct: async (productId: number): Promise<PaginatedResponse<PricingRule>> => {
    return api.get<PaginatedResponse<PricingRule>>(`/pricing/rules/product/${productId}`)
  },

  // Simulation : calcule le prix pour un produit/quantité/dates donnés
  simulate: async (payload: {
    product_id: number
    quantity: number
    date_from: string
    date_to: string
  }): Promise<{ unit_price_cents: number; total_cents: number; rule_applied?: string }> => {
    return api.post<{ unit_price_cents: number; total_cents: number; rule_applied?: string }>(
      '/pricing/simulate',
      payload
    )
  },
}
