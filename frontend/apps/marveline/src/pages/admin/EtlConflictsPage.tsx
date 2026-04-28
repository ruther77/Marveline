// Route : /_massacorp/etl-conflicts
// Administration ETL — Conflits de déduplication (Jaro-Winkler / ADR-07)

import { PageHeader } from '@/components/PageHeader'
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/fetchClient'

// ─── Types ────────────────────────────────────────────────────────────────────

// Suggestion ETL automatique générée par le pipeline (ADR-07)
type Suggestion = 'MERGED' | 'KEPT_SEPARATE'

// Resolution persistée en base — PENDING = non résolu (jamais null en DB)
type Resolution = 'MERGED' | 'KEPT_SEPARATE' | 'PENDING'

interface EtlConflict {
  id: number
  etl_import_id: number | null
  catalogue_produit_id: number | null
  score_similarite: number | null    // 0.0 – 1.0 Jaro-Winkler
  designation_entrante: string       // désignation de la ligne importée
  designation_existante: string | null  // désignation du produit catalogue
  ean_a: string | null
  ean_b: string | null
  type_conflit: string | null
  suggestion: Suggestion | null
  resolution: Resolution
  created_at: string
  updated_at: string
}

interface EtlConflictStats {
  total: number
  pending: number
  merged: number
  kept_separate: number
  by_type: Record<string, number>
}

interface ResolutionPayload {
  ids: number[]
  resolution: 'MERGED' | 'KEPT_SEPARATE'
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const SUGGESTION_BADGE: Record<Suggestion, string> = {
  MERGED:        'badge badge-green',
  KEPT_SEPARATE: 'badge badge-muted',
}

const SUGGESTION_LABEL: Record<Suggestion, string> = {
  MERGED:        'Fusionner',
  KEPT_SEPARATE: 'Garder séparé',
}

const RESOLUTION_BADGE: Record<string, string> = {
  MERGED:        'badge badge-green',
  KEPT_SEPARATE: 'badge badge-muted',
}

const RESOLUTION_LABEL: Record<string, string> = {
  MERGED:        'Fusionné',
  KEPT_SEPARATE: 'Gardés séparés',
}

function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-[12px] text-[#a1a1a6]">—</span>
  const pct = Math.round(score * 100)
  const color = score >= 0.9 ? 'bg-green-500' : score >= 0.75 ? 'bg-amber-400' : 'bg-red-400'
  return (
    <div className="flex items-center gap-2">
      <div className="w-14 h-1.5 rounded-full bg-[#e5e5ea] overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[12px] font-mono text-[#6e6e73]">{score.toFixed(2)}</span>
    </div>
  )
}

// ─── Modals ───────────────────────────────────────────────────────────────────

function DetailModal({ conflict, onClose }: { conflict: EtlConflict; onClose: () => void }) {
  const qc = useQueryClient()
  const { mutate: resolve, isPending } = useMutation({
    mutationFn: (resolution: 'MERGED' | 'KEPT_SEPARATE') =>
      api.post('/admin/etl/conflicts/resolve', { ids: [conflict.id], resolution }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['etl-conflicts'] })
      qc.invalidateQueries({ queryKey: ['etl-conflicts-stats'] })
      onClose()
    },
  })

  const score = conflict.score_similarite
  const pct = score !== null ? Math.round(score * 100) : 0
  const color = score !== null
    ? score >= 0.9 ? 'text-green-600' : score >= 0.75 ? 'text-amber-500' : 'text-red-500'
    : 'text-[#a1a1a6]'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#d2d2d7]">
          <p className="font-semibold text-[#1d1d1f]">Détail conflit #{conflict.id}</p>
          <button onClick={onClose} className="text-[#6e6e73] hover:text-[#1d1d1f] text-xl leading-none">✕</button>
        </div>

        <div className="px-5 py-5 space-y-5">
          {/* Score */}
          <div className="flex items-center gap-3">
            <span className="text-[13px] text-[#6e6e73]">Score Jaro-Winkler</span>
            {score !== null ? (
              <>
                <span className={`text-2xl font-bold font-mono ${color}`}>{score.toFixed(3)}</span>
                <div className="flex-1 h-2 rounded-full bg-[#e5e5ea] overflow-hidden">
                  <div
                    className={`h-full rounded-full ${score >= 0.9 ? 'bg-green-500' : score >= 0.75 ? 'bg-amber-400' : 'bg-red-400'}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-[12px] text-[#6e6e73]">{pct}%</span>
              </>
            ) : (
              <span className="text-[#a1a1a6]">—</span>
            )}
          </div>

          {/* Désignations */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#f5f5f7] rounded-lg p-3">
              <p className="text-[11px] font-semibold text-[#a1a1a6] uppercase tracking-wide mb-1">Entrante</p>
              <p className="font-medium text-[#1d1d1f] text-[13px]">{conflict.designation_entrante}</p>
              {conflict.ean_a && <p className="text-[11px] text-[#6e6e73] font-mono mt-1">EAN: {conflict.ean_a}</p>}
            </div>
            <div className="bg-[#f5f5f7] rounded-lg p-3">
              <p className="text-[11px] font-semibold text-[#a1a1a6] uppercase tracking-wide mb-1">Catalogue</p>
              <p className="font-medium text-[#1d1d1f] text-[13px]">{conflict.designation_existante ?? '—'}</p>
              {conflict.ean_b && <p className="text-[11px] text-[#6e6e73] font-mono mt-1">EAN: {conflict.ean_b}</p>}
            </div>
          </div>

          {/* Suggestion */}
          {conflict.suggestion && (
            <div className="flex items-center gap-2">
              <span className="text-[13px] text-[#6e6e73]">Suggestion :</span>
              <span className={SUGGESTION_BADGE[conflict.suggestion]}>{SUGGESTION_LABEL[conflict.suggestion]}</span>
            </div>
          )}

          {/* Actions résolution */}
          {conflict.resolution === 'PENDING' ? (
            <div className="flex gap-2 pt-2">
              <button
                disabled={isPending}
                onClick={() => resolve('MERGED')}
                className="flex-1 py-2 rounded-lg bg-[#059669] text-white text-[13px] font-semibold hover:bg-[#047857] disabled:opacity-50"
              >
                Fusionner
              </button>
              <button
                disabled={isPending}
                onClick={() => resolve('KEPT_SEPARATE')}
                className="flex-1 py-2 rounded-lg border border-[#d2d2d7] text-[#6e6e73] text-[13px] hover:bg-[#f5f5f7] disabled:opacity-50"
              >
                Garder séparé
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 pt-2 text-[13px] text-[#6e6e73]">
              <span>Résolu :</span>
              <span className={RESOLUTION_BADGE[conflict.resolution]}>{RESOLUTION_LABEL[conflict.resolution]}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function BatchModal({ selected, onClose }: { selected: number[]; onClose: () => void }) {
  const qc = useQueryClient()
  const { mutate: resolve, isPending } = useMutation({
    mutationFn: (payload: ResolutionPayload) => api.post('/admin/etl/conflicts/resolve', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['etl-conflicts'] })
      qc.invalidateQueries({ queryKey: ['etl-conflicts-stats'] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#d2d2d7]">
          <p className="font-semibold text-[#1d1d1f]">Résoudre la sélection ({selected.length})</p>
          <button onClick={onClose} className="text-[#6e6e73] hover:text-[#1d1d1f] text-xl leading-none">✕</button>
        </div>
        <div className="px-5 py-5 space-y-3">
          <p className="text-[13px] text-[#6e6e73]">Appliquer la même résolution aux {selected.length} conflits sélectionnés :</p>
          <div className="flex flex-col gap-2">
            <button
              disabled={isPending}
              onClick={() => resolve({ ids: selected, resolution: 'MERGED' })}
              className="py-2.5 rounded-lg bg-[#059669] text-white text-[13px] font-semibold hover:bg-[#047857] disabled:opacity-50"
            >
              Fusionner tous
            </button>
            <button
              disabled={isPending}
              onClick={() => resolve({ ids: selected, resolution: 'KEPT_SEPARATE' })}
              className="py-2.5 rounded-lg border border-[#d2d2d7] text-[#6e6e73] text-[13px] hover:bg-[#f5f5f7] disabled:opacity-50"
            >
              Garder tous séparés
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Page principale ──────────────────────────────────────────────────────────

const FILTERS = [
  { label: 'Tous',     value: 'all' },
  { label: 'En attente', value: 'pending' },
  { label: 'Résolus',  value: 'resolved' },
]

export default function EtlConflictsPage() {
  const [filter, setFilter]       = useState('all')
  const [selected, setSelected]   = useState<number[]>([])
  const [detailId, setDetailId]   = useState<number | null>(null)
  const [showBatch, setShowBatch] = useState(false)

  const { data: stats } = useQuery({
    queryKey: ['etl-conflicts-stats'],
    queryFn: () => api.get<EtlConflictStats>('/admin/etl/conflicts/stats'),
    staleTime: 60_000,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['etl-conflicts', filter],
    queryFn: () => api.get<{ items: EtlConflict[]; total: number }>(`/admin/etl/conflicts?filter=${filter}`),
    staleTime: 30_000,
  })

  const rawItems = data?.items ?? []
  // Tri intelligent : PENDING en premier, puis par score décroissant
  const items = [...rawItems].sort((a, b) => {
    const aPending = a.resolution === 'PENDING' ? 0 : 1
    const bPending = b.resolution === 'PENDING' ? 0 : 1
    if (aPending !== bPending) return aPending - bPending
    return (b.score_similarite ?? 0) - (a.score_similarite ?? 0)
  })
  const detailConflict = items.find(c => c.id === detailId) ?? null

  function toggleSelect(id: number) {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  function toggleAll() {
    const pendingIds = items.filter(c => c.resolution === 'PENDING').map(c => c.id)
    setSelected(prev => prev.length === pendingIds.length ? [] : pendingIds)
  }

  const pendingItems = items.filter(c => c.resolution === 'PENDING')
  const allSelected = pendingItems.length > 0 && pendingItems.every(c => selected.includes(c.id))

  return (
    <div className="flex flex-col min-h-0">
      {/* Header */}
      <div className="px-7 pt-6 pb-4 border-b border-[#d2d2d7] bg-white">
        <div className="flex items-center justify-between gap-3">
          <PageHeader title="ETL — Conflits" subtitle="Déduplication par score Jaro-Winkler (ADR-07)" />
          <button
            disabled={selected.length === 0}
            onClick={() => setShowBatch(true)}
            className="px-4 py-2 rounded-lg bg-[#059669] text-white text-[13px] font-semibold hover:bg-[#047857] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Résoudre la sélection{selected.length > 0 ? ` (${selected.length})` : ''}
          </button>
        </div>

        {/* Stats bar */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
            {[
              { label: 'Total conflits',    value: stats.total,         color: 'text-[#1d1d1f]' },
              { label: 'En attente',        value: stats.pending,       color: 'text-amber-600' },
              { label: 'Fusionnés',         value: stats.merged,        color: 'text-green-600' },
              { label: 'Gardés séparés',    value: stats.kept_separate, color: 'text-[#6e6e73]' },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-[#f5f5f7] rounded-lg px-3 py-2.5 text-center">
                <p className={`text-xl font-bold font-mono ${color}`}>{value}</p>
                <p className="text-[11px] text-[#a1a1a6] mt-0.5">{label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Filtres */}
      <div className="px-7 py-3 border-b border-[#d2d2d7] bg-white flex gap-2">
        {FILTERS.map(f => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-3 py-1 rounded-full text-[12px] font-medium transition-colors ${
              filter === f.value
                ? 'bg-[#1d1d1f] text-white'
                : 'bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e5e5ea]'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="py-10 text-center text-[13px] text-[#a1a1a6]">Chargement…</div>
        ) : items.length === 0 ? (
          <p className="py-10 text-center text-[13px] text-[#a1a1a6]">Aucun conflit</p>
        ) : (
          <table className="w-full text-[13px] border-collapse">
            <thead className="sticky top-0 bg-white z-10">
              <tr className="border-b border-[#d2d2d7]">
                <th className="px-5 py-2.5 w-8">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleAll}
                    className="rounded border-[#d2d2d7]"
                  />
                </th>
                {['Score', 'Désignation entrante', 'Désignation catalogue', 'Suggestion', 'Résolution', 'Actions'].map(h => (
                  <th key={h} className="text-left text-[11.5px] font-semibold text-[#6e6e73] px-4 py-2.5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(c => (
                <tr
                  key={c.id}
                  className={`border-b border-[#e5e5ea] last:border-0 ${
                    selected.includes(c.id) ? 'bg-[#f0fdf4]' : 'hover:bg-[#f5f5f7]'
                  }`}
                >
                  <td className="px-5 py-2.5">
                    {c.resolution === 'PENDING' && (
                      <input
                        type="checkbox"
                        checked={selected.includes(c.id)}
                        onChange={() => toggleSelect(c.id)}
                        onClick={e => e.stopPropagation()}
                        className="rounded border-[#d2d2d7]"
                      />
                    )}
                  </td>
                  <td className="px-4 py-2.5"><ScoreBar score={c.score_similarite} /></td>
                  <td className="px-4 py-2.5 text-[#1d1d1f] font-medium max-w-[200px] truncate">{c.designation_entrante}</td>
                  <td className="px-4 py-2.5 text-[#1d1d1f] max-w-[200px] truncate">{c.designation_existante ?? '—'}</td>
                  <td className="px-4 py-2.5">
                    {c.suggestion
                      ? <span className={SUGGESTION_BADGE[c.suggestion]}>{SUGGESTION_LABEL[c.suggestion]}</span>
                      : <span className="text-[#a1a1a6] text-[12px]">—</span>
                    }
                  </td>
                  <td className="px-4 py-2.5">
                    {c.resolution !== 'PENDING'
                      ? <span className={RESOLUTION_BADGE[c.resolution]}>{RESOLUTION_LABEL[c.resolution]}</span>
                      : <span className="text-[#a1a1a6] text-[12px]">—</span>
                    }
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      onClick={() => setDetailId(c.id)}
                      className="text-[12px] text-[#059669] hover:underline"
                    >
                      Voir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modals */}
      {detailConflict !== null && (
        <DetailModal conflict={detailConflict} onClose={() => setDetailId(null)} />
      )}
      {showBatch && (
        <BatchModal selected={selected} onClose={() => { setShowBatch(false); setSelected([]) }} />
      )}
    </div>
  )
}
