export type ReservationStatus =
  | 'draft' | 'confirmed'
  | 'confirmed_risk' | 'pre_check' | 'delivered'
  | 'extended' | 'returned' | 'returned_dispute' | 'completed' | 'cancelled'
