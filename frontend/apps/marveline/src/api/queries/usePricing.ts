import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { pricingApi } from '../pricing'
import type { PricingRuleCreate } from '@/types/pricing'

export function usePricingRules(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.pricing.rules(),
    queryFn: () => pricingApi.list(),
    enabled: options?.enabled ?? true,
    select: (data) => data.items,
  })
}

export function usePricingRule(ruleId: number | null) {
  return useQuery({
    queryKey: queryKeys.pricing.rule(ruleId!),
    queryFn: () => pricingApi.get(ruleId!),
    enabled: ruleId !== null,
  })
}

/**
 * Règles de tarification applicables à un produit spécifique.
 * Inclut les règles globales, de catégorie et produit selon le backend.
 */
export function usePricingByProduct(productId: number | null, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['pricing', 'by-product', productId],
    queryFn: () => pricingApi.getByProduct(productId!),
    enabled: productId !== null && (options?.enabled ?? true),
    staleTime: 2 * 60 * 1000,
    select: (data) => data.items,
  })
}

export function usePricingSimulate(params: {
  product_id: number
  quantity: number
  date_from: string
  date_to: string
} | null) {
  return useQuery({
    queryKey: queryKeys.pricing.simulate(params ?? {}),
    queryFn: () => pricingApi.simulate(params!),
    enabled: params !== null,
  })
}

export function usePricingMutations() {
  const qc = useQueryClient()

  const invalidatePricing = () =>
    qc.invalidateQueries({ queryKey: queryKeys.pricing.all })

  const create = useMutation({
    mutationFn: (data: PricingRuleCreate) => pricingApi.create(data),
    onSuccess: invalidatePricing,
  })

  const update = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<PricingRuleCreate> }) =>
      pricingApi.update(id, data),
    onSuccess: invalidatePricing,
  })

  const remove = useMutation({
    mutationFn: (id: number) => pricingApi.delete(id),
    onSuccess: invalidatePricing,
  })

  return { create, update, remove }
}
