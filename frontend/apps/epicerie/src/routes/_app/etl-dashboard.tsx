import { createFileRoute } from '@tanstack/react-router'
import EtlDashboardPage from '@/pages/EtlDashboardPage'

export const Route = createFileRoute('/_app/etl-dashboard')({
  component: EtlDashboardPage,
})
