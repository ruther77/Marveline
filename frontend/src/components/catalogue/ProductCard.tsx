import { Package, Edit, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Product, Category } from '@/types/product'
import { getStockStatusLabel, getStockBarColor, getStockPercent } from '@/types/product'

interface ProductCardProps {
  product: Product
  categories?: Category[]
  onEdit: (product: Product) => void
  onDelete: (product: Product) => void
}

export function ProductCard({ product, categories, onEdit, onDelete }: ProductCardProps) {
  const stockPercent = getStockPercent(product)
  const barColor = getStockBarColor(product)
  const stockLabel = getStockStatusLabel(product)
  const categoryName = categories?.find((c) => c.slug === product.category)?.name || product.category

  return (
    <div className="bg-dark-800 rounded-xl border border-dark-700 p-4 hover:border-dark-600 transition-colors group">
      {/* Icon + Status */}
      <div className="flex items-start justify-between mb-3">
        <div className="p-2.5 bg-dark-700 rounded-lg">
          <Package className="w-5 h-5 text-primary-500" />
        </div>
        <span
          className={cn(
            'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
            product.is_active
              ? 'bg-green-500/10 text-green-500'
              : 'bg-dark-700 text-dark-400'
          )}
        >
          {product.is_active ? 'Actif' : 'Inactif'}
        </span>
      </div>

      {/* Name + Category */}
      <h3 className="font-semibold text-white truncate">{product.name}</h3>
      <div className="flex items-center gap-2 mt-1">
        <span className="text-xs px-2 py-0.5 bg-primary-500/10 text-primary-400 rounded-full">
          {categoryName}
        </span>
        <span className="text-xs font-mono text-dark-500">{product.sku}</span>
      </div>

      {/* Price */}
      <div className="mt-3">
        <span className="text-lg font-bold text-white">
          {product.price_per_day_euros.toFixed(2)} €
        </span>
        <span className="text-xs text-dark-500 ml-1">/jour</span>
      </div>

      {/* Stock bar */}
      <div className="mt-3">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-dark-400">
            {product.available_quantity}/{product.stock_quantity}
          </span>
          <span className={cn('font-medium', barColor.replace('bg-', 'text-'))}>
            {stockLabel}
          </span>
        </div>
        <div className="h-1.5 bg-dark-700 rounded-full overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all', barColor)}
            style={{ width: `${Math.min(stockPercent, 100)}%` }}
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-3 border-t border-dark-700">
        <button
          onClick={() => onEdit(product)}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm text-dark-300 hover:text-white hover:bg-dark-700 rounded-lg transition-colors"
        >
          <Edit className="w-3.5 h-3.5" />
          Modifier
        </button>
        <button
          onClick={() => onDelete(product)}
          className="flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}
