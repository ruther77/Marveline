import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { bundlesApi } from '@/api/bundles'
import { useMultiModal } from '@/hooks/useModal'
import { BundleFormModal, BundleDeleteModal } from './components'
import type { Bundle } from '@/types/product'
import {
  Package,
  Plus,
  Edit,
  Trash2,
  MoreVertical,
  ChevronLeft,
  ChevronRight,
  Star,
  Tag,
} from 'lucide-react'
import { cn } from '@/lib/utils'

type ModalType = 'create' | 'edit' | 'delete'

export default function BundlesPage() {
  const [page, setPage] = useState(1)
  const [featuredFilter, setFeaturedFilter] = useState<boolean | null>(null)
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)

  const modal = useMultiModal<Bundle>()

  const { data, isLoading } = useQuery({
    queryKey: ['bundles', page, featuredFilter],
    queryFn: () =>
      bundlesApi.getBundles({
        page,
        page_size: 20,
        featured: featuredFilter || undefined,
        active_only: true,
      }),
  })

  const bundles = data?.items || []
  const totalPages = data?.total_pages || 1

  const handleOpenModal = (type: ModalType, bundle?: Bundle) => {
    setOpenMenuId(null)
    modal.open(type, bundle)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Formules & Packs</h1>
          <p className="text-dark-400 mt-1">
            Gérez les formules et packs de produits
          </p>
        </div>
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Nouvelle formule
        </button>
      </div>

      {/* Filters */}
      <div className="card">
        <select
          value={
            featuredFilter === null ? '' : featuredFilter ? 'true' : 'false'
          }
          onChange={(e) =>
            setFeaturedFilter(
              e.target.value === '' ? null : e.target.value === 'true'
            )
          }
          className="input"
        >
          <option value="">Toutes les formules</option>
          <option value="true">En vedette uniquement</option>
          <option value="false">Non vedette</option>
        </select>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-dark-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Formule
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Prix formule
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-dark-400">
                  Nettoyage
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
                  <td colSpan={5} className="text-center py-8 text-dark-400">
                    Chargement...
                  </td>
                </tr>
              ) : bundles.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-dark-400">
                    Aucune formule trouvée
                  </td>
                </tr>
              ) : (
                bundles.map((bundle) => (
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
                        {Number(bundle.bundle_price).toFixed(2)} €
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {bundle.cleaning_fee > 0 ? (
                        <div className="flex items-center gap-2">
                          <Tag className="w-4 h-4 text-blue-500" />
                          <span className="text-blue-500 font-medium">
                            +{Number(bundle.cleaning_fee).toFixed(2)} € nettoyage
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
                      <div className="flex items-center justify-end gap-2">
                        <div className="relative">
                          <button
                            onClick={() =>
                              setOpenMenuId(
                                openMenuId === bundle.id ? null : bundle.id
                              )
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
                                  onClick={() => handleOpenModal('edit', bundle)}
                                  className="w-full px-4 py-2 text-left hover:bg-dark-700 flex items-center gap-2 first:rounded-t-lg"
                                >
                                  <Edit className="w-4 h-4" />
                                  Modifier
                                </button>
                                <button
                                  onClick={() =>
                                    handleOpenModal('delete', bundle)
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
                ))
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
