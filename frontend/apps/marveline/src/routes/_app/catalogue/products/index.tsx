import { createFileRoute } from '@tanstack/react-router'
export const Route = createFileRoute('/_app/catalogue/products/')({
  validateSearch: (search): { q?: string; category?: string; stock_filter?: string; view?: 'grid' | 'table'; page?: number } => ({
    q:           typeof search.q           === 'string' ? search.q           : '',
    category:    typeof search.category    === 'string' ? search.category    : '',
    stock_filter:typeof search.stock_filter=== 'string' ? search.stock_filter: '',
    view:        search.view === 'table' ? 'table' : 'grid',
    page:        typeof search.page        === 'number' ? search.page        : 1,
  }),
})
