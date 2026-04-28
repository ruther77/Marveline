import { createFileRoute } from '@tanstack/react-router'

type StockItemsSearch = {
  q?: string
  stock?: string
  category?: string
  page?: number
  highlight?: number
}

export const Route = createFileRoute('/_app/stock/items/')({
  validateSearch: (search: Record<string, unknown>): StockItemsSearch => ({
    q: typeof search.q === 'string' ? search.q : undefined,
    stock: typeof search.stock === 'string' ? search.stock : undefined,
    category: typeof search.category === 'string' ? search.category : undefined,
    page: typeof search.page === 'number' ? search.page : undefined,
    highlight: typeof search.highlight === 'number' ? search.highlight : undefined,
  }),
})
