import { createLazyFileRoute } from '@tanstack/react-router'
import LoyaltyDashboardPage from '@/pages/loyalty/LoyaltyDashboardPage'

export const Route = createLazyFileRoute('/_app/admin/loyalty')({
  component: LoyaltyDashboardPage,
})
