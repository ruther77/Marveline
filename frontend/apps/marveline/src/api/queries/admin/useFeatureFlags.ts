import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '../keys'
import { featureFlagsApi } from '../../featureFlags'
import type { FeatureFlagCreate, FeatureFlagUpdate } from '@/types/featureFlag'

export function useFeatureFlags(params?: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: queryKeys.admin.featureFlags(),
    queryFn: () => featureFlagsApi.listFeatureFlags(params),
    staleTime: 60 * 1000,
  })
}

export function useFeatureFlagDetail(id: number | null) {
  return useQuery({
    queryKey: ['admin', 'feature-flags', 'detail', id],
    queryFn: () => featureFlagsApi.get(id!),
    enabled: id !== null,
    staleTime: 60 * 1000,
  })
}

export function useToggleFeatureFlag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, is_enabled }: { id: number; is_enabled: boolean }) =>
      featureFlagsApi.toggle(id, is_enabled),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.admin.featureFlags() }) },
  })
}

export function useCreateFeatureFlag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: FeatureFlagCreate) => featureFlagsApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.admin.featureFlags() }) },
  })
}

export function useUpdateFeatureFlag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: FeatureFlagUpdate }) =>
      featureFlagsApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.admin.featureFlags() }) },
  })
}

export function useDeleteFeatureFlag() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => featureFlagsApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.admin.featureFlags() }) },
  })
}
