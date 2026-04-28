import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/admin/loyalty-members')({
  validateSearch: (search): { q?: string; tier?: string; page?: number } => ({
    q: typeof search.q === 'string' ? search.q : '',
    tier: typeof search.tier === 'string' ? search.tier : '',
    page: typeof search.page === 'number' ? Math.max(1, Math.floor(search.page)) : 1,
  }),
})
