// Route : /_massacorp/epicerie/historique
// Historique des ventes épicerie — 4 tabs statut + table financière + modal détail

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { massacorpApi as api } from '@/api'
import type { ModePaiement } from '@/types/epicerie-v2'

// ─── Types ────────────────────────────────────────────────────────────────────

type StatutVente = 'VALIDEE' | 'EN_ATTENTE' | 'ANNULEE'

interface VenteListItem {
  id: number
  numero_ticket: string        // VTE-YYYYMMDD-NNNN
  statut: StatutVente
  total_ttc_cts: number        // centimes
  total_tva_cts: number        // centimes
  mode_paiement: ModePaiement
  monnaie_rendue_cts: number   // centimes
  nb_articles: number
  created_at: string
}

interface LigneVenteDetail {
  produit_designation: string
  quantite: number
  prix_unitaire_cts: number
  total_ligne_cts: number
  taux_tva: number             // ‰ — ex: 850 = 8,5%
}

interface VenteDetail extends VenteListItem {
  lignes: LigneVenteDetail[]
  remise_cts: number
  remise_motif: string | null
  client_nom: string | null
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const TABS: { label: string; statut: StatutVente | null }[] = [
  { label: 'Toutes',     statut: null },
  { label: 'Confirmée',  statut: 'VALIDEE' },
  { label: 'En attente', statut: 'EN_ATTENTE' },
  { label: 'Annulée',    statut: 'ANNULEE' },
]

const STATUT_BADGE: Record<StatutVente, string> = {
  VALIDEE:    'badge badge-green',
  EN_ATTENTE: 'badge badge-yellow',
  ANNULEE:    'badge badge-red',
}

const STATUT_LABEL: Record<StatutVente, string> = {
  VALIDEE:    'Confirmée',
  EN_ATTENTE: 'En attente',
  ANNULEE:    'Annulée',
}

const PAIEMENT_LABEL: Record<ModePaiement, string> = {
  ESPECES:  'Espèces',
  CB:       'CB',
  VIREMENT: 'Virement',
}

function fmtCts(cts: number): string {
  return `${(cts / 100).toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} XPF`
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

// ─── Composants ───────────────────────────────────────────────────────────────

function TabBar({ active, counts, onChange }: {
  active: StatutVente | null
  counts: Record<string, number>
  onChange: (s: StatutVente | null) => void
}) {
  return (
    <div className="flex gap-1 border-b border-[#d2d2d7] px-5">
      {TABS.map(({ label, statut }) => {
        const count = statut ? (counts[statut] ?? 0) : Object.values(counts).reduce((a, b) => a + b, 0)
        const isActive = active === statut
        return (
          <button
            key={label}
            onClick={() => onChange(statut)}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-[13px] border-b-2 transition-colors ${
              isActive
                ? 'border-[#059669] text-[#059669] font-semibold'
                : 'border-transparent text-[#6e6e73] hover:text-[#1d1d1f]'
            }`}
          >
            {label}
            <span className={`text-[11px] px-1.5 py-0.5 rounded-full font-semibold ${
              isActive ? 'bg-[#059669] text-white' : 'bg-[#e5e5ea] text-[#6e6e73]'
            }`}>{count}</span>
          </button>
        )
      })}
    </div>
  )
}

function VenteRow({ v, onClick }: { v: VenteListItem; onClick: () => void }) {
  const tvaPct = v.total_ttc_cts > 0
    ? ((v.total_tva_cts / v.total_ttc_cts) * 100).toFixed(1)
    : '0'
  return (
    <tr
      onClick={onClick}
      className="hover:bg-[#f5f5f7] cursor-pointer border-b border-[#e5e5ea] last:border-0"
    >
      <td className="px-4 py-2.5 pl-5 font-mono text-[12px] text-[#059669] font-semibold">{v.numero_ticket}</td>
      <td className="px-4 py-2.5 text-[#6e6e73] text-[13px]">{fmtDate(v.created_at)}</td>
      <td className="px-4 py-2.5 text-[#1d1d1f] text-[13px]">{v.nb_articles} article{v.nb_articles > 1 ? 's' : ''}</td>
      <td className="px-4 py-2.5 font-semibold text-[#1d1d1f] text-[13px]">{fmtCts(v.total_ttc_cts)}</td>
      <td className="px-4 py-2.5 text-[#6e6e73] text-[13px]">{fmtCts(v.total_tva_cts)} <span className="text-[11px]">({tvaPct}%)</span></td>
      <td className="px-4 py-2.5 text-[13px]">
        <span className="badge badge-blue">{PAIEMENT_LABEL[v.mode_paiement] ?? v.mode_paiement}</span>
      </td>
      <td className="px-4 py-2.5 text-[#6e6e73] text-[13px]">{v.monnaie_rendue_cts > 0 ? fmtCts(v.monnaie_rendue_cts) : '—'}</td>
      <td className="px-4 py-2.5">
        <span className={STATUT_BADGE[v.statut]}>{STATUT_LABEL[v.statut]}</span>
      </td>
    </tr>
  )
}

function DetailModal({ venteId, onClose }: { venteId: number; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['epicerie-vente-detail', venteId],
    queryFn: () => api.get<VenteDetail>(`/epicerie/ventes/${venteId}`),
    staleTime: 60_000,
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-xl mx-4 overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#d2d2d7]">
          <div>
            <p className="font-semibold text-[#1d1d1f]">{data?.numero_ticket ?? '…'}</p>
            {data && <p className="text-[12px] text-[#6e6e73] mt-0.5">{fmtDate(data.created_at)}</p>}
          </div>
          <button onClick={onClose} className="text-[#6e6e73] hover:text-[#1d1d1f] text-xl leading-none">✕</button>
        </div>

        {isLoading && (
          <div className="px-5 py-10 text-center text-[13px] text-[#a1a1a6]">Chargement…</div>
        )}

        {data && (
          <div className="px-5 py-4 space-y-4">
            {/* Lignes */}
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[#d2d2d7]">
                  {['Article', 'Qté', 'P.U.', 'Total'].map(h => (
                    <th key={h} className="text-left text-[11.5px] font-semibold text-[#6e6e73] pb-2 first:pl-0">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#f5f5f7]">
                {data.lignes.map((l, i) => (
                  <tr key={i}>
                    <td className="py-1.5 text-[#1d1d1f]">{l.produit_designation}</td>
                    <td className="py-1.5 text-[#6e6e73]">{l.quantite}</td>
                    <td className="py-1.5 text-[#6e6e73]">{fmtCts(l.prix_unitaire_cts)}</td>
                    <td className="py-1.5 font-medium">{fmtCts(l.total_ligne_cts)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Récap financier */}
            <div className="bg-[#f5f5f7] rounded-lg p-3 space-y-1 text-[13px]">
              <div className="flex justify-between text-[#6e6e73]">
                <span>Sous-total HT</span>
                <span>{fmtCts(data.total_ttc_cts - data.total_tva_cts)}</span>
              </div>
              <div className="flex justify-between text-[#6e6e73]">
                <span>TVA (8,5%)</span>
                <span>{fmtCts(data.total_tva_cts)}</span>
              </div>
              {data.remise_cts > 0 && (
                <div className="flex justify-between text-[#991b1b]">
                  <span>Remise{data.remise_motif ? ` — ${data.remise_motif}` : ''}</span>
                  <span>-{fmtCts(data.remise_cts)}</span>
                </div>
              )}
              <div className="flex justify-between font-semibold text-[#1d1d1f] pt-1 border-t border-[#d2d2d7]">
                <span>Total TTC</span>
                <span>{fmtCts(data.total_ttc_cts)}</span>
              </div>
            </div>

            {/* Paiement */}
            <div className="flex gap-2 flex-wrap">
              <span className="badge badge-blue">{PAIEMENT_LABEL[data.mode_paiement] ?? data.mode_paiement}</span>
              {data.monnaie_rendue_cts > 0 && (
                <span className="badge badge-muted">Monnaie : {fmtCts(data.monnaie_rendue_cts)}</span>
              )}
              <span className={STATUT_BADGE[data.statut]}>{STATUT_LABEL[data.statut]}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Page principale ──────────────────────────────────────────────────────────

const PAGE_SIZE = 25

export default function HistoriqueVentesPage() {
  const [tabStatut, setTabStatut] = useState<StatutVente | null>(null)
  const [search, setSearch]       = useState('')
  const [page, setPage]           = useState(1)
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['epicerie-ventes', tabStatut, search, page],
    queryFn: () => {
      const params: Record<string, string | number> = {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }
      if (tabStatut) params.statut = tabStatut
      if (search)    params.search = search
      const qs = Object.entries(params).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&')
      return api.get<{ items: VenteListItem[]; total: number; counts: Record<string, number> }>(
        `/epicerie/ventes?${qs}`,
      )
    },
    staleTime: 30_000,
    placeholderData: prev => prev,
  })

  const items     = data?.items   ?? []
  const total     = data?.total   ?? 0
  const counts    = data?.counts  ?? {}
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function handleTabChange(statut: StatutVente | null) {
    setTabStatut(statut)
    setPage(1)
  }

  function handleSearch(v: string) {
    setSearch(v)
    setPage(1)
  }

  return (
    <div className="flex flex-col min-h-0">
      {/* Header */}
      <div className="px-7 pt-6 pb-0 border-b border-[#d2d2d7] bg-white">
        <div className="flex items-center justify-between pb-4">
          <div>
            <h1 className="text-[22px] font-bold text-[#1d1d1f] tracking-tight">Historique Ventes</h1>
            <p className="text-[13px] text-[#6e6e73] mt-0.5">Toutes les transactions de l'épicerie</p>
          </div>
          <div className="relative max-w-xs">
            <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#a1a1a6]" width="14" height="14"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
            </svg>
            <input
              value={search}
              onChange={e => handleSearch(e.target.value)}
              placeholder="N° ticket, article…"
              className="w-full border border-[#d2d2d7] rounded-md pl-8 pr-3 py-1.5 text-[13px] placeholder-[#a1a1a6] focus:outline-none focus:ring-1 focus:ring-[#059669]"
            />
          </div>
        </div>
        <TabBar active={tabStatut} counts={counts} onChange={handleTabChange} />
      </div>

      {/* Table */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="px-7 py-10 text-center text-[13px] text-[#a1a1a6]">Chargement…</div>
        ) : items.length === 0 ? (
          <p className="px-7 py-10 text-center text-[13px] text-[#a1a1a6]">Aucune vente trouvée</p>
        ) : (
          <table className="w-full text-[13px] border-collapse">
            <thead className="sticky top-0 bg-white z-10">
              <tr className="border-b border-[#d2d2d7]">
                {['N° Vente', 'Date / Heure', 'Articles', 'Montant TTC', 'TVA 8,5%', 'Paiement', 'Monnaie', 'Statut'].map(h => (
                  <th key={h} className="text-left text-[11.5px] font-semibold text-[#6e6e73] px-4 py-2.5 first:pl-5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(v => (
                <VenteRow key={v.id} v={v} onClick={() => setSelectedId(v.id)} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-7 py-3 border-t border-[#d2d2d7] flex items-center justify-between bg-white text-[13px]">
          <span className="text-[#6e6e73]">{total} vente{total > 1 ? 's' : ''}</span>
          <div className="flex items-center gap-2">
            <button
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
              className="px-3 py-1 rounded border border-[#d2d2d7] text-[#6e6e73] hover:bg-[#f5f5f7] disabled:opacity-40"
            >Préc.</button>
            <span className="text-[#6e6e73]">{page} / {totalPages}</span>
            <button
              disabled={page === totalPages}
              onClick={() => setPage(p => p + 1)}
              className="px-3 py-1 rounded border border-[#d2d2d7] text-[#6e6e73] hover:bg-[#f5f5f7] disabled:opacity-40"
            >Suiv.</button>
          </div>
        </div>
      )}

      {/* Modal détail */}
      {selectedId !== null && (
        <DetailModal venteId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
