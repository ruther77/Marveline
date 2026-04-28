import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formulasApi } from '@/api/formulas'
import type { FormulaCreate, FormulaUpdate, ApplyFormulaRequest } from '@/types/formula'

const FORMULAS_KEY = ['formulas'] as const

export function useFormulasList(params?: { formula_type?: string; featured_only?: boolean }) {
  return useQuery({
    queryKey: [...FORMULAS_KEY, params],
    queryFn: () => formulasApi.list(params),
  })
}

export function useFormula(id: number) {
  return useQuery({
    queryKey: [...FORMULAS_KEY, id],
    queryFn: () => formulasApi.get(id),
    enabled: id > 0,
  })
}

export function useCreateFormula() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: FormulaCreate) => formulasApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: FORMULAS_KEY }),
  })
}

export function useUpdateFormula() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: FormulaUpdate }) =>
      formulasApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: FORMULAS_KEY }),
  })
}

export function useDeleteFormula() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => formulasApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: FORMULAS_KEY }),
  })
}

export function useApplyFormula() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ApplyFormulaRequest) => formulasApi.apply(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: FORMULAS_KEY }),
  })
}
