/**
 * Types pour les événements clients
 */

export type EventType = 'wedding' | 'baptism' | 'birthday' | 'seminar' | 'other';
export type EventStatus = 'pending' | 'confirmed' | 'in_progress' | 'completed' | 'cancelled';
export type PaymentStatus = 'unpaid' | 'partial' | 'paid' | 'refunded';

export interface EventItem {
  id: number;
  event_id: number;
  product_id?: number;
  product_variation_id?: number;
  bundle_id?: number;
  quantity: number;
  unit_price: number;
  cleaning_fee: number;
  tax_rate: number;
  total_price: number;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface Event {
  id: number;
  tenant_id: number;

  // Informations client
  customer_name: string;
  customer_email?: string;
  customer_phone?: string;
  customer_address?: string;

  // Détails événement
  event_type: EventType;
  event_name?: string;
  event_date: string; // ISO date
  event_location?: string;
  guest_count?: number;

  // Dates location
  rental_start_date: string; // ISO date
  rental_end_date: string; // ISO date

  // Statut
  status: EventStatus;
  payment_status: PaymentStatus;

  // Facturation
  total_amount: number;
  deposit_amount: number;
  paid_amount: number;

  // Notes
  notes?: string;
  internal_notes?: string;

  // Relations
  items: EventItem[];

  // Audit
  created_at: string;
  updated_at: string;
  is_active: boolean;
  deleted_at?: string;
}

export interface EventListItem {
  id: number;
  customer_name: string;
  customer_email?: string;
  event_type: EventType;
  event_date: string;
  rental_start_date: string;
  rental_end_date: string;
  status: EventStatus;
  payment_status: PaymentStatus;
  total_amount: number;
  items_count: number;
  created_at: string;
}

export interface EventStats {
  total_events: number;
  pending: number;
  confirmed: number;
  in_progress: number;
  completed: number;
  cancelled: number;
  total_revenue: number;
  average_event_value: number;
}

export interface CreateEventRequest {
  customer_name: string;
  customer_email?: string;
  customer_phone?: string;
  customer_address?: string;
  event_type: EventType;
  event_name?: string;
  event_date: string;
  event_location?: string;
  guest_count?: number;
  rental_start_date: string;
  rental_end_date: string;
  notes?: string;
  internal_notes?: string;
  items: Array<{
    product_id?: number;
    product_variation_id?: number;
    bundle_id?: number;
    quantity: number;
    unit_price: number;
    cleaning_fee?: number;
    tax_rate?: number;
    notes?: string;
  }>;
}

export interface UpdateEventRequest {
  customer_name?: string;
  customer_email?: string;
  customer_phone?: string;
  customer_address?: string;
  event_type?: EventType;
  event_name?: string;
  event_date?: string;
  event_location?: string;
  guest_count?: number;
  rental_start_date?: string;
  rental_end_date?: string;
  status?: EventStatus;
  payment_status?: PaymentStatus;
  total_amount?: number;
  deposit_amount?: number;
  paid_amount?: number;
  notes?: string;
  internal_notes?: string;
}
