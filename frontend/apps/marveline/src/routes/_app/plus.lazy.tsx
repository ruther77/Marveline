import { createLazyFileRoute } from '@tanstack/react-router'
import PlusPage from '@/pages/plus/PlusPage'

export const Route = createLazyFileRoute('/_app/plus')({
  component: PlusPage,
})
