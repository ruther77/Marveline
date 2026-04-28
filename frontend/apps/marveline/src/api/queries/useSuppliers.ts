import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { suppliersApi } from '@/api/suppliers'
import type { SupplierCreate, SupplierUpdate } from '@/types/supplier'

export function useSuppliers() {
  return useQuery({
    queryKey: queryKeys.catalogue.suppliers(),
    queryFn: () => suppliersApi.list(),
    staleTime: 5 * 60 * 1000,
  })
}

export function useSupplierDetail(id: number | null) {
  return useQuery({
    queryKey: ['catalogue', 'suppliers', 'detail', id],
    queryFn: () => suppliersApi.get(id!),
    enabled: id !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useSupplierMutations() {
  const qc = useQueryClient()
  const invalidate = () => qc.invalidateQueries({ queryKey: queryKeys.catalogue.suppliers() })

  const create = useMutation({
    mutationFn: (data: SupplierCreate) => suppliersApi.create(data),
    onSuccess: invalidate,
  })

  const update = useMutation({
    mutationFn: ({ id, data }: { id: number; data: SupplierUpdate }) =>
      suppliersApi.update(id, data),
    onSuccess: invalidate,
  })

  const remove = useMutation({
    mutationFn: (id: number) => suppliersApi.delete(id),
    onSuccess: invalidate,
  })

  return { create, update, remove }
}
