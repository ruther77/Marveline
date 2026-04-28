import { createFileRoute } from '@tanstack/react-router'
import RestaurantDashboardPage from '../../pages/RestaurantDashboardPage'
import { requireManager } from '@/lib/routeGuards'

export const Route = createFileRoute('/_app/dashboard')({
  beforeLoad: requireManager,
  component: RestaurantDashboardPage,
})
