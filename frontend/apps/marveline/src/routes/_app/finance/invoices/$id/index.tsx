import { createFileRoute, useNavigate, useParams } from '@tanstack/react-router'
import { InvoiceDetailModal } from '@/pages/invoices/components'

function InvoiceDetailPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const invoiceId = parseInt(id, 10)
  const navigate = useNavigate()

  return (
    <InvoiceDetailModal
      isOpen={!isNaN(invoiceId)}
      onClose={() => navigate({ to: '/finance/invoices' })}
      invoiceId={isNaN(invoiceId) ? undefined : invoiceId}
    />
  )
}

export const Route = createFileRoute('/_app/finance/invoices/$id/')({
  component: InvoiceDetailPage,
})
