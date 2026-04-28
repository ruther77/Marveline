import { createFileRoute, Outlet } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/stock/items/$id')({
  component: () => <Outlet />,
})
