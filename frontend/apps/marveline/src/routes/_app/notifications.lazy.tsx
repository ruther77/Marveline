import { createLazyFileRoute } from '@tanstack/react-router'
import NotificationsPage from '@/pages/dashboard/NotificationsPage'

export const Route = createLazyFileRoute('/_app/notifications')({
  component: NotificationsPage,
})
