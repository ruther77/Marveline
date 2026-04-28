import { useQuery } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { depositsApi } from '../deposits'

export function useDepositsList(params?: {
  status?: string
  date_from?: string
  date_to?: string
  skip?: number
  limit?: number
}) {
  return useQuery({
    queryKey: queryKeys.deposits.list(params ?? {}),
    queryFn: () => depositsApi.list(params),
    staleTime: 2 * 60 * 1000,
  })
}

export function useDepositsSummary() {
  return useQuery({
    queryKey: queryKeys.deposits.summary(),
    queryFn: () => depositsApi.summary(),
    staleTime: 2 * 60 * 1000,
  })
}
