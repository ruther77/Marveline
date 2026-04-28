import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { supplierOrdersApi } from '@/api/supplier_orders'
import type {
  SupplierOrderCreate,
  SupplierOrderUpdate,
  SupplierOrderReceiptCreate,
} from '@/types/supplier_order'

export function useSupplierOrders(params?: {
  skip?: number
  limit?: number
  status?: string
  supplier_id?: number
}) {
  return useQuery({
    queryKey: queryKeys.supplierOrders.list(params ?? {}),
    queryFn: () => supplierOrdersApi.listSupplierOrders(params),
    staleTime: 60 * 1000,
  })
}

export function useSupplierOrder(id: number) {
  return useQuery({
    queryKey: queryKeys.supplierOrders.detail(id),
    queryFn: () => supplierOrdersApi.get(id),
    enabled: id > 0,
    staleTime: 30 * 1000,
  })
}

export function useSupplierOrderMutations() {
  const qc = useQueryClient()

  const invalidateAll = () =>
    qc.invalidateQueries({ queryKey: queryKeys.supplierOrders.all })

  const invalidateDetail = (id: number) =>
    qc.invalidateQueries({ queryKey: queryKeys.supplierOrders.detail(id) })

  const create = useMutation({
    mutationFn: (data: SupplierOrderCreate) => supplierOrdersApi.create(data),
    onSuccess: invalidateAll,
  })

  const update = useMutation({
    mutationFn: ({ id, data }: { id: number; data: SupplierOrderUpdate }) =>
      supplierOrdersApi.update(id, data),
    onSuccess: (_res, { id }) => { invalidateAll(); invalidateDetail(id) },
  })

  const confirm = useMutation({
    mutationFn: (id: number) => supplierOrdersApi.confirm(id),
    onSuccess: (_res, id) => { invalidateAll(); invalidateDetail(id) },
  })

  const receive = useMutation({
    mutationFn: ({ id, data }: { id: number; data: SupplierOrderReceiptCreate }) =>
      supplierOrdersApi.receive(id, data),
    onSuccess: (_res, { id }) => { invalidateAll(); invalidateDetail(id) },
  })

  const cancel = useMutation({
    mutationFn: (id: number) => supplierOrdersApi.cancel(id),
    onSuccess: (_res, id) => { invalidateAll(); invalidateDetail(id) },
  })

  const remove = useMutation({
    mutationFn: (id: number) => supplierOrdersApi.delete(id),
    onSuccess: invalidateAll,
  })

  return { create, update, confirm, receive, cancel, remove }
}
