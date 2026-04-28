import { api } from './fetchClient'
import type {
  SupplierOrder,
  SupplierOrderPage,
  SupplierOrderCreate,
  SupplierOrderUpdate,
  SupplierOrderReceiptCreate,
} from '@/types/supplier_order'

export interface SupplierOrderListParams {
  skip?: number
  limit?: number
  status?: string
  supplier_id?: number
}

export const supplierOrdersApi = {
  listSupplierOrders(params: SupplierOrderListParams = {}): Promise<SupplierOrderPage> {
    const q = new URLSearchParams({
      skip: String(params.skip ?? 0),
      limit: String(params.limit ?? 20),
    })
    if (params.status) q.set('status', params.status)
    if (params.supplier_id) q.set('supplier_id', String(params.supplier_id))
    const qs = q.toString()
    return api.get<SupplierOrderPage>(`/supplier-orders?${qs}`)
  },

  get(id: number): Promise<SupplierOrder> {
    return api.get<SupplierOrder>(`/supplier-orders/${id}`)
  },

  create(data: SupplierOrderCreate): Promise<SupplierOrder> {
    return api.post<SupplierOrder>('/supplier-orders', data)
  },

  update(id: number, data: SupplierOrderUpdate): Promise<SupplierOrder> {
    return api.patch<SupplierOrder>(`/supplier-orders/${id}`, data)
  },

  confirm(id: number): Promise<SupplierOrder> {
    return api.post<SupplierOrder>(`/supplier-orders/${id}/confirm`, {})
  },

  receive(id: number, data: SupplierOrderReceiptCreate): Promise<SupplierOrder> {
    return api.post<SupplierOrder>(`/supplier-orders/${id}/receive`, data)
  },

  cancel(id: number): Promise<SupplierOrder> {
    return api.post<SupplierOrder>(`/supplier-orders/${id}/cancel`, {})
  },

  delete(id: number): Promise<void> {
    return api.delete<void>(`/supplier-orders/${id}`)
  },

  getSupplierPrices(supplierId: number): Promise<SupplierProductPrice[]> {
    return api.get<SupplierProductPrice[]>(`/supplier-orders/prices/${supplierId}`)
  },
}

export interface SupplierProductPrice {
  product_id: number
  variant_id: number | null
  cost_price_cents: number
  last_order_date: string | null
}
