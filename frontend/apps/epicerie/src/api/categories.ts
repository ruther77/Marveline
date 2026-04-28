import { massacorpApi } from '@/api'

export interface MargeCategorie {
  categorie: string
  taux_marge_centieme: number
  taux_pct: number
}

export interface MargeCategorieCreate {
  categorie: string
  taux_marge_centieme?: number
}

export const margeCategoriesApi = {
  getAll: async (): Promise<MargeCategorie[]> => {
    const data = await massacorpApi.get<{ marges: MargeCategorie[]; total: number }>('/epicerie/marges')
    return data.marges
  },

  create: async (payload: MargeCategorieCreate): Promise<MargeCategorie> => {
    return massacorpApi.post<MargeCategorie>('/epicerie/marges/categories', payload)
  },

  delete: async (categorie: string): Promise<void> => {
    await massacorpApi.delete(`/epicerie/marges/categories/${categorie}`)
  },
}
