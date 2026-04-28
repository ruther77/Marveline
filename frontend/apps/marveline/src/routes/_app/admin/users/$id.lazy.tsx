import { createLazyFileRoute } from '@tanstack/react-router'
import AdminUserDetailPage from '@/pages/admin/AdminUserDetailPage'

export const Route = createLazyFileRoute('/_app/admin/users/$id')({
  component: AdminUserDetailPage,
})
