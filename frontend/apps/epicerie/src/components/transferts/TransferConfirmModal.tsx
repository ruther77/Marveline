// Confirmation avant validation transfert — action irréversible

import { formatCents } from '@/utils/etl-helpers'

interface TransferConfirmModalProps {
  nbArticles: number
  totalTtcCts: number
  loading: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function TransferConfirmModal({
  nbArticles, totalTtcCts, loading, onConfirm, onCancel,
}: TransferConfirmModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onCancel}>
      <div className="bg-white rounded-2xl w-full max-w-sm shadow-xl p-5 space-y-4" onClick={e => e.stopPropagation()}>
        <h2 className="text-base font-bold text-slate-900">Confirmer le transfert</h2>
        <p className="text-sm text-slate-600">
          <strong>{nbArticles} article{nbArticles > 1 ? 's' : ''}</strong> vont être déduits du stock
          épicerie et ajoutés au stock restaurant pour un total de{' '}
          <strong className="text-slate-900">{formatCents(totalTtcCts)} TTC</strong>.
        </p>
        <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
          Cette action est irréversible. Les mouvements de stock et la facture interne seront créés immédiatement.
        </p>
        <div className="flex gap-2 justify-end pt-1">
          <button onClick={onCancel} disabled={loading}
            className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
            Annuler
          </button>
          <button onClick={onConfirm} disabled={loading}
            className="px-4 py-2 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50">
            {loading ? 'Transfert en cours…' : 'Confirmer ✓'}
          </button>
        </div>
      </div>
    </div>
  )
}
