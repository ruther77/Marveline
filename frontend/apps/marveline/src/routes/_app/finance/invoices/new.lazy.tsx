import { createLazyFileRoute } from '@tanstack/react-router'
import InvoiceCreatePage from '@/pages/invoices/InvoiceCreatePage'

export const Route = createLazyFileRoute('/_app/finance/invoices/new')({
  component: InvoiceCreatePage,
})
