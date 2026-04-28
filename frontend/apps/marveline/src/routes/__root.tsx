import { createRootRoute, Outlet } from '@tanstack/react-router'
import { AppErrorBoundary } from '@/components/errors'
import { ToastProvider } from '@shared/components/ui/Toast'

export const Route = createRootRoute({
  component: () => (
    <AppErrorBoundary>
      <ToastProvider>
        <Outlet />
      </ToastProvider>
    </AppErrorBoundary>
  ),
})
