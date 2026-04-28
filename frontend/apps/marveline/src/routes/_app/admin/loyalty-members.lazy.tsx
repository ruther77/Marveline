import { createLazyFileRoute } from '@tanstack/react-router'
import LoyaltyMembersPage from '@/pages/loyalty/LoyaltyMembersPage'

export const Route = createLazyFileRoute('/_app/admin/loyalty-members')({
  component: LoyaltyMembersPage,
})
