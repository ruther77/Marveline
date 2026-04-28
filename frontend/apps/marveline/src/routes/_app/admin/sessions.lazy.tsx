import { createLazyFileRoute } from '@tanstack/react-router'
import AdminTenantSessionsPage from '@/pages/admin/AdminTenantSessionsPage'

export const Route = createLazyFileRoute('/_app/admin/sessions')({
  component: AdminTenantSessionsPage,
})
