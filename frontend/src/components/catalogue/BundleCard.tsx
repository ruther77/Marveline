import { useNavigate } from 'react-router-dom'
import { Package, Star, Eye, Edit, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Bundle } from '@/types/product'

interface BundleCardProps {
  bundle: Bundle
  onEdit: (bundle: Bundle) => void
  onDelete: (bundle: Bundle) => void
}

export function BundleCard({ bundle, onEdit, onDelete }: BundleCardProps) {
  const navigate = useNavigate()

  return (
    <div className="bg-dark-800 rounded-xl border border-dark-700 p-4 hover:border-dark-600 transition-colors group">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="p-2.5 bg-dark-700 rounded-lg">
          <Package className="w-5 h-5 text-primary-500" />
        </div>
        <div className="flex items-center gap-2">
          {bundle.featured && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/10 text-yellow-500">
              <Star className="w-3 h-3 fill-yellow-500" />
              Vedette
            </span>
          )}
          <span
            className={cn(
              'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
              bundle.is_active
                ? 'bg-green-500/10 text-green-500'
                : 'bg-dark-700 text-dark-400'
            )}
          >
            {bundle.is_active ? 'Actif' : 'Inactif'}
          </span>
        </div>
      </div>

      {/* Name + Description */}
      <h3 className="font-semibold text-white truncate">{bundle.name}</h3>
      {bundle.description && (
        <p className="text-sm text-dark-400 mt-1 line-clamp-2">{bundle.description}</p>
      )}

      {/* Price */}
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-lg font-bold text-white">
          {(bundle.bundle_price_euros ?? 0).toFixed(2)} €
        </span>
        {bundle.cleaning_fee > 0 && (
          <span className="text-xs text-blue-400">
            +{(bundle.cleaning_fee_euros ?? 0).toFixed(2)} € nettoyage
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-dark-700">
        <button
          onClick={() => navigate(`/products/bundles/${bundle.id}`)}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm text-dark-300 hover:text-white hover:bg-dark-700 rounded-lg transition-colors"
        >
          <Eye className="w-3.5 h-3.5" />
          Details
        </button>
        <button
          onClick={() => onEdit(bundle)}
          className="flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm text-dark-300 hover:text-white hover:bg-dark-700 rounded-lg transition-colors"
        >
          <Edit className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => onDelete(bundle)}
          className="flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}
