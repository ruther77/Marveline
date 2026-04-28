import { createFileRoute } from '@tanstack/react-router'
export const Route = createFileRoute('/_app/stock/alerts/$id')({
  validateSearch: (search): { level: string } => ({
    level: typeof search.level === 'string' ? search.level : 'critical',
  }),
})
