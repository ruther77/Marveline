import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { productsApi } from '@/api/products'
import { categoriesApi } from '@/api/categories'
import { cn } from '@/lib/utils'
import { useMultiModal } from '@/hooks/useModal'
import { useResponsive } from '@/hooks/useMediaQuery'
import { ProductFormModal, ProductDeleteModal } from './components'
import { ProductCard } from '@/components/catalogue'
import { ViewToggle, getStoredViewMode, setStoredViewMode } from '@/components/ui/ViewToggle'
import type { ViewMode } from '@/components/ui/ViewToggle'
import SmartFilters from '@/components/ui/SmartFilters'
import type { FilterConfig } from '@/components/ui/SmartFilters'
import { NoSearchResults, NoData } from '@/components/ui/EmptyState'
import type { Product } from '@/types/product'
import { getStockStatus, getStockStatusColor, getStockStatusLabel } from '@/types/product'
import {
  Package,
  ChevronLeft,
  ChevronRight,
  Edit,
  Trash2,
  Plus,
  MoreVertical,
} from 'lucide-react'

type ModalType = 'create' | 'edit' | 'delete'

export default function ProductsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [filterValues, setFilterValues] = useState<Record<string, unknown>>({})
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)

  const { isMobile } = useResponsive()
  const [viewMode, setViewMode] = useState<ViewMode>(() =>
    isMobile ? 'grid' : getStoredViewMode()
  )

  const modal = useMultiModal<Product>()

  const effectiveView = isMobile ? 'grid' : viewMode

  const categoryFilter = filterValues.category as string | null
  const stockFilter = filterValues.stock as string | null

  const { data, isLoading } = useQuery({
    queryKey: ['products', page, categoryFilter, search],
    queryFn: () =>
      productsApi.getProducts({
        page,
        page_size: 20,
        category: categoryFilter || undefined,
        active_only: true,
      }),
  })

  const { data: categories } = useQuery({
    queryKey: ['categories'],
    queryFn: () => categoriesApi.getCategories(true),
  })

  const products = data?.items || []
  const totalPages = data?.total_pages || 1

  // Filtrage client-side (recherche + stock)
  const filteredProducts = products.filter((p) => {
    if (search) {
      const q = search.toLowerCase()
      if (!p.name.toLowerCase().includes(q) && !p.sku.toLowerCase().includes(q)) return false
    }
    if (stockFilter) {
      const status = getStockStatus(p)
      if (status !== stockFilter) return false
    }
    return true
  })

  const handleOpenModal = (type: ModalType, product?: Product) => {
    setOpenMenuId(null)
    modal.open(type, product)
  }

  const handleViewChange = (mode: ViewMode) => {
    setViewMode(mode)
    setStoredViewMode(mode)
  }

  const handleFilterChange = (key: string, value: unknown) => {
    setFilterValues((prev) => ({ ...prev, [key]: value }))
    if (key === 'category') setPage(1)
  }

  const handleFilterReset = () => {
    setFilterValues({})
    setSearch('')
    setPage(1)
  }

  const filterConfigs: FilterConfig[] = [
    {
      key: 'category',
      label: 'Categorie',
      type: 'select',
      options: categories?.map((c) => ({ value: c.slug, label: c.name })) || [],
    },
    {
      key: 'stock',
      label: 'Stock',
      type: 'select',
      options: [
        { value: 'in_stock', label: 'En stock' },
        { value: 'low_stock', label: 'Stock faible' },
        { value: 'out_of_stock', label: 'Rupture' },
      ],
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Produits</h1>
          <p className="text-dark-400 mt-1">
            Gerez le catalogue de produits
          </p>
        </div>
        <div className="flex items-center gap-3">
          {!isMobile && (
            <ViewToggle mode={viewMode} onChange={handleViewChange} />
          )}
          <button
            onClick={() => handleOpenModal('create')}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Nouveau produit</span>
          </button>
        </div>
      </div>

      {/* Smart Filters */}
      <SmartFilters
        filters={filterConfigs}
        values={filterValues}
        onChange={handleFilterChange}
        onReset={handleFilterReset}
        searchable
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Rechercher par nom ou SKU..."
      />

      {/* Content */}
      {isLoading ? (
        <div className="card text-center py-8 text-dark-400">Chargement...</div>
      ) : filteredProducts.length === 0 ? (
        products.length === 0 ? (
          <NoData
            onAction={() => handleOpenModal('create')}
            actionLabel="Nouveau produit"
          />
        ) : (
          <NoSearchResults
            searchTerm={search || undefined}
            onClear={handleFilterReset}
          />
        )
      ) : effectiveView === 'grid' ? (
        /* Grid View */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filteredProducts.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              categories={categories}
              onEdit={(p) => handleOpenModal('edit', p)}
              onDelete={(p) => handleOpenModal('delete', p)}
            />
          ))}
        </div>
      ) : (
        /* Table View */
        <div className="card p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-700">
                  <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Produit</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">SKU</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Categorie</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Stock</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Prix/jour</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Statut</th>
                  <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map((product) => {
                  const stockColor = getStockStatusColor(product)
                  const stockLabel = getStockStatusLabel(product)
                  return (
                    <tr
                      key={product.id}
                      className="border-b border-dark-700 hover:bg-dark-800/50"
                    >
                      <td className="py-3 px-4">
                        <div className="font-medium">{product.name}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="font-mono text-sm">{product.sku}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm text-dark-300">
                          {categories?.find((c) => c.slug === product.category)?.name || product.category}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">
                            {product.available_quantity}/{product.stock_quantity}
                          </span>
                          <span className={cn('text-sm', stockColor)}>
                            {stockLabel}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="font-medium">
                          {product.price_per_day_euros.toFixed(2)} €
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={cn(
                            'inline-flex items-center px-2 py-1 rounded text-xs',
                            product.is_active
                              ? 'bg-green-500/10 text-green-500'
                              : 'bg-dark-700 text-dark-400'
                          )}
                        >
                          {product.is_active ? 'Actif' : 'Inactif'}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center justify-end">
                          <div className="relative">
                            <button
                              onClick={() =>
                                setOpenMenuId(openMenuId === product.id ? null : product.id)
                              }
                              className="p-1 hover:bg-dark-700 rounded"
                            >
                              <MoreVertical className="w-4 h-4" />
                            </button>
                            {openMenuId === product.id && (
                              <>
                                <div
                                  className="fixed inset-0 z-10"
                                  onClick={() => setOpenMenuId(null)}
                                />
                                <div className="absolute right-0 mt-2 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-lg z-20">
                                  <button
                                    onClick={() => handleOpenModal('edit', product)}
                                    className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                  >
                                    <Edit className="w-4 h-4" />
                                    Modifier
                                  </button>
                                  <button
                                    onClick={() => handleOpenModal('delete', product)}
                                    className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 text-red-500 last:rounded-b-lg"
                                  >
                                    <Trash2 className="w-4 h-4" />
                                    Supprimer
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-dark-700">
              <div className="text-sm text-dark-400">
                Page {page} sur {totalPages}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Grid pagination */}
      {effectiveView === 'grid' && totalPages > 1 && filteredProducts.length > 0 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-dark-400">
            Page {page} sur {totalPages}
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Modals */}
      <ProductFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        product={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />

      <ProductDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        product={modal.data}
      />
    </div>
  )
}
