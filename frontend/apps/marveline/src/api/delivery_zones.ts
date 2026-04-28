import { api } from './fetchClient'
import type { DeliveryZone, DeliveryZoneCreate, DeliveryZoneUpdate } from '../types/delivery_zone'

export const deliveryZonesApi = {
  getZones: async (): Promise<DeliveryZone[]> => {
    const data = await api.get<{ items: DeliveryZone[] }>('/delivery-zones?limit=1000')
    return data.items
  },

  getZone: async (id: number): Promise<DeliveryZone> => {
    return api.get<DeliveryZone>(`/delivery-zones/${id}`)
  },

  createZone: async (zone: DeliveryZoneCreate): Promise<DeliveryZone> => {
    return api.post<DeliveryZone>('/delivery-zones', zone)
  },

  updateZone: async (id: number, zone: DeliveryZoneUpdate): Promise<DeliveryZone> => {
    return api.patch<DeliveryZone>(`/delivery-zones/${id}`, zone)
  },

  deleteZone: async (id: number): Promise<void> => {
    await api.delete(`/delivery-zones/${id}`)
  },
}
