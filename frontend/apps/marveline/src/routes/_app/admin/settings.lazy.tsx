import { createLazyFileRoute } from '@tanstack/react-router'
import AdminSettingsPage from '@/pages/admin/AdminSettingsPage'

export const Route = createLazyFileRoute('/_app/admin/settings')({
  component: AdminSettingsPage,
})
