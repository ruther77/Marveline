import type { PaginatedResponse } from './index'

export type ContainerType = 'bac' | 'carton' | 'palette' | 'housse' | 'caisse'

export const CONTAINER_TYPE_LABELS: Record<ContainerType, string> = {
  bac: 'Bac',
  carton: 'Carton',
  palette: 'Palette',
  housse: 'Housse',
  caisse: 'Caisse',
}

export interface Container {
  id: number
  tenant_id: number
  name: string
  container_type: ContainerType
  length_cm?: number | null
  width_cm?: number | null
  height_cm?: number | null
  max_weight_grams?: number | null
  serial_number?: string | null
  is_available: boolean
  is_active: boolean
  notes?: string | null
  created_at: string
  updated_at: string
}

export interface ContainerCreate {
  name: string
  container_type: ContainerType
  length_cm?: number | null
  width_cm?: number | null
  height_cm?: number | null
  max_weight_grams?: number | null
  serial_number?: string | null
  notes?: string | null
}

export interface ContainerUpdate {
  name?: string
  container_type?: ContainerType
  length_cm?: number | null
  width_cm?: number | null
  height_cm?: number | null
  max_weight_grams?: number | null
  serial_number?: string | null
  is_available?: boolean
  notes?: string | null
}

export interface ContainerItemCreate {
  movement_item_id: number
  quantity: number
}

export interface ContainerAssignCreate {
  container_id: number
  movement_id: number
  notes?: string | null
  items?: ContainerItemCreate[]
}

export interface ContainerItem {
  id: number
  tenant_id: number
  container_assignment_id: number
  movement_item_id: number
  quantity: number
  created_at: string
  updated_at: string
}

export interface ContainerAssignment {
  id: number
  tenant_id: number
  container_id: number
  movement_id: number
  notes?: string | null
  created_at: string
  updated_at: string
  container?: Container | null
  items: ContainerItem[]
}

export type PaginatedContainers = PaginatedResponse<Container>

// ── Contenu persistant ──────────────────────────────────────

export interface ContainerContent {
  id: number
  tenant_id: number
  container_id: number
  product_id: number
  variant_id?: number | null
  quantity: number
  created_at: string
  updated_at: string
  product_name?: string | null
  variant_label?: string | null
}

export interface ContainerContentCreate {
  product_id: number
  variant_id?: number | null
  quantity: number
}

export interface ContainerContentUpdate {
  quantity: number
}

export interface ContainerDetail extends Container {
  contents: ContainerContent[]
  contents_count: number
  total_items: number
}

export interface ContainerMovementHistory {
  movement_id: number
  movement_type: string
  status: string
  scheduled_date?: string | null
  reservation_reference?: string | null
  items_summary: { quantity: number }[]
}

export interface BulkContentEntry {
  product_id: number
  variant_id?: number | null
  quantity: number
}
