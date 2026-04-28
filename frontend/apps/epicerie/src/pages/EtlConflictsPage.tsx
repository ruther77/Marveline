// Route : /_app/etl-conflits
// ETL Conflits — déduplication avec diff visuel et preview merge

import { useState } from 'react'
import { Link, useSearch } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { massacorpApi } from '@/api'
import DesignationDiff from '@/components/etl/DesignationDiff'
import { Pagination } from '@/components/Pagination'

const CONFLICTS_PER_PAGE = 50

// ─── Types ──────────────────────────────────────────────────────────────────

type Suggestion = 'MERGED' | 'KEPT_SEPARATE'
type Resolution = 'MERGED' | 'KEPT_SEPARATE' | 'PENDING'

interface EtlConflict {
  id: number
  etl_import_id: number | null
  catalogue_produit_id: number | null
  score_similarite: number | null
  designation_entrante: string
  designation_existante: string | null
  ean_a: string | null
  ean_b: string | null
  type_conflit: string | null
  suggestion: Suggestion | null
  resolution: Resolution
  created_at: string
  updated_at: string
}

interface EtlConflictStats {
  total: number; pending: number; merged: number; kept_separate: number
  by_type: Record<string, number>
}

// ─── Helpers ────────────────────────────────────────────────────────────────

const SUGGESTION_LABEL: Record<Suggestion, string> = { MERGED: 'Même produit', KEPT_SEPARATE: 'Produits différents' }
const SUGGESTION_BADGE: Record<Suggestion, string> = {
  MERGED: 'inline-block px-2 py-0.5 rounded text-xs font-medium bg-green-50 text-green-600',
  KEPT_SEPARATE: 'inline-block px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-500',
}
const RESOLUTION_LABEL: Record<string, string> = { MERGED: 'Même produit', KEPT_SEPARATE: 'Produits différents' }
const RESOLUTION_BADGE: Record<string, string> = {
  MERGED: 'inline-block px-2 py-0.5 rounded text-xs font-medium bg-green-50 text-green-600',
  KEPT_SEPARATE: 'inline-block px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-500',
}

function ScoreBar({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-slate-400">—</span>
  const pct = Math.round(score * 100)
  const color = score >= 0.9 ? 'bg-green-500' : score >= 0.75 ? 'bg-amber-400' : 'bg-red-400'
  return (
    <div className="flex items-center gap-2">
      <div className="w-14 h-1.5 rounded-full bg-slate-200 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-slate-500">{pct} %</span>
    </div>
  )
}

// ─── Detail Modal (avec diff visuel + preview merge) ────────────────────────

function DetailModal({ conflict, onClose }: { conflict: EtlConflict; onClose: () => void }) {
  const qc = useQueryClient()
  const { mutate: resolve, isPending } = useMutation({
    mutationFn: (resolution: 'MERGED' | 'KEPT_SEPARATE') =>
      massacorpApi.post('/admin/etl/conflicts/resolve', { ids: [conflict.id], resolution }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['etl-conflicts'] })
      qc.invalidateQueries({ queryKey: ['etl-conflicts-stats'] })
      qc.invalidateQueries({ queryKey: ['etl-imports'] })
      qc.invalidateQueries({ queryKey: ['etl-import-detail'] })
      onClose()
    },
  })

  const score = conflict.score_similarite
  const pct = score !== null ? Math.round(score * 100) : 0
  const color = score !== null ? (score >= 0.9 ? 'text-green-600' : score >= 0.75 ? 'text-amber-500' : 'text-red-500') : 'text-slate-400'

  // Preview merge : combine les infos
  const mergePreview = conflict.designation_existante
    ? `${conflict.designation_existante} (EAN: ${conflict.ean_b || conflict.ean_a || '—'})`
    : conflict.designation_entrante

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <p className="font-semibold text-slate-900">Conflit #{conflict.id}</p>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 text-xl leading-none">&times;</button>
        </div>

        <div className="px-5 py-5 space-y-5">
          {/* Score */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-500">Ressemblance</span>
            {score !== null ? (
              <>
                <span className={`text-2xl font-bold font-mono ${color}`}>{pct} %</span>
                <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
                  <div className={`h-full rounded-full ${score >= 0.9 ? 'bg-green-500' : score >= 0.75 ? 'bg-amber-400' : 'bg-red-400'}`}
                    style={{ width: `${pct}%` }} />
                </div>
              </>
            ) : <span className="text-slate-400">—</span>}
          </div>

          {/* Diff visuel */}
          <DesignationDiff
            textA={conflict.designation_entrante}
            textB={conflict.designation_existante ?? '—'}
          />

          {/* EAN */}
          {(conflict.ean_a || conflict.ean_b) && (
            <div className="flex gap-4 text-xs">
              {conflict.ean_a && <span className="text-slate-500">EAN entrante: <span className="font-mono text-slate-700">{conflict.ean_a}</span></span>}
              {conflict.ean_b && <span className="text-slate-500">EAN catalogue: <span className="font-mono text-slate-700">{conflict.ean_b}</span></span>}
            </div>
          )}

          {/* Preview merge */}
          {conflict.resolution === 'PENDING' && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
              <p className="text-[11px] font-semibold text-emerald-600 uppercase tracking-wide mb-1">Résultat si fusionné</p>
              <p className="text-sm text-emerald-800 font-medium">{mergePreview}</p>
            </div>
          )}

          {/* Suggestion */}
          {conflict.suggestion && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500">Suggestion :</span>
              <span className={SUGGESTION_BADGE[conflict.suggestion]}>{SUGGESTION_LABEL[conflict.suggestion]}</span>
            </div>
          )}

          {/* Actions */}
          {conflict.resolution === 'PENDING' ? (
            <div className="flex gap-2 pt-2">
              <button disabled={isPending} onClick={() => resolve('MERGED')}
                className="flex-1 py-2 rounded-lg bg-green-600 text-white text-sm font-semibold hover:bg-green-500 disabled:opacity-50">
                C'est le même produit
              </button>
              <button disabled={isPending} onClick={() => resolve('KEPT_SEPARATE')}
                className="flex-1 py-2 rounded-lg border border-slate-300 text-slate-600 text-sm hover:bg-slate-50 disabled:opacity-50">
                Ce sont deux produits différents
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 pt-2 text-sm text-slate-500">
              <span>Résolu :</span>
              <span className={RESOLUTION_BADGE[conflict.resolution]}>{RESOLUTION_LABEL[conflict.resolution]}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Batch Modal ────────────────────────────────────────────────────────────

function BatchModal({ selected, onClose }: { selected: number[]; onClose: () => void }) {
  const qc = useQueryClient()
  const { mutate: resolve, isPending } = useMutation({
    mutationFn: (payload: { ids: number[]; resolution: 'MERGED' | 'KEPT_SEPARATE' }) =>
      massacorpApi.post('/admin/etl/conflicts/resolve', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['etl-conflicts'] })
      qc.invalidateQueries({ queryKey: ['etl-conflicts-stats'] })
      qc.invalidateQueries({ queryKey: ['etl-imports'] })
      qc.invalidateQueries({ queryKey: ['etl-import-detail'] })
      onClose()
    },
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-sm mx-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <p className="font-semibold text-slate-900">Résoudre la sélection ({selected.length})</p>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-900 text-xl leading-none">&times;</button>
        </div>
        <div className="px-5 py-5 space-y-3">
          <p className="text-sm text-slate-500">Appliquer la même résolution aux {selected.length} conflits sélectionnés :</p>
          <button disabled={isPending} onClick={() => resolve({ ids: selected, resolution: 'MERGED' })}
            className="w-full py-2.5 rounded-lg bg-green-600 text-white text-sm font-semibold hover:bg-green-500 disabled:opacity-50">
            C'est le même produit — appliquer à la sélection
          </button>
          <button disabled={isPending} onClick={() => resolve({ ids: selected, resolution: 'KEPT_SEPARATE' })}
            className="w-full py-2.5 rounded-lg border border-slate-300 text-slate-600 text-sm hover:bg-slate-50 disabled:opacity-50">
            Ce sont des produits différents — appliquer à la sélection
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Page ───────────────────────────────────────────────────────────────────

const FILTERS = [
  { label: 'Tous', value: 'all' },
  { label: 'En attente', value: 'pending' },
  { label: 'Résolus', value: 'resolved' },
]

export default function EtlConflictsPage() {
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<number[]>([])
  const [detailId, setDetailId] = useState<number | null>(null)
  const [showBatch, setShowBatch] = useState(false)

  // Filter by import ID from URL search params
  let importIdFilter: number | null = null
  try {
    const search = useSearch({ strict: false }) as Record<string, unknown>
    if (search?.import_id) importIdFilter = Number(search.import_id)
  } catch { /* no search params */ }

  const { data: stats } = useQuery({
    queryKey: ['etl-conflicts-stats'],
    queryFn: () => massacorpApi.get<EtlConflictStats>('/admin/etl/conflicts/stats'),
    staleTime: 60_000,
  })

  const offset = (page - 1) * CONFLICTS_PER_PAGE
  const params = new URLSearchParams({
    filter,
    limit: String(CONFLICTS_PER_PAGE),
    offset: String(offset),
  })
  if (importIdFilter) params.set('import_id', String(importIdFilter))
  const apiUrl = `/admin/etl/conflicts?${params.toString()}`

  const { data, isLoading } = useQuery({
    queryKey: ['etl-conflicts', filter, importIdFilter, page],
    queryFn: () => massacorpApi.get<{ items: EtlConflict[]; total: number }>(apiUrl),
    staleTime: 30_000,
    placeholderData: prev => prev,
  })

  function handleFilterChange(next: string) {
    setFilter(next)
    setPage(1)
    setSelected([])
  }

  const rawItems = data?.items ?? []
  const total = data?.total ?? 0
  const items = [...rawItems].sort((a, b) => {
    const aPending = a.resolution === 'PENDING' ? 0 : 1
    const bPending = b.resolution === 'PENDING' ? 0 : 1
    if (aPending !== bPending) return aPending - bPending
    return (b.score_similarite ?? 0) - (a.score_similarite ?? 0)
  })
  const detailConflict = items.find(c => c.id === detailId) ?? null

  const toggleSelect = (id: number) => setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  const pendingItems = items.filter(c => c.resolution === 'PENDING')
  const allSelected = pendingItems.length > 0 && pendingItems.every(c => selected.includes(c.id))
  const toggleAll = () => setSelected(allSelected ? [] : pendingItems.map(c => c.id))

  return (
    <div className="flex flex-col min-h-0">
      {/* Header */}
      <div className="px-4 sm:px-7 pt-6 pb-4 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-slate-900">ETL — Conflits</h1>
              {importIdFilter && (
                <span className="text-xs bg-violet-50 text-violet-600 px-2 py-0.5 rounded-lg font-medium">
                  Import #{importIdFilter}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-0.5">Détection automatique de doublons dans votre catalogue</p>
          </div>
          <div className="flex items-center gap-2">
            {importIdFilter && (
              <Link to="/etl-conflits" className="text-xs text-slate-500 hover:text-slate-700 underline">
                Voir tous
              </Link>
            )}
            <button disabled={selected.length === 0} onClick={() => setShowBatch(true)}
              className="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-semibold hover:bg-green-500 disabled:opacity-40 disabled:cursor-not-allowed">
              Résoudre ({selected.length})
            </button>
          </div>
        </div>

        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
            {[
              { label: 'Total', value: stats.total, color: 'text-slate-900' },
              { label: 'En attente', value: stats.pending, color: 'text-amber-600' },
              { label: 'Fusionnés', value: stats.merged, color: 'text-green-600' },
              { label: 'Gardés séparés', value: stats.kept_separate, color: 'text-slate-500' },
            ].map(({ label, value, color }) => (
              <div key={label} className="bg-slate-50 rounded-lg px-3 py-2.5 text-center">
                <p className={`text-xl font-bold font-mono ${color}`}>{value}</p>
                <p className="text-[11px] text-slate-400 mt-0.5">{label}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Filtres */}
      <div className="px-4 sm:px-7 py-3 border-b border-slate-200 bg-white flex gap-2">
        {FILTERS.map(f => (
          <button key={f.value} onClick={() => handleFilterChange(f.value)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              filter === f.value ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
            }`}>
            {f.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="py-10 text-center text-sm text-slate-400">Chargement…</div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center">
            <div className="text-4xl mb-3">✅</div>
            <p className="text-sm text-slate-500">Aucun conflit {filter === 'pending' ? 'en attente' : ''}</p>
          </div>
        ) : (
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 bg-white z-10">
              <tr className="border-b border-slate-200">
                <th className="px-5 py-2.5 w-8">
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} className="rounded border-slate-300" />
                </th>
                {['Import', 'Score', 'Désignation entrante', 'Désignation catalogue', 'Suggestion', 'Résolution', ''].map(h => (
                  <th key={h} className="text-left text-[11.5px] font-semibold text-slate-500 px-4 py-2.5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(c => (
                <tr key={c.id} className={`border-b border-slate-100 last:border-0 ${
                  selected.includes(c.id) ? 'bg-green-50' : 'hover:bg-slate-50'
                }`}>
                  <td className="px-5 py-2.5">
                    {c.resolution === 'PENDING' && (
                      <input type="checkbox" checked={selected.includes(c.id)}
                        onChange={() => toggleSelect(c.id)} className="rounded border-slate-300" />
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    {c.etl_import_id ? (
                      <Link to="/etl-imports/$id" params={{ id: String(c.etl_import_id) }} onClick={e => e.stopPropagation()}
                        className="text-[11px] text-violet-600 hover:underline font-mono">
                        #{c.etl_import_id}
                      </Link>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-2.5"><ScoreBar score={c.score_similarite} /></td>
                  <td className="px-4 py-2.5 text-slate-900 font-medium max-w-[200px] truncate">{c.designation_entrante}</td>
                  <td className="px-4 py-2.5 text-slate-700 max-w-[200px] truncate">{c.designation_existante ?? '—'}</td>
                  <td className="px-4 py-2.5">
                    {c.suggestion ? <span className={SUGGESTION_BADGE[c.suggestion]}>{SUGGESTION_LABEL[c.suggestion]}</span> : <span className="text-slate-400 text-xs">—</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    {c.resolution !== 'PENDING'
                      ? <span className={RESOLUTION_BADGE[c.resolution]}>{RESOLUTION_LABEL[c.resolution]}</span>
                      : <span className="text-slate-400 text-xs">—</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    <button onClick={() => setDetailId(c.id)} className="text-xs text-emerald-600 hover:underline">Voir</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {total > CONFLICTS_PER_PAGE && (
        <div className="px-4 sm:px-7 py-3 border-t border-slate-200 bg-white">
          <Pagination
            page={page}
            total={total}
            perPage={CONFLICTS_PER_PAGE}
            onPageChange={setPage}
            itemLabel="conflit"
          />
        </div>
      )}

      {/* Modals */}
      {detailConflict !== null && <DetailModal conflict={detailConflict} onClose={() => setDetailId(null)} />}
      {showBatch && <BatchModal selected={selected} onClose={() => { setShowBatch(false); setSelected([]) }} />}
    </div>
  )
}
