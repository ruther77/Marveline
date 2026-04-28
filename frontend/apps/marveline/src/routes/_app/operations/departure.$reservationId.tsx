import { createFileRoute, Outlet } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/operations/departure/$reservationId')({
  component: () => <Outlet />,
})
