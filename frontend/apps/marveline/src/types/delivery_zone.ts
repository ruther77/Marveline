// DeliveryZone types — aligned with backend DeliveryZoneResponse

export interface DeliveryZone {
  id: number
  tenant_id: number
  department_code: string   // ex: "60", "80", "02"
  department_name: string   // ex: "Oise", "Somme"
  delivery_fee_cents: number
  sunday_surcharge_cents: number
  notes: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DeliveryZoneCreate {
  department_code: string
  department_name: string
  delivery_fee_cents: number
  sunday_surcharge_cents: number
  notes?: string | null
}

export interface DeliveryZoneUpdate {
  department_code?: string
  department_name?: string
  delivery_fee_cents?: number
  sunday_surcharge_cents?: number
  notes?: string | null
  is_active?: boolean
}
