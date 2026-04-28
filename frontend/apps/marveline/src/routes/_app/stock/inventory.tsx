import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/_app/stock/inventory')({
  validateSearch: (search): {
    q?: string
    stock?: string
    category?: string
    page?: number
  } => ({
    q: typeof search.q === 'string' ? search.q : '',
    stock: typeof search.stock === 'string' ? search.stock : 'all',
    category: typeof search.category === 'string' ? search.category : '',
    page: typeof search.page === 'number' ? search.page : 1,
  }),
})
