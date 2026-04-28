import { createLazyFileRoute } from '@tanstack/react-router'
import { Outlet } from '@tanstack/react-router'

export const Route = createLazyFileRoute('/_app/admin/users')({
  component: () => <Outlet />,
})
