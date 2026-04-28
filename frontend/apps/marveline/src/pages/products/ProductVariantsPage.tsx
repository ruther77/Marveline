import { PageHeader } from '@/components/PageHeader'
import { useParams } from '@tanstack/react-router'
import { useProductDetail, useProductVariantsList } from '@/api/queries'
import { useMultiModal } from '@/hooks/useModal'
import { ProductVariantFormModal, ProductVariantDeleteModal } from './components'
import { NoData, ErrorState } from '@shared/components/ui/EmptyState'
import type { ProductVariant } from '@/types/product_variant'
import { PRODUCT_COLORS } from '@/types/product_variant'
import { Plus, Edit, Trash2 } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import { formatCents } from '@/lib/utils'

type ModalType = 'create' | 'edit' | 'delete'

const COLOR_CLASSES: Record<string, string> = {
  blanc: 'bg-white text-gray-800',
  ivoire: 'bg-yellow-50 text-yellow-900',
  bordeaux: 'bg-red-900 text-red-100',
  noir: 'bg-gray-900 text-gray-100',
  rouge: 'bg-red-600 text-white',
  vert_amande: 'bg-green-200 text-green-900',
  vert_sapin: 'bg-green-800 text-green-100',
  taupe: 'bg-stone-400 text-stone-900',
}

function ColorBadge({ color }: { color?: string }) {
  if (!color) return <span className="text-dark-500">—</span>
  const label = PRODUCT_COLORS.find((c) => c.value === color)?.label ?? color
  const cls = COLOR_CLASSES[color] ?? 'bg-dark-900 text-dark-200'
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${cls}`}>
      {label}
    </span>
  )
}

export default function ProductVariantsPage() {
  const { id } = useParams({ strict: false })
  const productId = Number(id)
  const modal = useMultiModal<ProductVariant>()

  const { data: product } = useProductDetail(isNaN(productId) ? null : productId)
  const { data: variants, isLoading, error, refetch } = useProductVariantsList(
    isNaN(productId) ? null : productId
  )

  const handleOpenModal = (type: ModalType, variant?: ProductVariant) => {
    modal.open(type, variant)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <BackButton />
        <div className="flex-1">
          <PageHeader title="Variantes produit" subtitle={product?.name} />
        </div>
        <button
          onClick={() => handleOpenModal('create')}
          className="btn-primary flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Nouvelle variante</span>
        </button>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="animate-pulse divide-y divide-dark-600">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-4 py-4">
                <div className="flex-1 space-y-2">
                  <div className="h-3 skel rounded w-24" />
                </div>
                <div className="h-3 skel rounded w-16" />
                <div className="h-3 skel rounded w-20" />
                <div className="h-3 skel rounded w-10" />
                <div className="h-3 skel rounded w-10" />
              </div>
            ))}
          </div>
        ) : error ? (
          <ErrorState onRetry={() => refetch()} />
        ) : !variants || variants.length === 0 ? (
          <NoData
            onAction={() => handleOpenModal('create')}
            actionLabel="Nouvelle variante"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-dark-600">
                  <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">Label</th>
                  <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">Couleur</th>
                  <th className="text-left px-4 py-4 text-sm font-medium text-dark-400 hidden md:table-cell">Taille</th>
                  <th className="text-left px-4 py-4 text-sm font-medium text-dark-400 hidden md:table-cell">Gamme</th>
                  <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">SKU</th>
                  <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">Stock</th>
                  <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">Dispo</th>
                  <th className="text-left px-4 py-4 text-sm font-medium text-dark-400 hidden lg:table-cell">Prix override</th>
                  <th className="text-left px-4 py-4 text-sm font-medium text-dark-400">Statut</th>
                  <th className="px-4 py-4" />
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-600/50">
                {variants.map((variant) => (
                  <tr key={variant.id} className="hover:bg-dark-900/50">
                    <td className="px-4 py-4">
                      <span className="font-medium text-sm">{variant.label}</span>
                    </td>
                    <td className="px-4 py-4">
                      <ColorBadge color={variant.color} />
                    </td>
                    <td className="px-4 py-4 text-sm text-dark-300 hidden md:table-cell">
                      {variant.size ?? '—'}
                    </td>
                    <td className="px-4 py-4 text-sm text-dark-300 hidden md:table-cell">
                      {variant.gamme ?? '—'}
                    </td>
                    <td className="px-4 py-4">
                      <span className="font-mono text-sm">{variant.sku}</span>
                    </td>
                    <td className="px-4 py-4 text-sm">{variant.stock_quantity}</td>
                    <td className="px-4 py-4 text-sm">
                      <span className={variant.available_quantity === 0 ? 'text-dark-500' : ''}>
                        {variant.available_quantity}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-sm hidden lg:table-cell">
                      {variant.price_per_day != null
                        ? formatCents(variant.price_per_day)
                        : <span className="text-dark-500">—</span>}
                    </td>
                    <td className="px-4 py-4">
                      {variant.is_active ? (
                        <span className="px-2 py-0.5 bg-green-500/10 text-green-400 text-xs rounded-full">
                          Active
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 bg-dark-900 text-dark-400 text-xs rounded-full">
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleOpenModal('edit', variant)}
                          className="p-1.5 hover:bg-dark-600 rounded text-dark-400 hover:text-dark-50 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                          title="Modifier"
                          aria-label="Modifier la variante"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleOpenModal('delete', variant)}
                          className="p-1.5 hover:bg-red-500/10 rounded text-dark-400 hover:text-red-400 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                          title="Supprimer"
                          aria-label="Supprimer la variante"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      <ProductVariantFormModal
        isOpen={modal.isOpen('create') || modal.isOpen('edit')}
        onClose={modal.close}
        variant={modal.data}
        productId={productId}
        mode={modal.isOpen('edit') ? 'edit' : 'create'}
      />

      <ProductVariantDeleteModal
        isOpen={modal.isOpen('delete')}
        onClose={modal.close}
        variant={modal.data}
        productId={productId}
      />
    </div>
  )
}
