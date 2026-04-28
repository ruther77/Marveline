// Header sticky import — score, réconciliation inline, actions CTA

import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import type { EtlImportDetail, EtlImportUpdateRequest } from '@/types/etl_import'
import { formatCents, formatDate, STATUT_LABELS, STATUT_COLORS } from '@/utils/etl-helpers'
import EuroInput from '@/components/EuroInput'

interface ImportReviewHeaderProps {
  detail: EtlImportDetail
  importId: number
  isPreview: boolean
  dirty: boolean
  isActing: boolean
  showCelebration: boolean
  onSave: () => void
  onValidate: () => void
  onReject: () => void
  onRevert: () => void
  onCancelEdits: () => void
  onUpdateMeta: (data: EtlImportUpdateRequest) => void
  // Option B — édition post-validation
  postValidatedEditing: boolean
  postValidatedDirty: boolean
  postValidatedSaving?: boolean
  onStartPostValidatedEdit: () => void
  onSavePostValidatedEdits: () => void
  onCancelPostValidatedEdit: () => void
  // P7 — Reprendre en édition (REJECTED/REVERTED → PREVIEW)
  onReopen: () => void
  onReclassify?: () => void
  isReclassifying?: boolean
}

function ScoreCircle({ score }: { score: number | null }) {
  const s = score ?? 0
  const pct = Math.min(s, 100)
  const color = s >= 80 ? '#059669' : s >= 50 ? '#f59e0b' : '#ef4444'
  const r = 18
  const circ = 2 * Math.PI * r
  const offset = circ - (pct / 100) * circ

  return (
    <div className="relative w-12 h-12 shrink-0">
      <svg viewBox="0 0 44 44" className="w-full h-full -rotate-90">
        <circle cx="22" cy="22" r={r} fill="none" stroke="#e2e8f0" strokeWidth="4" />
        <circle cx="22" cy="22" r={r} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" className="transition-all duration-500" />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[11px] font-bold text-slate-700">
        {s}
      </span>
    </div>
  )
}

export default function ImportReviewHeader({
  detail, importId, isPreview, dirty, isActing, showCelebration,
  onSave, onValidate, onReject, onRevert, onCancelEdits, onUpdateMeta,
  postValidatedEditing, postValidatedDirty, postValidatedSaving = false,
  onStartPostValidatedEdit, onSavePostValidatedEdits, onCancelPostValidatedEdit,
  onReopen, onReclassify, isReclassifying = false,
}: ImportReviewHeaderProps) {
  const [editingMeta, setEditingMeta] = useState(false)
  const [editData, setEditData] = useState<EtlImportUpdateRequest>({})

  const startEditMeta = () => {
    setEditData({
      numero_facture: detail.numero_facture || undefined,
      date_facture: detail.date_facture || undefined,
      montant_ht_total: detail.montant_ht_total || undefined,
    })
    setEditingMeta(true)
  }

  return (
    <div className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 py-3">
        {/* Row 1: breadcrumb + actions */}
        <div className="flex items-center gap-3 mb-3">
          <Link
            to="/etl-imports"
            className="flex items-center gap-1 text-[13px] text-slate-600 hover:text-slate-900 font-medium px-2 py-1 -mx-2 rounded hover:bg-slate-100 transition-colors"
            title="Retour à la liste des imports"
          >
            <span className="text-base leading-none">←</span>
            <span>Imports</span>
          </Link>
          <span className="text-slate-300">/</span>
          <span className="text-[13px] text-slate-800 font-semibold">#{importId}</span>

          <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUT_COLORS[detail.statut] || 'bg-slate-100 text-slate-500'}`}>
            {STATUT_LABELS[detail.statut] || detail.statut}
          </span>

          <span className="text-slate-400 text-xs">{detail.vendor_code}</span>

          <div className="flex-1" />

          {dirty && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-amber-500 font-medium px-2 py-1 bg-amber-50 rounded">Non sauvegardé</span>
              <button onClick={onCancelEdits} className="text-xs text-slate-500 hover:text-slate-700 underline">Annuler</button>
            </div>
          )}

          {isPreview && (
            <div className="flex gap-2">
              {onReclassify && (
                <button onClick={onReclassify} disabled={isActing || isReclassifying}
                  className="px-3 py-1.5 bg-violet-50 hover:bg-violet-100 text-violet-700 text-sm rounded-lg transition-colors disabled:opacity-50 flex items-center gap-1.5"
                  title="Re-classer automatiquement les lignes sans catégorie (KNN)">
                  {isReclassifying ? (
                    <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
                      <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" className="opacity-75" />
                    </svg>
                  ) : '✦'}
                  {isReclassifying ? 'Reclassification…' : 'Auto-classer'}
                </button>
              )}
              {dirty && (
                <button onClick={onSave} disabled={isActing}
                  className="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 text-white text-sm rounded-lg transition-colors disabled:opacity-50">
                  Sauvegarder
                </button>
              )}
              <button onClick={onValidate} disabled={isActing}
                className={`px-4 py-1.5 text-white text-sm font-semibold rounded-lg transition-all disabled:opacity-50 ${
                  showCelebration
                    ? 'bg-emerald-500 ring-2 ring-emerald-300 ring-offset-2 animate-pulse'
                    : 'bg-green-600 hover:bg-green-500'
                }`}>
                Valider l'import
              </button>
              <button onClick={onReject} disabled={isActing}
                className="px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-600 text-sm rounded-lg transition-colors disabled:opacity-50">
                Rejeter
              </button>
            </div>
          )}

          {detail.statut === 'VALIDATED' && !postValidatedEditing && (
            <div className="flex gap-2 items-center">
              <button onClick={onStartPostValidatedEdit}
                className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-lg transition-colors">
                Corriger une ligne
              </button>
              <button onClick={onRevert}
                className="px-2.5 py-1.5 text-amber-700 hover:bg-amber-50 text-xs rounded-lg transition-colors underline">
                Annuler l'import
              </button>
            </div>
          )}

          {(detail.statut === 'REJECTED' || detail.statut === 'REVERTED') && (
            <button
              onClick={onReopen}
              className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-lg transition-colors"
            >
              Reprendre en édition
            </button>
          )}

          {detail.statut === 'VALIDATED' && postValidatedEditing && (
            <div className="flex gap-2 items-center">
              {postValidatedDirty && !postValidatedSaving && (
                <span className="text-xs text-amber-600 font-medium px-2 py-1 bg-amber-50 rounded">
                  Corrections non enregistrées
                </span>
              )}
              <button
                onClick={onSavePostValidatedEdits}
                disabled={!postValidatedDirty || isActing || postValidatedSaving}
                className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2">
                {postValidatedSaving && (
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
                    <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" className="opacity-75" />
                  </svg>
                )}
                {postValidatedSaving ? 'Enregistrement…' : 'Enregistrer les corrections'}
              </button>
              <button
                onClick={onCancelPostValidatedEdit}
                disabled={postValidatedSaving}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-600 text-sm rounded-lg transition-colors disabled:opacity-40">
                Quitter l'édition
              </button>
            </div>
          )}
        </div>

        {/* Row 2: facture info + score */}
        <div className="flex items-center gap-4">
          <ScoreCircle score={detail.quality_score} />

          {!editingMeta ? (
            <div className="flex-1 grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
              <div>
                <span className="text-slate-400 text-xs block">N° Facture</span>
                <span className="text-slate-700">{detail.numero_facture || '—'}</span>
              </div>
              <div>
                <span className="text-slate-400 text-xs block">Date</span>
                <span className="text-slate-700">{formatDate(detail.date_facture)}</span>
              </div>
              <div>
                <span className="text-slate-400 text-xs block">HT</span>
                <span className="text-slate-700 font-mono">{formatCents(detail.montant_ht_total)}</span>
              </div>
              <div>
                <span className="text-slate-400 text-xs block">TVA</span>
                <span className="text-slate-700 font-mono">{formatCents(detail.montant_tva_total)}</span>
              </div>
              <div>
                <span className="text-slate-400 text-xs block">TTC</span>
                <span className="text-slate-900 font-medium font-mono">{formatCents(detail.montant_ttc_total)}</span>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-end gap-3">
              <div>
                <label className="text-slate-400 text-xs block mb-1">N° Facture</label>
                <input type="text" value={editData.numero_facture || ''} onChange={e => setEditData({ ...editData, numero_facture: e.target.value })}
                  className="bg-white border border-slate-300 rounded px-2 py-1 text-slate-700 text-sm w-32" />
              </div>
              <div>
                <label className="text-slate-400 text-xs block mb-1">Date</label>
                <input type="date" value={editData.date_facture || ''} onChange={e => setEditData({ ...editData, date_facture: e.target.value })}
                  className="bg-white border border-slate-300 rounded px-2 py-1 text-slate-700 text-sm" />
              </div>
              <div>
                <label className="text-slate-400 text-xs block mb-1">HT</label>
                <EuroInput value={editData.montant_ht_total ?? null} onChange={val => setEditData({ ...editData, montant_ht_total: val })} placeholder="0.00" />
              </div>
              <button onClick={() => { onUpdateMeta(editData); setEditingMeta(false) }}
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm rounded-lg">
                Sauver
              </button>
              <button onClick={() => setEditingMeta(false)}
                className="px-2 py-1.5 text-slate-500 hover:text-slate-700 text-sm">
                Annuler
              </button>
            </div>
          )}

          {isPreview && !editingMeta && (
            <button onClick={startEditMeta} className="text-emerald-600 hover:text-emerald-700 text-xs font-medium shrink-0">
              Modifier
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
