export interface Notification {
  id: number
  tenant_id: number
  user_id: number | null
  type: string
  title: string
  message: string | null
  link: string | null
  is_read: boolean
  created_at: string
  read_at: string | null
}

export interface NotificationList {
  items: Notification[]
  total: number
  unread_count: number
}
