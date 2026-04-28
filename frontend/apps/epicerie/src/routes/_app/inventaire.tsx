import { createFileRoute } from '@tanstack/react-router'
import InventairePage from '../../pages/InventairePage'

export const Route = createFileRoute('/_app/inventaire')({
  component: InventairePage,
})
