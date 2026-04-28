import { createFileRoute } from '@tanstack/react-router'
import BarPage from '../../pages/BarPage'

export const Route = createFileRoute('/_app/bar')({
  component: BarPage,
})
