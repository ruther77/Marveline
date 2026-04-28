import { createFileRoute } from '@tanstack/react-router'
import type { SearchResultType } from '@/types/search'

const VALID_TYPES: SearchResultType[] = ['customer', 'product', 'reservation', 'invoice', 'devis']

export interface SearchPageSearch {
  q: string
  types: SearchResultType[]
}

export const Route = createFileRoute('/_app/search')({
  validateSearch: (search: Record<string, unknown>): SearchPageSearch => {
    const q = typeof search.q === 'string' ? search.q : ''

    const rawTypes = search.types
    let types: SearchResultType[] = []
    if (Array.isArray(rawTypes)) {
      types = (rawTypes as string[]).filter(
        (t): t is SearchResultType => VALID_TYPES.includes(t as SearchResultType)
      )
    } else if (typeof rawTypes === 'string' && VALID_TYPES.includes(rawTypes as SearchResultType)) {
      types = [rawTypes as SearchResultType]
    }

    return { q, types }
  },
})
