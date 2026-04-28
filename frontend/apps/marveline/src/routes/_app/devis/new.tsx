import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/devis/new')({
  validateSearch: (search): { step?: number } => {
    const raw = search.step
    const step = typeof raw === 'number' ? raw : typeof raw === 'string' ? parseInt(raw, 10) : 1
    return { step: [1, 2, 3, 4, 5].includes(step) ? step : 1 }
  },
})
