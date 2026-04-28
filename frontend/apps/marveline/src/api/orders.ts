import { api } from './fetchClient'
import type { OrdersListResponse, OrdersListParams, OrderType, OrderDetail } from '../types/order'

export const ordersApi = {
  list: (params: OrdersListParams = {}): Promise<OrdersListResponse> => {
    const query = new URLSearchParams()
    if (params.skip !== undefined) query.set('skip', String(params.skip))
    if (params.limit !== undefined) query.set('limit', String(params.limit))
    if (params.status) query.set('status', params.status)
    if (params.order_type) query.set('order_type', params.order_type)
    const qs = query.toString()
    return api.get<OrdersListResponse>(`/orders${qs ? `?${qs}` : ''}`)
  },

  getDetail: (orderType: OrderType, orderId: number): Promise<OrderDetail> => {
    return api.get<OrderDetail>(`/orders/${orderType}/${orderId}`)
  },
}
