import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { bundlesApi } from '@/api/bundles'
import { useMultiModal } from '@/hooks/useModal'
import { useResponsive } from '@/hooks/useMediaQuery'
import { BundleFormModal, BundleDeleteModal } from './components'
import { BundleCard } from '@/components/catalogue'
import { ViewToggle, getStoredViewMode, setStoredViewMode } from '@/components/ui/ViewToggle'
import type { ViewMode } from '@/components/ui/ViewToggle'
import SmartFilters from '@/components/ui/SmartFilters'
import type { FilterConfig } from '@/components/ui/SmartFilters'
import { NoSearchResults, NoData } from '@/components/ui/EmptyState'
import type { Bundle } from '@/types/product'
import {
  Plus,
  Edit,
  Trash2,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  Star,
  Tag,
  Eye,
} from 'lucide-react'
import { cn } from '@/lib/utils'

type ModalType = 'create' | 'edit' | 'delete'

export default function BundlesPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [filterValues, setFilterValues] = useState<Record<string, unknown>>({})
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)

  const { isMobile } = useResponsive()
  const [viewMode, setViewMode] = useState<ViewMode>(() =>
    isMobile ? 'grid' : getStoredViewMode()
  )

  const navigate = useNavigate()
  const modal = useMultiModal<Bundle>()

  const effectiveView = isMobile ? 'grid' : viewMode

  const featuredFilter = filterValues.featured as string | null

  const { data, isLoading } = useQuery({
    queryKey: ['bundles', page, featuredFilter],
    queryFn: () =>
      bundlesApi.getBundles({
        page,
        page_size: 20,
        featured: featuredFilter === 'true' ? true : featuredFilter === 'false' ? false : undefined,
        active_only: true,
      }),
  })

  const bundles = data?.items || []
  const totalPages = data?.total_pages || 1

  // Filtrage client-side (recherche)
  const filteredBundles = search
    ? bundles.filter((b) => b.name.toLowerCase().includes(search.toLowerCase()))
    : bundles

  const handleOpenModal = (type: ModalType, bundle?: Bundle) => {
    setOpenMenuId(null)
    modal.open(type, bundle)
  }

  const handleViewChange = (mode: ViewMode) => {
    setViewMode(mode)
    setStoredViewMode(mode)
  }

  const handleFilterChange = (key: string, value: unknown) => {
    setFilterValues((prev) => ({ ...prev, [key]: value }))
    setPage(1)
  }

  const handleFilterReset = () => {
    setFilterValues({})
    setSearch('')
    setPage(1)
  }

  const filterConfigs: FilterConfig[] = [
    {
      key: 'featured',
      label: 'Vedette',
      type: 'select',
      icon: Star,
      options: [
        { value: 'true', label: 'En vedette' },
        { value: 'false', label: 'Non vedette' },
      ],
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Formules & Packs</h1>
          <p className="text-dark-400 mt-1">
            Gerez les formules et packs de produits
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
            <span className="hidden sm:inline">Nouvelle formule</span>
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
        searchPlaceholder="Rechercher une formule..."
      />

      {/* Content */}
      {isLoading ? (
        <div className="card text-center py-8 text-dark-400">Chargement...</div>
      ) : filteredBundles.length === 0 ? (
        bundles.length === 0 && !featuredFilter ? (
          <NoData
            onAction={() => handleOpenModal('create')}
            actionLabel="Nouvelle formule"
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
          {filteredBundles.map((bundle) => (
            <BundleCard
              key={bundle.id}
              bundle={bundle}
              onEdit={(b) => handleOpenModal('edit', b)}
              onDelete={(b) => handleOpenModal('delete', b)}
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
                  <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Formule</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Prix formule</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Nettoyage</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">Statut</th>
                  <th className="text-right py-3 px-4 text-sm font-medium text-dark-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredBundles.map((bundle) => (
                  <tr
                    key={bundle.id}
                    className="border-b border-dark-700 hover:bg-dark-800/50"
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        {bundle.featured && (
                          <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
                        )}
                        <div>
                          <div className="font-medium">{bundle.name}</div>
                          {bundle.description && (
                            <div className="text-sm text-dark-400 line-clamp-1">
                              {bundle.description}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-medium">
                        {(bundle.bundle_price_euros ?? 0).toFixed(2)} €
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {bundle.cleaning_fee > 0 ? (
                        <div className="flex items-center gap-2">
                          <Tag className="w-4 h-4 text-blue-500" />
                          <span className="text-blue-500 font-medium">
                            +{(bundle.cleaning_fee_euros ?? 0).toFixed(2)} € nettoyage
                          </span>
                        </div>
                      ) : (
                        <span className="text-dark-500">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={cn(
                          'inline-flex items-center px-2 py-1 rounded text-xs',
                          bundle.is_active
                            ? 'bg-green-500/10 text-green-500'
                            : 'bg-dark-700 text-dark-400'
                        )}
                      >
                        {bundle.is_active ? 'Actif' : 'Inactif'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end">
                        <div className="relative">
                          <button
                            onClick={() =>
                              setOpenMenuId(openMenuId === bundle.id ? null : bundle.id)
                            }
                            className="p-1 hover:bg-dark-700 rounded"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>
                          {openMenuId === bundle.id && (
                            <>
                              <div
                                className="fixed inset-0 z-10"
                                onClick={() => setOpenMenuId(null)}
                              />
                              <div className="absolute right-0 mt-2 w-48 bg-dark-800 border border-dark-700 rounded-lg shadow-lg z-20">
                                <button
                                  onClick={() => {
                                    setOpenMenuId(null)
                                    navigate(`/products/bundles/${bundle.id}`)
                                  }}
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                >
                                  <Eye className="w-4 h-4" />
                                  Voir details
                                </button>
                                <button
                                  onClick={() => handleOpenModal('edit', bundle)}
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2"
                                >
                                  <Edit className="w-4 h-4" />
                                  Modifier
                                </button>
                                <button
                                  onClick={() => handleOpenModal('delete', bundle)}
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
                ))}
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
      {effectiveView === 'grid' && totalPages > 1 && filteredBundles.length > 0 && (
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
      <BundleFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        bundle={modal.data}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />

      <BundleDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        bundle={modal.data}
      />
    </div>
  )
}
