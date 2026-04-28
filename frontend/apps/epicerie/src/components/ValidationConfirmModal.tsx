/**
 * Modal de confirmation avant validation d'un import ETL.
 *
 * Affiche un résumé : lignes erreur/warning/valid, montants, écart réconciliation.
 * L'opérateur confirme ou annule explicitement.
 */
import React, { useMemo } from 'react'
import { AlertTriangle, CheckCircle, XCircle } from 'lucide-react'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import type { LigneFactureRead, EtlImportDetail } from '@/types/etl_import'
import { validateLigne } from '@/types/etl_import'

function formatCents(cts: number | null | undefined): string {
  if (cts === null || cts === undefined) return '—'
  return (cts / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

interface ValidationConfirmModalProps {
  lignes: LigneFactureRead[]
  detail: EtlImportDetail
  loading: boolean
  onConfirm: () => void
  onCancel: () => void
}

export default function ValidationConfirmModal({
  lignes,
  detail,
  loading,
  onConfirm,
  onCancel,
}: ValidationConfirmModalProps) {
  const trapRef = useFocusTrap<HTMLDivElement>(onCancel)

  const stats = useMemo(() => {
    let valid = 0, warning = 0, error = 0
    for (const l of lignes) {
      const v = validateLigne(l)
      if (v.status === 'valid') valid++
      else if (v.status === 'warning') warning++
      else error++
    }
    return { valid, warning, error, total: lignes.length }
  }, [lignes])

  const ecart = detail.montant_ht_total && detail.montant_ht_calcule
    ? Math.abs(detail.montant_ht_total - detail.montant_ht_calcule)
    : 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onCancel}>
      <div ref={trapRef as React.Ref<HTMLDivElement>} role="dialog" aria-modal="true"
        className="bg-white rounded-2xl border border-slate-200 w-full max-w-md shadow-xl"
        onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-slate-200">
          <h2 className="text-[15px] font-bold text-slate-900">Confirmer la validation</h2>
          <p className="text-[12px] text-slate-500 mt-0.5">
            Cette action va créer les mouvements de stock et la facture fournisseur.
          </p>
        </div>

        <div className="px-5 py-4 space-y-3">
          {/* Stats lignes */}
          <div className="flex gap-3">
            <div className="flex items-center gap-1.5 text-[12px]">
              <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
              <span className="text-slate-700">{stats.valid} valides</span>
            </div>
            <div className="flex items-center gap-1.5 text-[12px]">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
              <span className="text-slate-700">{stats.warning} à vérifier</span>
            </div>
            <div className="flex items-center gap-1.5 text-[12px]">
              <XCircle className="h-3.5 w-3.5 text-red-600" />
              <span className="text-slate-700">{stats.error} en erreur</span>
            </div>
          </div>

          {/* Alerte erreurs */}
          {stats.error > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-[12px] text-red-700">
              {stats.error} ligne{stats.error > 1 ? 's' : ''} sans quantité ou sans prix — elles ne généreront pas de mouvement de stock.
            </div>
          )}

          {/* Montants */}
          <div className="bg-slate-50 rounded-lg px-3 py-2 space-y-1">
            <div className="flex justify-between text-[12px]">
              <span className="text-slate-500">Montant HT déclaré</span>
              <span className="text-slate-700 font-mono">{formatCents(detail.montant_ht_total)}</span>
            </div>
            <div className="flex justify-between text-[12px]">
              <span className="text-slate-500">Montant TTC déclaré</span>
              <span className="text-slate-900 font-mono font-medium">{formatCents(detail.montant_ttc_total)}</span>
            </div>
            {ecart > 100 && (
              <div className="flex justify-between text-[12px] text-amber-700">
                <span>Écart réconciliation</span>
                <span className="font-mono">{formatCents(ecart)}</span>
              </div>
            )}
          </div>
        </div>

        <div className="px-5 py-4 border-t border-slate-200 flex gap-2 justify-end">
          <button
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-[13px] text-slate-600 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-4 py-2 text-[13px] font-semibold text-white bg-emerald-600 hover:bg-emerald-500 rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? 'Validation en cours…' : 'Valider l\'import'}
          </button>
        </div>
      </div>
    </div>
  )
}
