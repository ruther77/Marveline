import { useQuery } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { searchApi } from '@/api/search'

export function useSearch(q: string, types?: string[], limit = 20) {
  return useQuery({
    queryKey: queryKeys.search.results(q, types),
    queryFn: () => searchApi.search(q, types, limit),
    enabled: q.trim().length >= 1,
    staleTime: 10_000,
  })
}
