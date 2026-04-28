import { createFileRoute } from '@tanstack/react-router'
import HistoriqueVentesPage from '../../pages/HistoriqueVentesPage'

export const Route = createFileRoute('/_app/historique')({
  component: HistoriqueVentesPage,
})
