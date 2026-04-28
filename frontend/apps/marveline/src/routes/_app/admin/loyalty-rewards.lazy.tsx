import { createLazyFileRoute } from '@tanstack/react-router'
import LoyaltyRewardsPage from '@/pages/loyalty/LoyaltyRewardsPage'

export const Route = createLazyFileRoute('/_app/admin/loyalty-rewards')({
  component: LoyaltyRewardsPage,
})
