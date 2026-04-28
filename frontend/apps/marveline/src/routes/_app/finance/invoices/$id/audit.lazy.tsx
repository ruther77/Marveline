import { createLazyFileRoute } from '@tanstack/react-router'
import InvoiceAuditPage from '@/pages/invoices/InvoiceAuditPage'

export const Route = createLazyFileRoute('/_app/finance/invoices/$id/audit')({
  component: InvoiceAuditPage,
})
