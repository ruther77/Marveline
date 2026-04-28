import { createLazyFileRoute } from '@tanstack/react-router'
import NotificationsSettingsPage from '@/pages/dashboard/NotificationsSettingsPage'

export const Route = createLazyFileRoute('/_app/notifications/settings')({
  component: NotificationsSettingsPage,
})
