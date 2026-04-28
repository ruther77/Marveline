import { createFileRoute } from '@tanstack/react-router'
import CuisinePage from '../../pages/CuisinePage'

export const Route = createFileRoute('/_app/cuisine')({
  component: CuisinePage,
})
