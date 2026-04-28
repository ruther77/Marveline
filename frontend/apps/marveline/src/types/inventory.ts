/**
 * Types pour les mouvements de stock (arrivées/retours)
 */

export type MovementType = 'departure' | 'return';
export type MovementStatus = 'scheduled' | 'in_transit' | 'completed' | 'late' | 'cancelled';
export type DeliveryMethod = 'delivery' | 'pickup' | 'shipping';
export type InspectionStatus = 'pending' | 'ok' | 'damaged' | 'missing';
export type ItemCondition = 'perfect' | 'good' | 'damaged' | 'missing';

export interface MovementItemUnit {
  id: number;
  stock_item_id: number;
  status_before?: string;
  status_after?: string;
  condition?: ItemCondition;
  condition_notes?: string;
}

export interface MovementItem {
  id: number;
  movement_id: number;
  event_item_id?: number;
  product_id?: number;
  variant_id?: number;
  product_name?: string;
  quantity_expected: number;
  quantity_actual?: number;
  condition?: ItemCondition;
  condition_notes?: string;
  units?: MovementItemUnit[];
  created_at: string;
  updated_at: string;
}

export interface InventoryMovement {
  id: number;
  tenant_id: number;
  event_id?: number;
  reservation_id?: number;

  // Type et dates
  movement_type: MovementType;
  scheduled_date: string; // ISO datetime
  actual_date?: string; // ISO datetime

  // Statut
  status: MovementStatus;

  // Livraison
  delivery_method?: DeliveryMethod;
  delivery_address?: string;
  delivery_notes?: string;

  // Responsable
  handled_by_user_id?: number;

  // Inspection (retours)
  inspection_status?: InspectionStatus;
  inspection_notes?: string;
  damage_fee: number;

  // Relations
  items: MovementItem[];

  // Audit
  created_at: string;
  updated_at: string;
}

export interface InventoryMovementListItem {
  id: number;
  event_id?: number;
  reservation_id?: number;
  movement_type: MovementType;
  scheduled_date: string;
  actual_date?: string;
  status: MovementStatus;
  delivery_method?: DeliveryMethod;
  items_count: number;
  product_names: string[];
  created_at: string;
}

export interface MovementStats {
  total_movements: number;
  scheduled: number;
  in_transit: number;
  completed: number;
  late: number;
  cancelled: number;
  total_damage_fees: number;
}

export interface CreateMovementRequest {
  event_id?: number;
  reservation_id?: number;
  movement_type: MovementType;
  scheduled_date: string;
  delivery_method?: DeliveryMethod;
  delivery_address?: string;
  delivery_notes?: string;
  items: Array<{
    event_item_id?: number;
    product_id?: number;
    variant_id?: number;
    quantity_expected: number;
    condition?: ItemCondition;
    condition_notes?: string;
  }>;
}

export interface UpdateMovementRequest {
  scheduled_date?: string;
  actual_date?: string;
  status?: MovementStatus;
  delivery_method?: DeliveryMethod;
  delivery_address?: string;
  delivery_notes?: string;
  handled_by_user_id?: number;
  inspection_status?: InspectionStatus;
  inspection_notes?: string;
  damage_fee?: number;
}
