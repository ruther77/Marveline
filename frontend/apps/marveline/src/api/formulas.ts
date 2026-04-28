import { api } from './fetchClient'
import type {
  Formula,
  FormulaCreate,
  FormulaUpdate,
  ApplyFormulaRequest,
  ApplyFormulaResponse,
} from '../types/formula'

export const formulasApi = {
  list: async (params?: { formula_type?: string; featured_only?: boolean }) => {
    const qs = new URLSearchParams()
    if (params?.formula_type) qs.set('formula_type', params.formula_type)
    if (params?.featured_only) qs.set('featured_only', 'true')
    const query = qs.toString()
    const res = await api.get<{ items: Formula[]; total: number }>(query ? `/formulas?${query}` : '/formulas')
    return res.items
  },

  get: (id: number) => api.get<Formula>(`/formulas/${id}`),

  create: (data: FormulaCreate) => api.post<Formula>('/formulas', data),

  update: (id: number, data: FormulaUpdate) =>
    api.patch<Formula>(`/formulas/${id}`, data),

  delete: (id: number) => api.delete<void>(`/formulas/${id}`),

  apply: (data: ApplyFormulaRequest) =>
    api.post<ApplyFormulaResponse>('/formulas/apply', data),
}
