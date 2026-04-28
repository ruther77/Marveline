import { createFileRoute } from '@tanstack/react-router'
import TransfertDetailPage from '../../../pages/TransfertDetailPage'

export const Route = createFileRoute('/_app/transferts/$id')({
  component: TransfertDetailPage,
})
