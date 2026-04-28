import { createLazyFileRoute } from '@tanstack/react-router'
import SearchPage from '@/pages/search/SearchPage'

export const Route = createLazyFileRoute('/_app/search')({
  component: SearchPage,
})
