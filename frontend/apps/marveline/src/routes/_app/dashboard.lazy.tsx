import { createLazyFileRoute } from '@tanstack/react-router'
import DashboardPage from '@/pages/dashboard/DashboardPage'

export const Route = createLazyFileRoute('/_app/dashboard')({
  component: DashboardPage,
})
