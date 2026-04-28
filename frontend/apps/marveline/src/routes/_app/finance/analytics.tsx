import { createFileRoute } from '@tanstack/react-router'
import AnalyticsPage from '@/pages/dashboard/AnalyticsPage'

export const Route = createFileRoute('/_app/finance/analytics')({
  component: AnalyticsPage,
})
