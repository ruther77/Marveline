export type DepositStatus = 'held' | 'released' | 'retained'

export interface Deposit {
  id: number
  reservation_id: number
  amount_cents: number
  status: DepositStatus
  retained_amount_cents?: number
  collection_date?: string
  release_date?: string
  notes?: string
  created_at: string
}

export interface DepositCreate {
  amount_cents: number
  collection_date?: string
  notes?: string
}

export interface DepositUpdate {
  status: DepositStatus
  retained_amount_cents?: number
  release_date?: string
  notes?: string
}
