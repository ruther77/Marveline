import { createFileRoute } from '@tanstack/react-router'
export const Route = createFileRoute('/_app/operations/departure/$reservationId/check')({
  validateSearch: (search): { index: number } => ({
    index: typeof search.index === 'number' ? search.index : parseInt(String(search.index ?? '0'), 10) || 0,
  }),
})
