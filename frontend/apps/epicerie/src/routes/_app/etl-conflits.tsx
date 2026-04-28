import { createFileRoute } from '@tanstack/react-router'
import EtlConflictsPage from '../../pages/EtlConflictsPage'

export const Route = createFileRoute('/_app/etl-conflits')({
  component: EtlConflictsPage,
})
