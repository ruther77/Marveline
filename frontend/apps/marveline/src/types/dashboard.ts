export interface UrgentAlert {
  reservation_id: number
  reference: string
  customer_name: string
  return_date: string
}

export interface TodayCard {
  reservation_id: number
  reference: string
  customer_name: string
  hour: string | null
  articles_count: number
  deposit_paid: boolean
  kind: 'departure' | 'return'
}

export interface TodayPlanning {
  departures: TodayCard[]
  returns: TodayCard[]
}

export interface ActivityItem {
  kind: 'return_checked' | 'invoice_paid' | 'deposit_received' | 'quote_sent' | 'low_stock' | 'reservation_created'
  label: string
  sub_label: string | null
  link: string | null
  created_at: string
}

export interface ActivityFeed {
  items: ActivityItem[]
}

export interface DashboardStats {
  active_reservations: number
  draft_reservations: number
  monthly_revenue_cents: number
  overdue_invoices: number
  overdue_amount_cents: number
  unpaid_invoices: number
  late_movements: number
  scheduled_departures: number
  scheduled_returns: number
  low_stock_products: number
  total_products: number
}

export interface FinancesMonthly {
  month: number
  revenue_cents: number
  invoices_paid: number
  invoices_overdue: number
}

export interface FinancesTotals {
  revenue_ytd_cents: number
  overdue_amount_cents: number
  active_reservations: number
  low_stock_products: number
}

export interface FinancesStats {
  year: number
  monthly: FinancesMonthly[]
  totals: FinancesTotals
}

export interface TopProductItem {
  product_id: number
  product_name: string
  category: string | null
  rental_count: number
  total_quantity: number
  revenue_cents: number
}

export interface SeasonalityMonthly {
  year: number
  month: number
  revenue_cents: number
  reservation_count: number
}

export interface AnalyticsKpis {
  avg_basket_cents: number
  total_reservations: number
  total_revenue_cents: number
  utilization_rate: number
  total_stock: number
  total_rented: number
  top_products: TopProductItem[]
  monthly_revenue: SeasonalityMonthly[]
  seasonality_years: number[]
}
