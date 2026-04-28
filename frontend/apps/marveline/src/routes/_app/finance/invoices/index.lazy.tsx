import { createLazyFileRoute } from '@tanstack/react-router'
import InvoicesPage from '@/pages/invoices/InvoicesPage'

export const Route = createLazyFileRoute('/_app/finance/invoices/')({
  component: InvoicesPage,
})
