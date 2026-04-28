import { createFileRoute } from '@tanstack/react-router'
import EtlImportDetailPage from '../../../pages/EtlImportDetailPage'

export const Route = createFileRoute('/_app/etl-imports/$id')({
  component: EtlImportDetailPage,
})
