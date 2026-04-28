import { createLazyFileRoute } from '@tanstack/react-router'
import FinancesExportPage from '@/pages/dashboard/FinancesExportPage'

export const Route = createLazyFileRoute('/_app/finance/export')({
  component: FinancesExportPage,
})
