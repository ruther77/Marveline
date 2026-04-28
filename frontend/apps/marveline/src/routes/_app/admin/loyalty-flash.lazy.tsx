import { createLazyFileRoute } from '@tanstack/react-router'
import LoyaltyFlashOffersPage from '@/pages/loyalty/LoyaltyFlashOffersPage'

export const Route = createLazyFileRoute('/_app/admin/loyalty-flash')({
  component: LoyaltyFlashOffersPage,
})
