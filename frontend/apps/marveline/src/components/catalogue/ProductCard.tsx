import { Package, Edit, Trash2, Palette } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Product, Category } from '@/types/product'
import { getStockStatusLabel, getStockBarColor, getStockPercent, CATEGORY_LABELS } from '@/types/product'

interface ProductCardProps {
  product: Product
  categories?: Category[]
  onEdit: (product: Product) => void
  onDelete: (product: Product) => void
  onVariants?: (product: Product) => void
  onClick?: (product: Product) => void
}

export function ProductCard({ product, categories, onEdit, onDelete, onVariants, onClick }: ProductCardProps) {
  const stockPercent = getStockPercent(product)
  const barColor = getStockBarColor(product)
  const stockLabel = getStockStatusLabel(product)
  const categoryName = categories?.find((c) => c.slug === product.category)?.name
    ?? CATEGORY_LABELS[product.category]
    ?? product.category.replace(/_/g, ' ')

  return (
    <div className="card hover:border-[var(--border2)] group overflow-hidden transition-colors" style={{ padding: 0 }}>
      {/* Image banner — cliquable vers la fiche */}
      <div
        className={cn('relative w-full h-36 bg-dark-900', onClick && 'cursor-pointer')}
        onClick={onClick ? () => onClick(product) : undefined}
      >
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            loading="lazy"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Package className="w-10 h-10 text-dark-500" />
          </div>
        )}
        <span
          className={cn(
            'absolute top-2 right-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium backdrop-blur-sm',
            product.is_active
              ? 'bg-green-500/20 text-green-400 border border-green-500/30'
              : 'bg-dark-900/70 text-dark-400 border border-dark-600'
          )}
        >
          {product.is_active ? 'Actif' : 'Inactif'}
        </span>
      </div>

      {/* Content */}
      <div className="p-4">
      {/* Name + Category — cliquable vers la fiche */}
      <h3
        className={cn('font-semibold truncate', onClick && 'cursor-pointer hover:text-primary-400 transition-colors')}
        onClick={onClick ? () => onClick(product) : undefined}
      >{product.name}</h3>
      <div className="flex items-center gap-2 mt-1">
        <span className="text-xs px-2 py-0.5 bg-primary-500/10 text-primary-400 rounded-full">
          {categoryName}
        </span>
        <span className="text-xs font-mono text-dark-500">{product.sku}</span>
      </div>

      {/* Price */}
      <div className="mt-4">
        <span className="text-lg font-bold">
          {product.price_per_day_euros.toFixed(2)} €
        </span>
        <span className="text-xs text-dark-500 ml-1">/jour</span>
      </div>

      {/* Stock bar */}
      <div className="mt-4">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-dark-400">
            {product.available_quantity}/{product.stock_quantity}
          </span>
          <span className={cn('font-medium', barColor.replace('bg-', 'text-'))}>
            {stockLabel}
          </span>
        </div>
        <div className="h-1.5 bg-dark-950 rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all', barColor)}
            style={{ width: `${Math.min(stockPercent, 100)}%` }}
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-dark-600">
        <button
          onClick={() => onEdit(product)}
          className="flex-1 flex items-center justify-center gap-1.5 px-4 py-1.5 text-sm text-dark-300 hover:text-dark-50 hover:bg-dark-600 rounded-lg transition-colors"
        >
          <Edit className="w-3.5 h-3.5" />
          Modifier
        </button>
        {onVariants && (
          <button
            onClick={() => onVariants(product)}
            className="flex items-center justify-center gap-1.5 px-4 py-1.5 text-sm text-primary-400 hover:text-primary-300 hover:bg-primary-500/10 rounded-lg transition-colors"
          >
            <Palette className="w-3.5 h-3.5" />
          </button>
        )}
        <button
          onClick={() => onDelete(product)}
          className="flex items-center justify-center gap-1.5 px-4 py-1.5 text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      </div>{/* /Content */}
    </div>
  )
}
