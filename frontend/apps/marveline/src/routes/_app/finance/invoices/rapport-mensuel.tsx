import { createFileRoute } from '@tanstack/react-router'
import { RapportMensuelPage } from '@/pages/invoices/RapportMensuelPage'

export const Route = createFileRoute('/_app/finance/invoices/rapport-mensuel')({
  component: RapportMensuelPage,
})
