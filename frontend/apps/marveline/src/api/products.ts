import { api } from './fetchClient'
import type {
  Product,
  ProductWithRelations,
  ProductCreate,
  ProductUpdate,
  PaginatedProducts,
  ProductImage,
  ProductAvailabilityResponse,
  ProductImportReport,
} from '../types/product'
import type { Maintenance, MaintenanceCreate, MaintenanceUpdate } from '../types/maintenance'

export interface AuditLogEntry {
  id: number
  user_id: number | null
  action: string
  entity_type: string | null
  entity_id: number | null
  changes: Record<string, unknown> | null
  description: string | null
  ip_address: string | null
  created_at: string
}

export interface InventorySummary {
  total_available: number
  total_stock: number
  total_unavailable: number
  out_of_stock: number
  low_stock: number
  categories: string[]
}

export const productsApi = {
  getInventorySummary: async (): Promise<InventorySummary> => {
    return api.get<InventorySummary>('/products/inventory-summary')
  },

  // List with filters — Backend utilise skip/limit et category (string)
  listProducts: async (params?: {
    skip?: number
    limit?: number
    category?: string
    available_only?: boolean
    active_only?: boolean
    search?: string
  }): Promise<PaginatedProducts> => {
    const p: Record<string, string> = {
      skip: String(params?.skip ?? 0),
      limit: String(params?.limit ?? 20),
    }
    if (params?.category) p.category = params.category
    if (params?.available_only) p.available_only = 'true'
    if (params?.active_only !== undefined) p.is_active = String(params.active_only)
    if (params?.search) p.search = params.search
    const qs = new URLSearchParams(p).toString()
    return api.get<PaginatedProducts>(`/products?${qs}`)
  },

  listLowStock: async (params?: { threshold?: number; limit?: number; skip?: number }): Promise<Product[]> => {
    const q = new URLSearchParams()
    if (params?.threshold != null) q.set('threshold', String(params.threshold))
    if (params?.limit != null) q.set('limit', String(params.limit))
    if (params?.skip != null) q.set('skip', String(params.skip))
    const qs = q.toString()
    const res = await api.get<{ items: Product[]; total: number }>(qs ? `/products/low-stock?${qs}` : '/products/low-stock')
    return res.items
  },

  // CRUD
  getProduct: async (id: number): Promise<ProductWithRelations> => {
    return api.get<ProductWithRelations>(`/products/${id}`)
  },

  createProduct: async (product: ProductCreate): Promise<Product> => {
    return api.post<Product>('/products', product)
  },

  updateProduct: async (id: number, product: ProductUpdate): Promise<Product> => {
    return api.patch<Product>(`/products/${id}`, product)
  },

  deleteProduct: async (id: number): Promise<void> => {
    await api.delete(`/products/${id}`)
  },

  uploadProductImage: async (id: number, file: File): Promise<Product> => {
    const form = new FormData()
    form.append('file', file)
    return api.post<Product>(`/products/${id}/image`, form)
  },

  getProductAudit: async (id: number, limit = 50): Promise<AuditLogEntry[]> => {
    return api.get<AuditLogEntry[]>(`/products/${id}/audit?limit=${limit}`)
  },

  listMaintenances: async (productId: number): Promise<Maintenance[]> => {
    return api.get<Maintenance[]>(`/products/${productId}/maintenances`)
  },

  createMaintenance: async (productId: number, data: MaintenanceCreate): Promise<Maintenance> => {
    return api.post<Maintenance>(`/products/${productId}/maintenances`, data)
  },

  updateMaintenance: async (
    productId: number,
    maintenanceId: number,
    data: MaintenanceUpdate,
  ): Promise<Maintenance> => {
    return api.patch<Maintenance>(`/products/${productId}/maintenances/${maintenanceId}`, data)
  },

  deleteMaintenance: async (productId: number, maintenanceId: number): Promise<void> => {
    await api.delete(`/products/${productId}/maintenances/${maintenanceId}`)
  },

  // Gallery images
  listImages: async (productId: number): Promise<ProductImage[]> => {
    return api.get<ProductImage[]>(`/products/${productId}/images`)
  },

  addImage: async (productId: number, file: File): Promise<ProductImage> => {
    const form = new FormData()
    form.append('file', file)
    return api.post<ProductImage>(`/products/${productId}/images`, form)
  },

  deleteImage: async (productId: number, imageId: number): Promise<void> => {
    await api.delete(`/products/${productId}/images/${imageId}`)
  },

  setPrimaryImage: async (productId: number, imageId: number): Promise<ProductImage> => {
    return api.patch<ProductImage>(`/products/${productId}/images/${imageId}/set-primary`, {})
  },

  importCsv: async (file: File): Promise<ProductImportReport> => {
    const form = new FormData()
    form.append('file', file)
    return api.post<ProductImportReport>('/products/import', form)
  },

  getAvailability: async (
    productId: number,
    dateFrom: string,
    dateTo: string,
  ): Promise<ProductAvailabilityResponse> => {
    return api.get<ProductAvailabilityResponse>(
      `/products/${productId}/availability?date_from=${dateFrom}&date_to=${dateTo}`,
    )
  },
}
