import { createLazyFileRoute } from '@tanstack/react-router'
import InvoiceEditPage from '@/pages/invoices/InvoiceEditPage'

export const Route = createLazyFileRoute('/_app/finance/invoices/$id/edit')({
  component: InvoiceEditPage,
})
