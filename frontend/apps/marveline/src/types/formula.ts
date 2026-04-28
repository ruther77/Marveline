export type FormulaType = 'classic' | 'vin_honneur'

export interface FormulaItem {
  id: number
  formula_id: number
  product_id: number
  quantity_per_person: number
}

export interface Formula {
  id: number
  tenant_id: number
  name: string
  slug: string
  description: string | null
  formula_type: FormulaType
  price_per_person_cents: number
  featured: boolean
  sort_order: number
  is_active: boolean
  items: FormulaItem[]
}

export interface FormulaItemCreate {
  product_id: number
  quantity_per_person: number
}

export interface FormulaCreate {
  name: string
  slug: string
  description?: string | null
  formula_type: FormulaType
  price_per_person_cents: number
  featured: boolean
  sort_order: number
  items: FormulaItemCreate[]
}

export interface FormulaUpdate {
  name?: string
  description?: string | null
  formula_type?: FormulaType
  price_per_person_cents?: number
  featured?: boolean
  sort_order?: number
  items?: FormulaItemCreate[]
}

export interface ApplyFormulaRequest {
  formula_id: number
  nb_guests: number
  reservation_id: number
}

export interface ApplyFormulaResponse {
  formula_id: number
  nb_guests: number
  lines_created: number
  total_quantity: number
}
