import { createLazyFileRoute } from '@tanstack/react-router'
import LoadingPage from '@/pages/planning/LoadingPage'

export const Route = createLazyFileRoute('/_app/planning/loading/$id')({
  component: LoadingPage,
})
