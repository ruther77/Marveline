import { createFileRoute } from '@tanstack/react-router'
export const Route = createFileRoute('/_app/reservations/')({
  validateSearch: (search): { page?: number; status?: string; highlight?: number; assigned_to_me?: boolean } => ({
    page:      Number(search.page) || 1,
    status:    typeof search.status    === 'string' ? search.status    : undefined,
    highlight: Number(search.highlight) || undefined,
    assigned_to_me: search.assigned_to_me === true || search.assigned_to_me === 'true' ? true : undefined,
  }),
})
