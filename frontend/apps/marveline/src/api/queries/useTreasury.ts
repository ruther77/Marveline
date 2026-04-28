import { useQuery } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { treasuryApi } from '@/api/treasury'

export function useTreasuryEntries(params?: {
  entry_type?: string
  date_from?: string
  date_to?: string
  method?: string
  skip?: number
  limit?: number
}) {
  return useQuery({
    queryKey: queryKeys.treasury.entries(params ?? {}),
    queryFn: () => treasuryApi.entries(params),
    staleTime: 2 * 60 * 1000,
  })
}

export function useTreasurySummary(params?: {
  date_from?: string
  date_to?: string
}) {
  return useQuery({
    queryKey: queryKeys.treasury.summary(params ?? {}),
    queryFn: () => treasuryApi.summary(params),
    staleTime: 2 * 60 * 1000,
  })
}
