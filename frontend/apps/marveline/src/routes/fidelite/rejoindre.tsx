import { createFileRoute } from '@tanstack/react-router'
import JoinLoyaltyPage from '@/pages/loyalty/JoinLoyaltyPage'

export const Route = createFileRoute('/fidelite/rejoindre')({
  component: JoinLoyaltyPage,
})
