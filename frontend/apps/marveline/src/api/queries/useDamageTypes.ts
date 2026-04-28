import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { damageTypesApi } from '../damage_types'
import type { DamageTypeCreate, DamageTypeUpdate } from '@/types/damage_type'

export function useDamageTypesList() {
  return useQuery({
    queryKey: queryKeys.damageTypes.all,
    queryFn: () => damageTypesApi.list(),
    staleTime: 5 * 60 * 1000,
  })
}

export function useDamageTypeDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.damageTypes.detail(id!),
    queryFn: () => damageTypesApi.get(id!),
    enabled: id !== null,
  })
}

export function useCreateDamageType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: DamageTypeCreate) => damageTypesApi.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.damageTypes.all }) },
  })
}

export function useUpdateDamageType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: DamageTypeUpdate }) =>
      damageTypesApi.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.damageTypes.all }) },
  })
}

export function useDeleteDamageType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => damageTypesApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.damageTypes.all }) },
  })
}
