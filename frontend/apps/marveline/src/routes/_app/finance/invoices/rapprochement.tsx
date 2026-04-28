import { createFileRoute } from '@tanstack/react-router'
import { RapprochementPage } from '@/pages/invoices/RapprochementPage'

export const Route = createFileRoute('/_app/finance/invoices/rapprochement')({
  component: RapprochementPage,
})
