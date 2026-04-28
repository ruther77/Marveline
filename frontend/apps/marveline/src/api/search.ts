import { api } from './fetchClient';
import type { SearchResponse } from '@/types/search';

export const searchApi = {
  search: (q: string, types?: string[], limit = 20): Promise<SearchResponse> => {
    const params = new URLSearchParams({ q, limit: String(limit) });
    if (types && types.length > 0) {
      types.forEach((t) => params.append('types', t));
    }
    return api.get<SearchResponse>(`/search?${params.toString()}`);
  },
};
