export type SearchResultType = 'customer' | 'product' | 'reservation' | 'invoice' | 'devis';

export interface SearchResult {
  type: SearchResultType;
  id: number;
  title: string;
  subtitle?: string | null;
  url: string;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}
