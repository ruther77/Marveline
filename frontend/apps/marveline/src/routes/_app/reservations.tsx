import { createFileRoute, Outlet } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/reservations')({
  component: () => (
    <div className="p-4 md:p-6">
      <Outlet />
    </div>
  ),
})
