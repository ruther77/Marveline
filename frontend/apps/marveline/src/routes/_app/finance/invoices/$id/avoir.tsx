import { createFileRoute } from '@tanstack/react-router'
import { AvoirsPage } from '@/pages/invoices/AvoirsPage'

export const Route = createFileRoute('/_app/finance/invoices/$id/avoir')({
  component: AvoirsPage,
})
