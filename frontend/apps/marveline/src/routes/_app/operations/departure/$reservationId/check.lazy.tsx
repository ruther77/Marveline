import { createLazyFileRoute } from '@tanstack/react-router'
import ArticleCheckPage from '@/pages/operations/ArticleCheckPage'

export const Route = createLazyFileRoute('/_app/operations/departure/$reservationId/check')({
  component: ArticleCheckPage,
})
