import { useNavigate } from '@tanstack/react-router'
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
    <div className="card rounded-xl hover:border-dark-600 transition-colors group overflow-hidden" style={{ padding: 0 }}>
      {/* Image banner — cliquable vers la fiche */}
      <div
        className="relative w-full h-36 bg-dark-900 cursor-pointer"
        onClick={() => navigate({ to: `/catalogue/bundles/${bundle.id}` })}
      >
        {bundle.image_url ? (
          <img
            src={bundle.image_url}
            alt={bundle.name}
            loading="lazy"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Package className="w-10 h-10 text-primary-500/60" />
          </div>
        )}
        <div className="absolute top-2 right-2 flex items-center gap-2">
          {bundle.featured && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 backdrop-blur-sm">
              <Star className="w-3 h-3 fill-yellow-400" />
              Vedette
            </span>
          )}
          <span
            className={cn(
              'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium backdrop-blur-sm',
              bundle.is_active
                ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                : 'bg-dark-900/70 text-dark-400 border border-dark-600'
            )}
          >
            {bundle.is_active ? 'Actif' : 'Inactif'}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
      {/* Name + Description */}
      <h3 className="font-semibold truncate">{bundle.name}</h3>
      {bundle.description && (
        <p className="text-sm text-dark-400 mt-1 line-clamp-2">{bundle.description}</p>
      )}

      {/* Price */}
      <div className="mt-4 flex items-baseline gap-2">
        <span className="text-lg font-bold">
          {(bundle.bundle_price_euros ?? 0).toFixed(2)} €
        </span>
        {bundle.cleaning_fee_cents > 0 && (
          <span className="text-xs text-blue-400">
            +{(bundle.cleaning_fee_euros ?? 0).toFixed(2)} € nettoyage
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-dark-600">
        <button
          onClick={() => navigate({ to: `/catalogue/bundles/${bundle.id}` })}
          className="flex-1 flex items-center justify-center gap-1.5 px-4 py-1.5 text-sm text-dark-300 hover:text-dark-50 hover:bg-dark-600 rounded-lg transition-colors"
        >
          <Eye className="w-3.5 h-3.5" />
          Details
        </button>
        <button
          onClick={() => onEdit(bundle)}
          className="flex items-center justify-center gap-1.5 px-4 py-1.5 text-sm text-dark-300 hover:text-dark-50 hover:bg-dark-600 rounded-lg transition-colors"
        >
          <Edit className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => onDelete(bundle)}
          className="flex items-center justify-center gap-1.5 px-4 py-1.5 text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      </div>{/* /Content */}
    </div>
  )
}
