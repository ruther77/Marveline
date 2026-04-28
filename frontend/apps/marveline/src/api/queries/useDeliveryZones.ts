import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { deliveryZonesApi } from '../delivery_zones'
import type { DeliveryZoneCreate, DeliveryZoneUpdate } from '@/types/delivery_zone'

export function useDeliveryZonesList() {
  return useQuery({
    queryKey: queryKeys.deliveryZones.list(),
    queryFn: () => deliveryZonesApi.getZones(),
    staleTime: 5 * 60 * 1000,
  })
}

export function useDeliveryZoneDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.deliveryZones.detail(id!),
    queryFn: () => deliveryZonesApi.getZone(id!),
    enabled: id !== null,
    staleTime: 5 * 60 * 1000,
  })
}

export function useCreateDeliveryZone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: DeliveryZoneCreate) => deliveryZonesApi.createZone(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.deliveryZones.all }) },
  })
}

export function useUpdateDeliveryZone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: DeliveryZoneUpdate }) =>
      deliveryZonesApi.updateZone(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.deliveryZones.all }) },
  })
}

export function useDeleteDeliveryZone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deliveryZonesApi.deleteZone(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: queryKeys.deliveryZones.all }) },
  })
}
