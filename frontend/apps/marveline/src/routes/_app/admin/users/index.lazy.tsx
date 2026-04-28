import { createLazyFileRoute } from '@tanstack/react-router'
import UsersPage from '@/pages/admin/UsersPage'

export const Route = createLazyFileRoute('/_app/admin/users/')({
  component: UsersPage,
})
