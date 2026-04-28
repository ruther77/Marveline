import { createRootRoute, Outlet, Navigate, useRouterState } from '@tanstack/react-router'
import { ToastProvider } from '@shared/components/ui/Toast'

export const Route = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  const pathname = useRouterState({ select: s => s.location.pathname })

  if (pathname === '/' || pathname === '') {
    return <Navigate to="/dashboard" />
  }

  return (
    <ToastProvider>
      <Outlet />
    </ToastProvider>
  )
}
