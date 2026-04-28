export type SupplierOrderStatus =
  | 'draft'
  | 'ordered'
  | 'partially_received'
  | 'fully_received'
  | 'cancelled'

export interface SupplierOrderLine {
  id: number
  product_id: number
  product_name: string | null
  qty_ordered: number
  unit_cost_cents: number
  qty_received: number
  qty_remaining: number
}

export interface SupplierOrderReceiptLineRead {
  id: number
  receipt_id: number
  order_line_id: number
  product_id: number
  product_name: string | null
  qty_received: number
  qty_damaged: number
  qty_missing: number
  damage_type_id: number | null
  notes: string | null
}

export interface SupplierOrderReceipt {
  id: number
  order_id: number
  received_at: string
  received_by: number
  notes: string | null
  lines_json: Record<string, number>
  receipt_lines: SupplierOrderReceiptLineRead[]
}

export interface SupplierOrder {
  id: number
  tenant_id: number
  supplier_id: number
  reference: string
  status: SupplierOrderStatus
  order_date: string | null
  expected_date: string | null
  notes: string | null
  created_at: string
  updated_at: string
  is_active: boolean
  lines: SupplierOrderLine[]
  receipts: SupplierOrderReceipt[]
}

export interface SupplierOrderListItem {
  id: number
  supplier_id: number
  reference: string
  status: SupplierOrderStatus
  order_date: string | null
  expected_date: string | null
  created_at: string
}

import type { PaginatedResponse } from './index'
export type SupplierOrderPage = PaginatedResponse<SupplierOrderListItem>

export interface SupplierOrderLineCreate {
  product_id: number
  qty_ordered: number
  unit_cost_cents: number
}

export interface SupplierOrderCreate {
  supplier_id: number
  reference: string
  order_date?: string
  expected_date?: string
  notes?: string
  lines: SupplierOrderLineCreate[]
}

export interface SupplierOrderUpdate {
  reference?: string
  order_date?: string
  expected_date?: string
  notes?: string
}

export interface ReceiptLineInput {
  line_id: number
  qty_received: number
  qty_damaged?: number
  qty_missing?: number
  damage_type_id?: number | null
  notes?: string | null
}

export interface SupplierOrderReceiptCreate {
  lines: ReceiptLineInput[]
  notes?: string
}
