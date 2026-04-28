import { api } from './fetchClient'
import type { DamageType, DamageTypeCreate, DamageTypeUpdate } from '@/types/damage_type'
import type { PaginatedResponse } from '@/types/index'

export const damageTypesApi = {
  list: () => api.get<PaginatedResponse<DamageType>>('/damage-types'),
  get: (id: number) => api.get<DamageType>(`/damage-types/${id}`),
  create: (data: DamageTypeCreate) => api.post<DamageType>('/damage-types', data),
  update: (id: number, data: DamageTypeUpdate) => api.patch<DamageType>(`/damage-types/${id}`, data),
  delete: (id: number) => api.delete<void>(`/damage-types/${id}`),
}
