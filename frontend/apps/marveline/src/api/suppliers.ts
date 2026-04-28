import { api } from './fetchClient'
import type { Supplier, SupplierCreate, SupplierUpdate } from '@/types/supplier'

export const suppliersApi = {
  async list(): Promise<Supplier[]> {
    const res = await api.get<{ items: Supplier[]; total: number }>('/suppliers')
    return res.items
  },

  get(id: number): Promise<Supplier> {
    return api.get<Supplier>(`/suppliers/${id}`)
  },

  create(data: SupplierCreate): Promise<Supplier> {
    return api.post<Supplier>('/suppliers', data)
  },

  update(id: number, data: SupplierUpdate): Promise<Supplier> {
    return api.patch<Supplier>(`/suppliers/${id}`, data)
  },

  delete(id: number): Promise<void> {
    return api.delete<void>(`/suppliers/${id}`)
  },
}
