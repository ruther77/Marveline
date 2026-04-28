export interface Supplier {
  id: number
  tenant_id: number
  name: string
  contact_name: string | null
  email: string | null
  phone: string | null
  address: string | null
  notes: string | null
  is_active: boolean
}

export interface SupplierCreate {
  name: string
  contact_name?: string
  email?: string
  phone?: string
  address?: string
  notes?: string
}

export interface SupplierUpdate {
  name?: string
  contact_name?: string
  email?: string
  phone?: string
  address?: string
  notes?: string
}
