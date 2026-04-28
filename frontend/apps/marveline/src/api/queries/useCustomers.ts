import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { customersApi } from '../customers'
import type { CustomerCreate, CustomerUpdate, CustomerList, PaginatedCustomers } from '@/types/customer'
export type { CustomerImportReport } from '@/types/customer'

export function useCustomersList(params?: Parameters<typeof customersApi.listCustomers>[0], enabled = true) {
  return useQuery({
    queryKey: queryKeys.customers.list(params ?? {}),
    queryFn: () => customersApi.listCustomers(params),
    enabled,
  })
}

export function useCustomerDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.customers.detail(id!),
    queryFn: () => customersApi.getCustomer(id!),
    enabled: id !== null,
  })
}

export function useCustomerHistory(id: number | null) {
  return useQuery({
    queryKey: queryKeys.customers.history(id!),
    queryFn: () => customersApi.getCustomerHistory(id!),
    enabled: id !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateCustomer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CustomerCreate) => customersApi.createCustomer(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.customers.all }) },
  })
}

export function useUpdateCustomer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CustomerUpdate }) =>
      customersApi.updateCustomer(id, data),

    onMutate: async ({ id, data }) => {
      await qc.cancelQueries({ queryKey: queryKeys.customers.lists() })

      const previousLists = qc.getQueriesData<PaginatedCustomers>({
        queryKey: queryKeys.customers.lists(),
      })

      qc.setQueriesData<PaginatedCustomers>(
        { queryKey: queryKeys.customers.lists() },
        (old) => {
          if (!old) return old
          return {
            ...old,
            items: old.items.map((c: CustomerList) =>
              c.id === id ? { ...c, ...data } : c
            ),
          }
        }
      )

      return { previousLists }
    },

    onError: (_err, _vars, context) => {
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data)
        })
      }
    },

    onSettled: (_r, _e, { id }) => {
      qc.invalidateQueries({ queryKey: queryKeys.customers.detail(id) })
      qc.invalidateQueries({ queryKey: queryKeys.customers.lists() })
    },
  })
}

export function useDeleteCustomer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => customersApi.deleteCustomer(id),

    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: queryKeys.customers.lists() })

      const previousLists = qc.getQueriesData<PaginatedCustomers>({
        queryKey: queryKeys.customers.lists(),
      })

      qc.setQueriesData<PaginatedCustomers>(
        { queryKey: queryKeys.customers.lists() },
        (old) => {
          if (!old) return old
          return {
            ...old,
            items: old.items.filter((c: CustomerList) => c.id !== id),
            total: old.total - 1,
          }
        }
      )

      return { previousLists }
    },

    onError: (_err, _vars, context) => {
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          qc.setQueryData(queryKey, data)
        })
      }
    },

    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.customers.all })
    },
  })
}

export function useClientRFM() {
  return useQuery({
    queryKey: queryKeys.customers.rfm(),
    queryFn: () => customersApi.getRFM(),
    staleTime: 10 * 60 * 1000,
  })
}

export function useCustomerRFMProfile(id: number, enabled: boolean = true) {
  return useQuery({
    queryKey: queryKeys.customers.rfmProfile(id),
    queryFn: () => customersApi.getCustomerRFMProfile(id),
    enabled: enabled && id > 0,
    staleTime: 10 * 60 * 1000,
  })
}

export function useSendRfmCampaign() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Parameters<typeof customersApi.sendRfmCampaign>[0]) =>
      customersApi.sendRfmCampaign(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.customers.rfm() })
    },
  })
}

export function useImportCustomersCsv() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => customersApi.importCsv(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.customers.all })
    },
  })
}
