import { createFileRoute } from '@tanstack/react-router'
import HistoriquePage from '../../pages/HistoriquePage'

export const Route = createFileRoute('/_app/historique')({
  component: HistoriquePage,
})
