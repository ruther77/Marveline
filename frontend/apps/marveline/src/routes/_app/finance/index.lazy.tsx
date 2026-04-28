import { createLazyFileRoute } from '@tanstack/react-router'
import FinancesPage from '@/pages/dashboard/FinancesPage'

export const Route = createLazyFileRoute('/_app/finance/')({
  component: FinancesPage,
})
