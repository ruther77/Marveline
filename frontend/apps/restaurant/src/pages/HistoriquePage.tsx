// Route : /_massacorp/restaurant/historique
// Historique des commandes restaurant — table paginée + modal détail + export CSV

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, Search, X, ClipboardList } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import type {
  CommandeHistoriqueRead,
  CommandeHistoriqueDetail,
  CommandeStatut,
  LigneHistoriqueRead,
} from '@/types/restaurant-v2'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtEur(cts: number): string {
  return (cts / 100).toFixed(2) + ' €'
}

function fmtHeure(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

function statutLabel(s: CommandeStatut): { label: string; cls: string } {
  switch (s) {
    case 'OUVERTE':  return { label: 'Ouverte',  cls: 'bg-blue-50 text-blue-600' }
    case 'SERVIE':   return { label: 'Servie',   cls: 'bg-emerald-50 text-emerald-700' }
    case 'PAYEE':    return { label: 'Payée',    cls: 'bg-emerald-50 text-emerald-700' }
    case 'ANNULEE':  return { label: 'Annulée',  cls: 'bg-red-50 text-red-600' }
  }
}

type Filtre = 'all' | 'OUVERTE' | 'SERVIE' | 'PAYEE' | 'ANNULEE'
type PeriodeFiltreId = 'today' | 'week' | 'month' | 'all'

const PERIODES: { id: PeriodeFiltreId; label: string }[] = [
  { id: 'today', label: "Aujourd'hui" },
  { id: 'week',  label: 'Cette semaine' },
  { id: 'month', label: 'Ce mois' },
  { id: 'all',   label: 'Tout' },
]

function periodeToParams(p: PeriodeFiltreId): { date_debut?: string; date_fin?: string } {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const fmt = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  if (p === 'today') return { date_debut: fmt(now), date_fin: fmt(now) }
  if (p === 'week') {
    const mon = new Date(now); mon.setDate(now.getDate() - now.getDay() + 1)
    return { date_debut: fmt(mon), date_fin: fmt(now) }
  }
  if (p === 'month') {
    const first = new Date(now.getFullYear(), now.getMonth(), 1)
    return { date_debut: fmt(first), date_fin: fmt(now) }
  }
  return {}
}

// ─── LigneRow (dans modal) ────────────────────────────────────────────────────

function LigneRow({ l }: { l: LigneHistoriqueRead }) {
  return (
    <div className="flex items-start gap-3 py-2.5">
      <div className="flex-1 min-w-0">
        <div className="text-[13px] font-medium text-stone-900">{l.description}</div>
        {l.side && <div className="text-[11.5px] text-stone-500 mt-0.5">{l.side}</div>}
      </div>
      <div className="text-[13px] text-stone-600 w-6 text-center">{l.quantite}</div>
      <div className="text-[13px] text-stone-600 w-24 text-right">{fmtEur(l.prix_unitaire_cts)}</div>
      <div className="text-[13px] font-medium text-stone-900 w-24 text-right">{fmtEur(l.montant_cts)}</div>
    </div>
  )
}

// ─── ModalDetail ─────────────────────────────────────────────────────────────

function ModalDetail({
  commandeId, onClose,
}: { commandeId: number; onClose: () => void }) {
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  const { data, isLoading, isError } = useQuery({
    queryKey: ['restaurant-commande-detail', commandeId],
    queryFn: () => restaurantApi.getCommandeDetail(commandeId),
    staleTime: 60_000,
  })

  const plats = data?.lignes.filter(l => l.type === 'plat') ?? []
  const boissons = data?.lignes.filter(l => l.type === 'boisson') ?? []

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex justify-end"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div ref={trapRef} role="dialog" aria-modal="true" className="w-full max-w-[520px] bg-white h-full flex flex-col shadow-2xl border-l border-stone-200">
        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-stone-200">
          <ClipboardList className="h-4 w-4 text-stone-400" />
          <h2 className="text-[15px] font-semibold text-stone-900 flex-1">
            Commande #{commandeId}
            {data && (
              <span className={`ml-2 text-[11.5px] font-semibold px-2 py-0.5 rounded-full ${statutLabel(data.statut).cls}`}>
                {statutLabel(data.statut).label}
              </span>
            )}
          </h2>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-stone-100 text-stone-400 transition-colors" aria-label="Fermer">
            <X className="h-4 w-4" />
          </button>
        </div>

        {isLoading && (
          <div className="flex-1 px-5 py-4 space-y-4 animate-pulse">
            <div className="space-y-2">
              <div className="bg-stone-200 rounded h-3 w-24" />
              <div className="grid grid-cols-2 gap-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="bg-stone-100 rounded-lg h-10" />
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <div className="bg-stone-200 rounded h-3 w-16" />
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="bg-stone-100 rounded-lg h-8" />
              ))}
            </div>
            <div className="bg-stone-100 rounded-lg h-12 mt-4" />
          </div>
        )}

        {isError && (
          <div className="flex-1 flex flex-col items-center justify-center gap-2">
            <p className="text-[13px] text-red-600">Erreur de chargement</p>
            <button onClick={onClose} className="text-[12px] text-amber-600 hover:underline">Fermer</button>
          </div>
        )}

        {data && (
          <div className="flex-1 overflow-y-auto">
            {/* Métadonnées */}
            <div className="px-5 py-4 border-b border-stone-100">
              <div className="text-[11.5px] font-semibold text-stone-400 uppercase tracking-wider mb-3">Informations</div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                {([
                  ['Table', `Table ${data.table_numero}`],
                  ['Couverts', String(data.nb_couverts)],
                  ['Ouverture', fmtHeure(data.date_ouverture)],
                  ['Fermeture', fmtHeure(data.date_fermeture)],
                  ['Paiement', data.mode_paiement ?? '—'],
                ] as [string, string][]).map(([k, v]) => (
                  <div key={k} className="flex flex-col">
                    <span className="text-[11px] text-stone-400">{k}</span>
                    <span className="text-[13px] text-stone-900 font-medium">{v}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Plats */}
            {plats.length > 0 && (
              <div className="px-5 py-4 border-b border-stone-100">
                <div className="text-[11.5px] font-semibold text-stone-400 uppercase tracking-wider mb-2">Plats</div>
                <div className="divide-y divide-stone-100">
                  {plats.map(l => <LigneRow key={l.ligne_id} l={l} />)}
                </div>
              </div>
            )}

            {/* Boissons */}
            {boissons.length > 0 && (
              <div className="px-5 py-4 border-b border-stone-100">
                <div className="text-[11.5px] font-semibold text-stone-400 uppercase tracking-wider mb-2">Boissons</div>
                <div className="divide-y divide-stone-100">
                  {boissons.map(l => <LigneRow key={l.ligne_id} l={l} />)}
                </div>
              </div>
            )}

            {/* Récap financier */}
            <div className="px-5 py-4">
              <div className="text-[11.5px] font-semibold text-stone-400 uppercase tracking-wider mb-3">
                Récapitulatif financier · TVA DOM 8.5%
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-[13px]">
                  <span className="text-stone-500">Sous-total HT</span>
                  <span className="text-stone-900">{fmtEur(data.sous_total_cts)}</span>
                </div>
                <div className="flex justify-between text-[13px]">
                  <span className="text-stone-500">TVA 8.5% (DOM)</span>
                  <span className="text-amber-600">{fmtEur(data.tva_cts)}</span>
                </div>
                {data.pourboire_cts > 0 && (
                  <div className="flex justify-between text-[13px]">
                    <span className="text-stone-500">Pourboire</span>
                    <span className="text-stone-900">{fmtEur(data.pourboire_cts)}</span>
                  </div>
                )}
                <div className="flex justify-between text-[14px] font-bold pt-2 border-t border-stone-200">
                  <span className="text-stone-900">Total TTC</span>
                  <span className="text-stone-900">{fmtEur(data.total_ttc_cts)}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="px-5 py-3 border-t border-stone-200 flex justify-end">
          <button onClick={onClose} className="px-4 py-2 text-[13px] font-semibold text-stone-600 bg-white border border-stone-200 rounded-lg hover:bg-stone-50 transition-colors">
            Fermer
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── HistoriquePage ───────────────────────────────────────────────────────────

export default function HistoriquePage() {
  const [filtreStatut, setFiltreStatut] = useState<Filtre>('all')
  const [filtrePeriode, setFiltrePeriode] = useState<PeriodeFiltreId>('today')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [page, setPage] = useState(1)

  const PER_PAGE = 50

  const queryParams = {
    statut: filtreStatut === 'all' ? undefined : filtreStatut,
    ...periodeToParams(filtrePeriode),
    page,
    per_page: PER_PAGE,
  }

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['restaurant-historique', queryParams],
    queryFn: () => restaurantApi.listHistorique(queryParams),
    staleTime: 30_000,
  })

  const items = data?.items ?? []
  const total = data?.total ?? 0
  const caPeriode = data?.ca_periode_cts ?? 0

  const filtered = useMemo(() => {
    if (!search.trim()) return items
    const q = search.toLowerCase()
    return items.filter(c =>
      String(c.id).includes(q) ||
      c.table_numero.toLowerCase().includes(q)
    )
  }, [items, search])

  const ONGLETS: { id: Filtre; label: string }[] = [
    { id: 'all',      label: 'Toutes' },
    { id: 'OUVERTE',  label: 'Ouvertes' },
    { id: 'SERVIE',   label: 'Servies' },
    { id: 'PAYEE',    label: 'Payées' },
    { id: 'ANNULEE',  label: 'Annulées' },
  ]

  function exportCsv() {
    const header = 'N° commande;Table;Ouverture;Fermeture;Couverts;Montant TTC (EUR);Statut\n'
    const rows = filtered.map(c =>
      [
        `#${c.id}`,
        `Table ${c.table_numero}`,
        fmtHeure(c.date_ouverture),
        fmtHeure(c.date_fermeture),
        c.nb_couverts,
        (c.total_cts / 100).toFixed(2),
        c.statut,
      ].join(';')
    ).join('\n')
    const blob = new Blob(['\uFEFF' + header + rows], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `commandes-restaurant-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col min-h-0 bg-stone-50">
      {/* Header */}
      <div className="px-5 pt-5 pb-4 border-b border-stone-200 bg-white shrink-0">
        <h1 className="text-[17px] font-bold text-stone-900 tracking-tight">Historique commandes</h1>
        <p className="text-[13px] text-stone-500 mt-0.5">Restaurant</p>
      </div>

      {/* Onglets statut */}
      <div className="flex border-b border-stone-200 bg-white px-5 shrink-0">
        {ONGLETS.map(o => (
          <button
            key={o.id}
            onClick={() => { setFiltreStatut(o.id); setPage(1) }}
            className={`px-4 py-3 text-[13px] font-medium border-b-2 transition-colors -mb-px ${
              filtreStatut === o.id
                ? 'border-amber-500 text-amber-600'
                : 'border-transparent text-stone-500 hover:text-stone-900'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-3 px-5 py-3 bg-white border-b border-stone-100 shrink-0 flex-wrap">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-stone-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="N° commande, table…"
            className="pl-8 pr-3 py-1.5 text-[13px] bg-stone-50 border border-stone-200 rounded-lg focus:outline-none focus:border-amber-400 focus:bg-white transition-colors w-48"
          />
          {search.trim() && (
            <span className="text-[10px] text-stone-400 absolute -bottom-4 left-0">
              {filtered.length}/{items.length} sur cette page
            </span>
          )}
        </div>
        {/* Période */}
        <div className="flex gap-1">
          {PERIODES.map(p => (
            <button
              key={p.id}
              onClick={() => { setFiltrePeriode(p.id); setPage(1) }}
              className={`px-3 py-1.5 text-[12px] font-medium rounded-lg transition-colors ${
                filtrePeriode === p.id
                  ? 'bg-amber-50 text-amber-600'
                  : 'text-stone-500 hover:bg-stone-100'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-4">
          <span className="text-[11.5px] text-stone-400">
            {total} commande{total > 1 ? 's' : ''}{caPeriode > 0 && ` · ${fmtEur(caPeriode)} TTC`}
          </span>
          <button
            onClick={exportCsv}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium text-stone-600 bg-white border border-stone-200 rounded-lg hover:bg-stone-50 transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="animate-pulse px-4 py-4 space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-3">
                <div className="bg-stone-200 rounded h-4 w-12" />
                <div className="bg-stone-200 rounded h-4 w-10" />
                <div className="bg-stone-200 rounded h-4 w-20" />
                <div className="bg-stone-200 rounded h-4 w-20" />
                <div className="bg-stone-200 rounded h-4 w-10" />
                <div className="bg-stone-200 rounded h-4 w-16" />
                <div className="bg-stone-200 rounded h-4 w-14" />
                <div className="bg-stone-200 rounded h-4 w-16" />
              </div>
            ))}
          </div>
        ) : isError ? (
          <div className="text-center py-12">
            <p className="text-[13px] text-red-600 mb-2">Erreur de chargement</p>
            <button onClick={() => refetch()} className="text-[12px] text-amber-600 hover:underline">Réessayer</button>
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-center text-[12px] text-stone-400 py-12">Aucune commande</p>
        ) : (
          <div className="bg-white mx-3 my-3 rounded-xl border border-stone-200 shadow-sm overflow-hidden">
            <table className="w-full text-[13px]">
              <thead className="bg-stone-50 border-b border-stone-200">
                <tr>
                  {['N°', 'Table', 'Ouverture', 'Fermeture', 'Couverts', 'Montant TTC', 'Statut'].map(h => (
                    <th key={h} className="text-left text-[11px] font-semibold text-stone-500 uppercase tracking-wide px-4 py-2.5 first:pl-5">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {filtered.map(c => {
                  const st = statutLabel(c.statut)
                  return (
                    <tr
                      key={c.id}
                      onClick={() => setSelectedId(c.id)}
                      className="hover:bg-stone-50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 pl-5 py-2.5 font-mono text-[12px] text-stone-500">#{c.id}</td>
                      <td className="px-4 py-2.5 font-medium text-stone-900">Table {c.table_numero}</td>
                      <td className="px-4 py-2.5 text-stone-600 font-mono text-[12px]">{fmtHeure(c.date_ouverture)}</td>
                      <td className="px-4 py-2.5 text-stone-600 font-mono text-[12px]">{fmtHeure(c.date_fermeture)}</td>
                      <td className="px-4 py-2.5 text-center text-stone-600">{c.nb_couverts}</td>
                      <td className="px-4 py-2.5 text-right font-semibold text-stone-900">
                        {fmtEur(c.total_cts)}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`text-[11.5px] font-semibold px-2.5 py-0.5 rounded-full ${st.cls}`}>
                          {st.label}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {total > PER_PAGE && (
          <div className="flex justify-center gap-2 py-4 border-t border-stone-100">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 text-[12px] border border-stone-200 rounded-lg text-stone-600 disabled:opacity-40 hover:bg-stone-50 transition-colors"
            >
              Précédent
            </button>
            <span className="px-3 py-1.5 text-[12px] text-stone-500">
              Page {page} / {Math.ceil(total / PER_PAGE)}
            </span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page * PER_PAGE >= total}
              className="px-3 py-1.5 text-[12px] border border-stone-200 rounded-lg text-stone-600 disabled:opacity-40 hover:bg-stone-50 transition-colors"
            >
              Suivant
            </button>
          </div>
        )}
      </div>

      {selectedId !== null && (
        <ModalDetail commandeId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  )
}
