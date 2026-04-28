// Client API — Mapping ingrédient restaurant ↔ produits épicerie + résolveur cascade
// Base : /restaurant/ingredients/{id}/produits-epicerie + resolve-preview

import { massacorpApi as api } from '@/api'
import type {
  MappingCreateBody,
  MappingListResponse,
  MappingRead,
  MappingReorderBody,
  MappingUpdateBody,
  ProduitEpicerieSearchResponse,
  ResolveRequestBody,
  ResolveResponse,
} from '@/types/ingredient_sourcing'

export const ingredientSourcingApi = {
  listMappings(ingredientId: number): Promise<MappingListResponse> {
    return api.get(`/restaurant/ingredients/${ingredientId}/produits-epicerie`)
  },

  addMapping(ingredientId: number, body: MappingCreateBody): Promise<MappingRead> {
    return api.post(`/restaurant/ingredients/${ingredientId}/produits-epicerie`, body)
  },

  updateMapping(
    ingredientId: number,
    produitId: number,
    body: MappingUpdateBody,
  ): Promise<MappingRead> {
    return api.patch(
      `/restaurant/ingredients/${ingredientId}/produits-epicerie/${produitId}`,
      body,
    )
  },

  deleteMapping(ingredientId: number, produitId: number): Promise<void> {
    return api.delete(
      `/restaurant/ingredients/${ingredientId}/produits-epicerie/${produitId}`,
    )
  },

  reorderMappings(
    ingredientId: number,
    body: MappingReorderBody,
  ): Promise<MappingRead[]> {
    return api.post(
      `/restaurant/ingredients/${ingredientId}/produits-epicerie/reorder`,
      body,
    )
  },

  resolvePreview(
    ingredientId: number,
    body: ResolveRequestBody,
  ): Promise<ResolveResponse> {
    return api.post(
      `/restaurant/ingredients/${ingredientId}/resolve-preview`,
      body,
    )
  },

  searchProduitsEpicerie(
    q: string,
    limit = 20,
  ): Promise<ProduitEpicerieSearchResponse> {
    const qs = new URLSearchParams()
    if (q) qs.set('q', q)
    qs.set('limit', String(limit))
    return api.get(`/restaurant/sourcing/produits-epicerie?${qs.toString()}`)
  },
}
