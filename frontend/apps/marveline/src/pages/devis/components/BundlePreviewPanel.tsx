import { Package, Loader2 } from 'lucide-react'
import { useBundlePreview } from '@/api/queries/useDevis'
import type { BundleItemPreview } from '@/types/devis'

interface BundlePreviewPanelProps {
  bundleId: number | null | undefined
  className?: string
}

/**
 * G31 — Panneau d'apercu du contenu d'un bundle avant ajout au devis.
 * Affiche les produits, variantes et quantites du bundle.
 */
export default function BundlePreviewPanel({ bundleId, className = '' }: BundlePreviewPanelProps) {
  const { data, isLoading } = useBundlePreview(bundleId)

  if (!bundleId || bundleId <= 0) return null

  if (isLoading) {
    return (
      <div className={`card rounded-xl p-4 ${className}`}>
        <div className="flex items-center gap-2 text-dark-400">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Chargement du bundle...</span>
        </div>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className={`bg-dark-800 border border-primary-500/20 rounded-xl overflow-hidden ${className}`}>
      <div className="px-4 py-3 bg-primary-500/5 border-b border-primary-500/20 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg overflow-hidden bg-primary-500/10 flex items-center justify-center shrink-0">
          {data.bundle_image_url ? (
            <img src={data.bundle_image_url} alt={data.bundle_name} loading="lazy" className="w-full h-full object-cover" />
          ) : (
            <Package className="w-4 h-4 text-primary-400" />
          )}
        </div>
        <span className="font-medium text-sm text-white truncate">{data.bundle_name}</span>
        <span className="ml-auto text-xs text-dark-400 shrink-0">
          {(data.bundle_price_cents / 100).toFixed(2)} EUR
        </span>
      </div>
      <div className="divide-y divide-dark-700">
        {data.items.map((item, i) => (
          <div key={i} className="px-4 py-2.5 flex items-center gap-3">
            <div className="w-8 h-8 rounded-md overflow-hidden bg-dark-950 flex items-center justify-center shrink-0">
              {item.product_image_url ? (
                <img src={item.product_image_url} alt={item.product_name} loading="lazy" className="w-full h-full object-cover" />
              ) : (
                <Package className="w-3.5 h-3.5 text-dark-500" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-white truncate">{item.product_name}</p>
              {item.variant_label && (
                <p className="text-xs text-dark-400 truncate">{item.variant_label}</p>
              )}
            </div>
            <span className="text-xs text-dark-300 font-mono shrink-0">x{item.quantity}</span>
          </div>
        ))}
      </div>
      <div className="px-4 py-2 bg-dark-900/50 text-xs text-dark-400">
        {data.items.length} article{data.items.length > 1 ? 's' : ''} dans ce pack
      </div>
    </div>
  )
}
