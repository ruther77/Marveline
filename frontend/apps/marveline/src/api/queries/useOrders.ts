import { useQuery } from '@tanstack/react-query'
import { queryKeys } from './keys'
import { ordersApi } from '../orders'
import type { OrdersListParams, OrderType } from '@/types/order'

export function useOrdersList(params: OrdersListParams = {}) {
  return useQuery({
    queryKey: queryKeys.orders.list(params as Record<string, unknown>),
    queryFn: () => ordersApi.list(params),
  })
}

export function useOrderDetail(orderType: OrderType, orderId: number | null) {
  return useQuery({
    queryKey: queryKeys.orders.detail(orderType, orderId ?? 0),
    queryFn: () => ordersApi.getDetail(orderType, orderId!),
    enabled: orderId !== null,
  })
}
