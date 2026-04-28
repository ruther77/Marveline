import { createFileRoute } from '@tanstack/react-router'
import { TresorerieePage } from '@/pages/invoices/TresorerieePage'

export const Route = createFileRoute('/_app/finance/treasury')({
  component: TresorerieePage,
})
