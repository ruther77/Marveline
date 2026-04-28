import { useQuery } from '@tanstack/react-query'
import { carrierApi } from '../carrier'
import type { CarrierQuoteRequest } from '@/types/carrier'

export function useCarrierQuotes(
  params: CarrierQuoteRequest & { enabled?: boolean },
) {
  const { enabled = true, ...req } = params
  return useQuery({
    queryKey: ['carrier', 'quotes', req.destination_postal_code, req.weight_grams],
    queryFn: () => carrierApi.getQuotes(req),
    enabled: enabled && req.weight_grams > 0 && req.destination_postal_code.length >= 2,
    staleTime: 2 * 60 * 1000,
    retry: 1,
  })
}
