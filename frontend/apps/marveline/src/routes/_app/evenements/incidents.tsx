import { createFileRoute } from '@tanstack/react-router'
import type { EventStatus } from '@/types/event'

export const Route = createFileRoute('/_app/evenements/incidents')({
  validateSearch: (search): { page?: number; q?: string; status?: EventStatus | '' } => ({
    page: typeof search.page === 'number' ? search.page : 1,
    q: typeof search.q === 'string' ? search.q : '',
    status: typeof search.status === 'string' ? search.status as EventStatus | '' : '' as EventStatus | '',
  }),
})
