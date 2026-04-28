import { createFileRoute } from '@tanstack/react-router'
import EtlImportsPage from '../../../pages/EtlImportsPage'

export const Route = createFileRoute('/_app/etl-imports/')({
  component: EtlImportsPage,
})
