export interface DamageType {
  id: number
  tenant_id: number
  name: string
  default_fee_cents: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DamageTypeCreate {
  name: string
  default_fee_cents: number
}

export interface DamageTypeUpdate {
  name?: string
  default_fee_cents?: number
  is_active?: boolean
}
