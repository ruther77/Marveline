import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '../keys'
import { apiKeysApi } from '../../apiKeys'
import type { ApiKeyCreate } from '@/types/apiKey'

export function useApiKeysList(params?: { skip?: number; limit?: number; include_inactive?: boolean }) {
  return useQuery({
    queryKey: queryKeys.admin.apiKeys(params ?? {}),
    queryFn: () => apiKeysApi.listApiKeys(params),
    staleTime: 60 * 1000,
  })
}

export function useApiKeyDetail(id: number | null) {
  return useQuery({
    queryKey: ['admin', 'api-keys', 'detail', id],
    queryFn: () => apiKeysApi.get(id!),
    enabled: id !== null,
    staleTime: 60 * 1000,
  })
}

export function useCreateApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiKeyCreate) => apiKeysApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'api-keys'] }) },
  })
}

export function useDeleteApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiKeysApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'api-keys'] }) },
  })
}

export function useUpdateApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof apiKeysApi.update>[1] }) =>
      apiKeysApi.update(id, data),
    onSuccess: (_r, { id }) => {
      qc.invalidateQueries({ queryKey: ['admin', 'api-keys'] })
      qc.invalidateQueries({ queryKey: ['admin', 'api-keys', 'detail', id] })
    },
  })
}

export function useRotateApiKey() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiKeysApi.rotate(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin', 'api-keys'] }) },
  })
}
