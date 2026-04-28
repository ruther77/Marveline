import { createLazyFileRoute } from '@tanstack/react-router'
import FinancesPeriodePage from '@/pages/dashboard/FinancesPeriodePage'

export const Route = createLazyFileRoute('/_app/finance/period')({
  component: FinancesPeriodePage,
})
