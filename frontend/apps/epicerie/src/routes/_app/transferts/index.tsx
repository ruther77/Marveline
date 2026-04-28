import { createFileRoute } from '@tanstack/react-router'
import TransfertsPage from '../../../pages/TransfertsPage'

export const Route = createFileRoute('/_app/transferts/')({
  component: TransfertsPage,
})
