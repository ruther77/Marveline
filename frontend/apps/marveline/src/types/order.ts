export type OrderStatus =
  | 'draft'
  | 'sent'
  | 'accepted'
  | 'confirmed'
  | 'in_progress'
  | 'returning'
  | 'closed'
  | 'cancelled'

export type OrderType = 'devis' | 'reservation' | 'vente'

export interface OrderItem {
  id: number
  type: OrderType
  reference: string
  customer_id: number
  customer_name: string | null
  status: OrderStatus
  event_date: string | null
  total_cents: number | null
  created_at: string
}

export interface OrdersListResponse {
  items: OrderItem[]
  total: number
  skip: number
  limit: number
}

export interface OrdersListParams {
  skip?: number
  limit?: number
  status?: OrderStatus
  order_type?: OrderType
}

export interface OrderLineItem {
  label: string
  quantity: number
  unit_price_cents: number
  subtotal_cents: number
}

export interface OrderDetail {
  id: number
  type: OrderType
  reference: string
  customer_id: number
  customer_name: string | null
  status: OrderStatus
  native_status: string
  event_date: string | null
  total_cents: number | null
  created_at: string
  notes: string | null
  event_location: string | null
  lines: OrderLineItem[]
  actions: string[]
}
