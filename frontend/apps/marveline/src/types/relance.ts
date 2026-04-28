export type RelanceStatus = 'scheduled' | 'sent' | 'cancelled'
export type RelanceChannel = 'email' | 'sms' | 'push'

export interface RelanceResponse {
  id: number
  tenant_id: number
  invoice_id: number
  scheduled_at: string
  sent_at: string | null
  cancelled_at: string | null
  status: RelanceStatus
  channel: RelanceChannel
  message: string | null
  created_at: string
}

export interface RelanceSchedulePayload {
  invoice_id: number
  scheduled_at: string
  channel?: RelanceChannel
  message?: string
}
