export interface PlanningReservation {
  id: number
  reference: string
  event_date: string
  return_date?: string | null
  status: string
  customer_id: number
  event_type?: string | null
  event_name?: string | null
  guest_count?: number | null
  assigned_user_id?: number | null
  assigned_user_name?: string | null
  type: 'reservation'
  // Logistique
  total_weight_grams?: number | null
  container_count?: number
  delivery_zone_name?: string | null
  delivery_fee_cents?: number
  delivery_method?: string | null
}

export interface PlanningAssignResponse {
  reservation_id: number
  assigned_user_id: number | null
}

export interface PlanningMovement {
  id: number
  scheduled_date: string
  movement_type: string
  reservation_id?: number | null
  type: 'movement'
}

export interface PlanningDay {
  reservations: PlanningReservation[]
  movements: PlanningMovement[]
}

export interface PlanningDayResponse {
  date: string
  reservations: PlanningReservation[]
  movements: PlanningMovement[]
  total_reservations: number
  total_movements: number
}

export interface PlanningWeek {
  week_start: string
  week_end: string
  days: Record<string, PlanningDay>
  total_reservations: number
  total_movements: number
}

export interface PlanningMonth {
  month: string
  start: string
  end: string
  reservations: PlanningReservation[]
  movements: PlanningMovement[]
  total_reservations: number
  total_movements: number
}

export interface PlanningResources {
  date: string
  active_reservations: PlanningReservation[]
  total: number
}

export interface PlanningTodayReservation {
  id: number
  reference: string
  event_date: string
  return_date?: string | null
  status: string
  customer_id?: number | null
  customer_name?: string | null
  event_name?: string | null
  event_type?: string | null
  guest_count?: number | null
  // Logistique
  total_weight_grams?: number | null
  container_count?: number
  delivery_zone_name?: string | null
  delivery_fee_cents?: number
  delivery_method?: string | null
}

export interface PlanningToday {
  date: string
  departures: PlanningTodayReservation[]
  returns_today: PlanningTodayReservation[]
  active: PlanningTodayReservation[]
  overdue: PlanningTodayReservation[]
  total_departures: number
  total_returns: number
  total_active: number
  total_overdue: number
}

export interface PlanningTimelineMovement {
  id: number
  scheduled_date: string
  movement_type: string
  status: string
  reservation_id?: number | null
  items_count: number
}

export interface PlanningTimelineEvent {
  reservation_id: number
  customer_name?: string | null
  event_date: string
  rental_start_date?: string | null
  rental_end_date?: string | null
  status: string
  departure?: PlanningTimelineMovement | null
  return_movement?: PlanningTimelineMovement | null
}

export interface PlanningTimeline {
  start_date: string
  end_date: string
  events: PlanningTimelineEvent[]
  reservations: PlanningReservation[]
  total_departures: number
  total_returns: number
  total_reservations: number
}

// Vue chargement
export interface LoadingContainerItem {
  movement_item_id: number
  product_name?: string | null
  variant_label?: string | null
  image_url?: string | null
  quantity: number
}

export interface LoadingContainer {
  container_id: number
  container_name: string
  container_type: string
  serial_number?: string | null
  items: LoadingContainerItem[]
}

export interface LoadingResponse {
  reservation_id: number
  reference: string
  customer_name?: string | null
  delivery_date?: string | null
  delivery_zone_name?: string | null
  delivery_method?: string | null
  total_weight_grams?: number | null
  containers: LoadingContainer[]
  unassigned_items_count: number
}
