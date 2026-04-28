import { useState } from 'react'
import { useParams } from '@tanstack/react-router'
import { useProductStock, useUpdateStockItemStatus } from '@/api/queries'
import { normalizeError } from '@shared/errors/normalizer'
import { Save } from 'lucide-react'
import { BackButton } from '@/layout/EntityBreadcrumb'
import type { StockItemStatus } from '@/types/stock_item'

const STATUS_LABELS: Record<StockItemStatus, string> = {
  available: 'Disponible',
  reserved: 'Réservé',
  on_location: 'En location',
  damaged: 'Endommagé',
  in_repair: 'En réparation',
  retired: 'Retiré',
}

const STATUSES: StockItemStatus[] = [
  'available', 'damaged', 'in_repair', 'retired',
]

export default function StockItemEditPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const [productIdStr, itemIdStr] = id.split('-')
  const productId = Number(productIdStr)
  const itemId = Number(itemIdStr)
  const isValid = !isNaN(productId) && !isNaN(itemId)

  const { data: stockDetail, isLoading, error: loadError } = useProductStock(
    isValid ? productId : null
  )
  const updateStatus = useUpdateStockItemStatus(productId)

  const item = stockDetail?.items.find(i => i.id === itemId)

  const [status, setStatus] = useState<StockItemStatus | ''>('')
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  if (item && status === '') {
    setStatus(item.status)
  }

  const handleSave = async () => {
    if (!item || updateStatus.isPending) return
    setSaveError(null)
    setSaved(false)
    try {
      await updateStatus.mutateAsync({ itemId, status: status as string })
      setSaved(true)
    } catch (err) {
      setSaveError(normalizeError(err).message || 'Erreur lors de la sauvegarde')
    }
  }

  // ── Invalid ID ─────────────────────────────────────────────────────────────
  if (!isValid) {
    return (
      <div className="max-w-lg mx-auto">
        <div className="card p-8 text-center text-danger">
          Identifiant invalide. Format attendu : productId-itemId
        </div>
      </div>
    )
  }

  // ── Loading skeleton ───────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-lg mx-auto space-y-4 animate-pulse">
        <div className="h-7 w-48 bg-dark-800 rounded" />
        <div className="h-3 w-32 bg-dark-800 rounded" />
        <div className="card p-6 space-y-4">
          <div className="h-4 w-24 bg-dark-800 rounded" />
          <div className="grid grid-cols-2 gap-3">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-12 bg-dark-800 rounded-lg" />
            ))}
          </div>
        </div>
        <div className="h-10 w-32 bg-dark-800 rounded-lg" />
      </div>
    )
  }

  // ── Error / not found ──────────────────────────────────────────────────────
  if (loadError || !item) {
    return (
      <div className="max-w-lg mx-auto">
        <div className="card p-8 text-center text-danger">
          {loadError ? normalizeError(loadError).message : 'Unité introuvable'}
        </div>
      </div>
    )
  }

  // ── Main view ──────────────────────────────────────────────────────────────
  return (
    <div className="max-w-lg mx-auto space-y-4 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <BackButton label="Retour" />
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold">Modifier l'unité #{itemId}</h1>
          {item.serial_number && (
            <p className="text-sm text-dark-400 font-mono">{item.serial_number}</p>
          )}
        </div>
      </div>

      {/* Statut */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">Statut</h2>
        <div className="grid grid-cols-2 gap-2">
          {STATUSES.map(s => (
            <button
              key={s}
              onClick={() => { setStatus(s); setSaved(false) }}
              className={[
                'py-4 px-4 rounded-xl text-sm font-medium border transition-colors min-h-[44px]',
                status === s
                  ? 'bg-primary-500/20 border-primary-500/50 text-primary-400'
                  : 'bg-dark-900 border-dark-600 text-dark-300 hover:bg-dark-600',
              ].join(' ')}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>
        <p className="text-xs text-dark-500">
          Statut actuel : <span className="text-dark-300">{STATUS_LABELS[item.status]}</span>
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-4 justify-end flex-wrap">
        {saveError != null && (
          <p className="text-sm text-danger">{saveError}</p>
        )}
        {saved && (
          <p className="text-sm text-green-400">Sauvegardé ✓</p>
        )}
        <button
          onClick={handleSave}
          disabled={updateStatus.isPending || status === item.status}
          className="btn-primary flex items-center gap-2 min-h-[44px]"
        >
          {updateStatus.isPending ? (
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Enregistrer
        </button>
      </div>
    </div>
  )
}
