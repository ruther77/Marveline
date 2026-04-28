import { createFileRoute } from '@tanstack/react-router'
import { CautionsPage } from '@/pages/invoices/CautionsPage'

export const Route = createFileRoute('/_app/finance/invoices/cautions')({
  component: CautionsPage,
})
