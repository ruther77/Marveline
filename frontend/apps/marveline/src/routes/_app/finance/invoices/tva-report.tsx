import { createFileRoute } from '@tanstack/react-router'
import { TvaReportPage } from '@/pages/invoices/TvaReportPage'

export const Route = createFileRoute('/_app/finance/invoices/tva-report')({
  component: TvaReportPage,
})
