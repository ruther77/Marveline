export type MaintenanceStatus = 'scheduled' | 'in_progress' | 'completed' | 'cancelled'

export interface Maintenance {
  id: number
  tenant_id: number
  product_id: number
  title: string
  description: string | null
  scheduled_date: string | null
  completed_date: string | null
  cost_cents: number | null
  status: MaintenanceStatus
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface MaintenanceCreate {
  title: string
  description?: string
  scheduled_date?: string
  cost_cents?: number
}

export interface MaintenanceUpdate {
  title?: string
  description?: string
  scheduled_date?: string
  completed_date?: string
  cost_cents?: number
  status?: MaintenanceStatus
}
