import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { productsApi } from '@/api/products'
import { categoriesApi } from '@/api/categories'
import { cn } from '@/lib/utils'
import { useMultiModal } from '@/hooks/useModal'
import { ProductFormModal, ProductDeleteModal } from './components'
import type { Product } from '@/types/product'
import { getStockStatus } from '@/types/product'
import {
  Search,
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
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null)
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)

  const modal = useMultiModal<Product>()

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

  // Filtrer par recherche côté client (backend n'a pas de param search)
  const filteredProducts = search
    ? products.filter(
        (p) =>
          p.name.toLowerCase().includes(search.toLowerCase()) ||
          p.sku.toLowerCase().includes(search.toLowerCase())
      )
    : products

  const handleOpenModal = (type: ModalType, product?: Product) => {
    setOpenMenuId(null)
    modal.open(type, product)
  }

  const getStockStatusColor = (status: string) => {
    switch (status) {
      case 'in_stock':
        return 'text-green-500'
      case 'low_stock':
        return 'text-yellow-500'
      case 'out_of_stock':
        return 'text-red-500'
      default:
        return 'text-dark-400'
    }
  }

  const getStockStatusLabel = (status: string) => {
    switch (status) {
      case 'in_stock':
        return 'En stock'
      case 'low_stock':
        return 'Stock faible'
      case 'out_of_stock':
        return 'Rupture'
      default:
        return status
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Produits</h1>
          <p className="text-dark-400 mt-1">
            Gérez le catalogue de produits
          </p>
        </div>
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nouveau produit
        </button>
      </div>

      {/* Filters */}
      <div className="card space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-400" />
          <input
            type="text"
            placeholder="Rechercher par nom ou SKU..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-10"
          />
        </div>

        <div className="flex gap-4 flex-wrap">
          <select
            value={categoryFilter || ''}
            onChange={(e) =>
              setCategoryFilter(e.target.value || null)
            }
            className="input"
          >
            <option value="">Toutes les catégories</option>
            {categories?.map((cat) => (
              <option key={cat.id} value={cat.slug}>
                {cat.name}
              </option>
            ))}
          </select>

          {(categoryFilter || search) && (
            <button
              onClick={() => {
                setCategoryFilter(null)
                setSearch('')
              }}
              className="btn-secondary"
            >
              Réinitialiser
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Produit
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  SKU
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Catégorie
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Stock
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Prix/jour
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Statut
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-dark-400">
                    Chargement...
                  </td>
                </tr>
              ) : filteredProducts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-dark-400">
                    Aucun produit trouvé
                  </td>
                </tr>
              ) : (
                filteredProducts.map((product) => {
                  const stockStatus = getStockStatus(product)
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
                          {categories?.find((c) => c.slug === product.category)
                            ?.name || product.category}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">
                            {product.available_quantity}/{product.stock_quantity}
                          </span>
                          <span
                            className={cn(
                              'text-sm',
                              getStockStatusColor(stockStatus)
                            )}
                          >
                            {getStockStatusLabel(stockStatus)}
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
                        <div className="flex items-center justify-end gap-2">
                          <div className="relative">
                            <button
                              onClick={() =>
                                setOpenMenuId(
                                  openMenuId === product.id ? null : product.id
                                )
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
                                    onClick={() =>
                                      handleOpenModal('edit', product)
                                    }
                                    className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                  >
                                    <Edit className="w-4 h-4" />
                                    Modifier
                                  </button>
                                  <button
                                    onClick={() =>
                                      handleOpenModal('delete', product)
                                    }
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
                })
              )}
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
