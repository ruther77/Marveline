import { createFileRoute } from '@tanstack/react-router'
import LoyaltyAdminPage from '../../../pages/LoyaltyAdminPage'

export const Route = createFileRoute('/_app/fidelite/')({
  component: LoyaltyAdminPage,
})
