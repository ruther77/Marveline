import type { CustomerList } from './customer'
import type { Product } from './product'

export type ReservationStatus = 'draft' | 'confirmed' | 'delivered' | 'returned' | 'cancelled'

export interface ReservationLine {
  id: number
  reservation_id: number
  product_id: number
  quantity: number
  unit_price_cents: number
  subtotal_cents: number
  unit_price_euros: number
  subtotal_euros: number
  product?: Product
}

export interface ReservationList {
  id: number
  tenant_id: number
  customer_id: number
  reference: string
  event_date: string
  delivery_date: string
  return_date: string
  event_location?: string
  status: ReservationStatus
  total_amount_cents: number
  total_amount_euros: number
  deposit_amount_cents: number
  deposit_paid: boolean
  notes?: string
  created_at: string
  updated_at: string
  is_active: boolean
}

export interface ReservationDetail extends ReservationList {
  customer?: CustomerList
  lines: ReservationLine[]
  deposit_amount_euros: number
  rental_days: number
}

export interface ReservationCreate {
  customer_id: number
  event_date: string
  delivery_date: string
  return_date: string
  event_location?: string
  deposit_amount_cents?: number
  notes?: string
  lines: { product_id: number; quantity: number }[]
}

export interface ReservationUpdate {
  event_date?: string
  delivery_date?: string
  return_date?: string
  event_location?: string
  deposit_paid?: boolean
}

export interface PaginatedReservations {
  items: ReservationList[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
