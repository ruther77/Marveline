export type EventStatus =
  | 'planned' | 'risk' | 'in_progress' | 'incident'
  | 'returned' | 'damage' | 'cancelled' | 'closed'

export interface EventUpdate {
  name?: string
  event_date?: string
  event_location?: string
  notes?: string
  reservation_id?: number
}

export interface IncidentAction {
  id: number
  incident_id: number
  label: string
  assignee_id: number
  assignee_name?: string
  deadline: string
  status: 'todo' | 'in_progress' | 'done'
}

export interface EventIncident {
  id: number
  event_id: number
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  sla_hours: number
  declared_at: string
  declared_by: number
  owner_id?: number
  owner_name?: string
  resolved_at?: string
  affected_items: number[]
  actions: IncidentAction[]
}

export interface EventListItem {
  id: number
  tenant_id: number
  reservation_id?: number
  name: string
  event_date: string
  event_location?: string
  status: EventStatus
  customer_name?: string
  created_at: string
}

export interface EventDetailFull extends EventListItem {
  incidents: EventIncident[]
}
