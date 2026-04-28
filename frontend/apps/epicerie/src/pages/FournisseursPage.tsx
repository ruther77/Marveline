// FC_EPICERIE_FOURNISSEURS.md §5 — FournisseursPage
// Onglets : Fournisseurs (accordéons lazy) | Synthèse dettes (calcul frontend)

import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { epicerieApi } from '@/api/epicerie'
import { normalizeError } from '@shared/errors/normalizer'
import { useToast } from '@shared/components/ui/Toast'
import { useMassaCorpAuthStore } from '@shared/stores/massacorpAuthStore'
import type {
  FournisseurRead,
  FournisseurStats,
  FinanceInvoiceRead,
  StatutFacture,
  StatutCommande,
  SupplyOrderRead,
  EpicerieProduitRead,
  LigneCommandeCreate,
  CaHistoriqueResponse,
  StockMargesResponse,
  AlertesPrixResponse,
  QualiteResponse,
} from '@/types/epicerie-v2'

// ── Tri urgence ───────────────────────────────────────────────────────────────
const URGENCE_ORDER: Record<FournisseurRead['badge_statut'], number> = {
  en_retard: 0,
  en_attente: 1,
  a_jour: 2,
}

// ── Commandes : labels et couleurs ────────────────────────────────────────────
const STATUT_CMD_LABEL: Record<StatutCommande, string> = {
  en_attente: 'En attente',
  confirmee: 'Confirmée',
  expediee: 'Expédiée',
  livree: 'Livrée',
  annulee: 'Annulée',
}
const STATUT_CMD_CLS: Record<StatutCommande, string> = {
  en_attente: 'bg-[rgba(146,64,14,.1)] text-[#92400e]',
  confirmee:  'bg-[rgba(37,99,235,.1)] text-[#1d4ed8]',
  expediee:   'bg-[rgba(8,145,178,.1)] text-[#0e7490]',
  livree:     'bg-[rgba(29,125,74,.1)] text-[#1d7d4a]',
  annulee:    'bg-[rgba(153,27,27,.1)] text-[#991b1b]',
}

// ── Palette couleurs cyclique (dot accordéon) ─────────────────────────────────
const SUPPLIER_COLORS = [
  '#2563eb', '#059669', '#d97706', '#7c3aed',
  '#db2777', '#dc2626', '#0891b2', '#65a30d',
]
function supplierColor(index: number): string {
  return SUPPLIER_COLORS[index % SUPPLIER_COLORS.length]
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatEur(centimes: number): string {
  return (centimes / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.split('T')[0].split('-').map(Number)
  const months = ['jan', 'fév', 'mar', 'avr', 'mai', 'jun', 'jul', 'aoû', 'sep', 'oct', 'nov', 'déc']
  return `${d} ${months[m - 1]} ${y}`
}

// ── Badge statut dette ────────────────────────────────────────────────────────
function BadgeStatutDette({ statut }: { statut: FournisseurRead['badge_statut'] }) {
  if (statut === 'a_jour')
    return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[rgba(29,125,74,.08)] text-[#1d7d4a]">À jour</span>
  if (statut === 'en_retard')
    return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[rgba(153,27,27,.08)] text-[#991b1b]">En retard</span>
  return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[rgba(146,64,14,.08)] text-[#92400e]">En attente</span>
}

// ── Badge statut facture ──────────────────────────────────────────────────────
function BadgeFacture({ statut }: { statut: StatutFacture }) {
  if (statut === 'PAYEE')
    return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[rgba(29,125,74,.08)] text-[#1d7d4a]">Payée</span>
  if (statut === 'EN_RETARD')
    return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[rgba(153,27,27,.08)] text-[#991b1b]">En retard</span>
  return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[rgba(146,64,14,.08)] text-[#92400e]">En attente</span>
}

// ── Skeletons ─────────────────────────────────────────────────────────────────
function SkeletonFournisseurList() {
  return (
    <div className="flex flex-col gap-2">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="border border-[#d2d2d7] rounded-md px-4 py-3.5 flex items-center gap-3 animate-pulse">
          <div className="w-2.5 h-2.5 rounded-full bg-[#e8e8ed] shrink-0" />
          <div className="flex-1 h-4 bg-[#e8e8ed] rounded max-w-[200px]" />
          <div className="flex items-center gap-3.5">
            <div className="h-8 w-14 bg-[#e8e8ed] rounded" />
            <div className="h-8 w-16 bg-[#e8e8ed] rounded" />
            <div className="h-6 w-16 bg-[#e8e8ed] rounded-full" />
          </div>
        </div>
      ))}
    </div>
  )
}

function SkeletonAccordeonStats() {
  return (
    <div className="p-4 flex flex-col gap-4 animate-pulse">
      <div className="grid grid-cols-3 gap-2.5 max-sm:grid-cols-2">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-[#f5f5f7] border border-[#d2d2d7] rounded-md p-3">
            <div className="h-3 bg-[#e8e8ed] rounded mb-2 w-3/4" />
            <div className="h-5 bg-[#e8e8ed] rounded w-1/2" />
          </div>
        ))}
      </div>
      <div className="space-y-2">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="flex items-center gap-2.5">
            <div className="h-3 bg-[#e8e8ed] rounded w-[120px] shrink-0" />
            <div className="flex-1 h-1.5 bg-[#e8e8ed] rounded-full" />
            <div className="h-3 bg-[#e8e8ed] rounded w-8" />
          </div>
        ))}
      </div>
    </div>
  )
}

// ── KPI band ─────────────────────────────────────────────────────────────────
function KpiBand({
  fournisseurs,
  filtreStatut,
  onFiltreChange,
}: {
  fournisseurs: FournisseurRead[]
  filtreStatut: FournisseurRead['badge_statut'] | null
  onFiltreChange: (s: FournisseurRead['badge_statut'] | null) => void
}) {
  const nbRetard  = fournisseurs.filter((f) => f.badge_statut === 'en_retard').length
  const nbAttente = fournisseurs.filter((f) => f.badge_statut === 'en_attente').length
  const totalDettes = fournisseurs.reduce((acc, f) => acc + f.dette_cts, 0)
  const totalCA     = fournisseurs.reduce((acc, f) => acc + f.ca_mensuel_cts, 0)
  const nbUrgents   = nbRetard + nbAttente

  const toggle = (s: FournisseurRead['badge_statut']) =>
    onFiltreChange(filtreStatut === s ? null : s)

  return (
    <div className="mb-4 flex flex-col gap-2">
      {/* Alerte urgence */}
      {nbUrgents > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-[rgba(153,27,27,.06)] border border-[rgba(153,27,27,.18)]">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#991b1b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <span className="text-[12px] font-semibold text-[#991b1b]">
            {nbUrgents} fournisseur{nbUrgents > 1 ? 's' : ''} {nbUrgents > 1 ? 'nécessitent' : 'nécessite'} une action
          </span>
        </div>
      )}

      {/* Métriques cliquables */}
      <div className="flex flex-wrap gap-2">
        {nbRetard > 0 && (
          <button
            onClick={() => toggle('en_retard')}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] font-semibold border transition-colors ${
              filtreStatut === 'en_retard'
                ? 'bg-[#991b1b] border-[#991b1b] text-white'
                : 'bg-[rgba(153,27,27,.08)] border-[rgba(153,27,27,.25)] text-[#991b1b] hover:bg-[rgba(153,27,27,.14)]'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-current shrink-0" />
            {nbRetard} en retard
          </button>
        )}
        {nbAttente > 0 && (
          <button
            onClick={() => toggle('en_attente')}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] font-semibold border transition-colors ${
              filtreStatut === 'en_attente'
                ? 'bg-[#92400e] border-[#92400e] text-white'
                : 'bg-[rgba(146,64,14,.08)] border-[rgba(146,64,14,.25)] text-[#92400e] hover:bg-[rgba(146,64,14,.14)]'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-current shrink-0" />
            {nbAttente} en attente
          </button>
        )}
        {totalDettes > 0 && (
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] font-semibold bg-[#f5f5f7] border border-[#d2d2d7] text-[#424245]">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            {formatEur(totalDettes)} dus
          </div>
        )}
        {totalCA > 0 && (
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] font-semibold bg-[rgba(5,150,105,.06)] border border-[rgba(5,150,105,.2)] text-[#1d7d4a]">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
            {formatEur(totalCA)} CA mois
          </div>
        )}
      </div>
    </div>
  )
}

// ── Distribution catégories ───────────────────────────────────────────────────
function DistributionCategories({
  distribution,
  color,
}: {
  distribution: FournisseurStats['distribution_categories']
  color: string
}) {
  return (
    <div>
      <div className="text-[11px] font-semibold text-[#6e6e73] mb-1.5">Répartition</div>
      <div className="flex flex-wrap gap-1.5">
        {distribution.map((d) => (
          <div
            key={d.categorie_nom}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border"
            style={{
              background: `${color}18`,
              borderColor: `${color}35`,
              color: '#424245',
            }}
          >
            <span className="font-bold" style={{ color }}>{d.pct}%</span>
            <span className="truncate max-w-[110px]">{d.categorie_nom}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Tableau factures avec filtres ─────────────────────────────────────────────
type FiltreFacture = 'TOUTES' | StatutFacture

function TableauFactures({
  invoices,
  onNouvelleCommande,
  isManager,
}: {
  invoices: FinanceInvoiceRead[]
  onNouvelleCommande: () => void
  isManager: boolean
}) {
  const [filtre, setFiltre] = useState<FiltreFacture>('TOUTES')

  const filtrees = filtre === 'TOUTES'
    ? invoices
    : invoices.filter((inv) => inv.statut === filtre)

  const totalFiltrees = filtrees.reduce((acc, inv) => acc + (inv.montant_cts ?? 0), 0)

  return (
    <div>
      <div className="flex items-center justify-between mb-2.5 gap-2.5 flex-wrap">
        <div className="flex gap-1">
          {(['TOUTES', 'EN_ATTENTE', 'PAYEE', 'EN_RETARD'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFiltre(f)}
              className={`px-2.5 py-1 rounded-full border text-[11.5px] font-medium cursor-pointer transition-colors ${
                filtre === f
                  ? 'bg-[#059669] border-[#059669] text-white'
                  : 'border-[#d2d2d7] text-[#6e6e73] hover:bg-[#f5f5f7]'
              }`}
            >
              {f === 'TOUTES' ? 'Toutes' : f === 'EN_ATTENTE' ? 'En attente' : f === 'PAYEE' ? 'Payées' : 'En retard'}
            </button>
          ))}
        </div>
        {isManager && (
          <button
            onClick={onNouvelleCommande}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border-[1.5px] border-[#059669] text-[#059669] text-[12.5px] font-semibold bg-transparent hover:bg-[rgba(5,150,105,.08)] transition-colors whitespace-nowrap"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            Nouvelle commande
          </button>
        )}
      </div>
      <div className="border border-[#d2d2d7] rounded-md overflow-hidden">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-[#f5f5f7]">
              <th className="p-[9px_12px] text-left text-[10.5px] font-bold uppercase tracking-[.05em] text-[#a1a1a6] border-b border-[#d2d2d7]">N° Facture</th>
              <th className="p-[9px_12px] text-left text-[10.5px] font-bold uppercase tracking-[.05em] text-[#a1a1a6] border-b border-[#d2d2d7]">Date</th>
              <th className="p-[9px_12px] text-left text-[10.5px] font-bold uppercase tracking-[.05em] text-[#a1a1a6] border-b border-[#d2d2d7]">Échéance</th>
              <th className="p-[9px_12px] text-left text-[10.5px] font-bold uppercase tracking-[.05em] text-[#a1a1a6] border-b border-[#d2d2d7]">Montant</th>
              <th className="p-[9px_12px] text-left text-[10.5px] font-bold uppercase tracking-[.05em] text-[#a1a1a6] border-b border-[#d2d2d7]">Statut</th>
            </tr>
          </thead>
          <tbody>
            {filtrees.length === 0 ? (
              <tr>
                <td colSpan={5} className="p-4 text-center text-[#a1a1a6] text-[13px]">
                  Aucune facture pour ce filtre.
                </td>
              </tr>
            ) : (
              filtrees.map((inv) => (
                <tr key={inv.id} className="hover:bg-[#f5f5f7] border-b border-[#d2d2d7] last:border-b-0">
                  <td className="p-[10px_12px] text-[12.5px] font-semibold text-[#1d1d1f] font-mono">{inv.numero}</td>
                  <td className="p-[10px_12px] text-[12.5px] text-[#424245]">{formatDate(inv.date_facture)}</td>
                  <td className="p-[10px_12px] text-[12.5px] text-[#424245]">{formatDate(inv.date_echeance)}</td>
                  <td className="p-[10px_12px] text-[12.5px] text-[#424245] font-semibold">{formatEur(inv.montant_cts)}</td>
                  <td className="p-[10px_12px]"><BadgeFacture statut={inv.statut} /></td>
                </tr>
              ))
            )}
          </tbody>
          {filtrees.length > 0 && (
            <tfoot>
              <tr className="bg-[#f5f5f7] border-t-2 border-[#d2d2d7]">
                <td colSpan={3} className="p-[9px_12px] text-[11px] font-bold uppercase tracking-[.05em] text-[#6e6e73]">
                  Total ({filtrees.length})
                </td>
                <td className="p-[9px_12px] text-[13px] font-bold text-[#1d1d1f]">{formatEur(totalFiltrees)}</td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  )
}

// ── Sparkline CA 6 mois ───────────────────────────────────────────────────────
function SparklineCA({ data }: { data: CaHistoriqueResponse | undefined }) {
  if (!data || data.items.length === 0) return null
  const items = data.items
  const vals = items.map((i) => i.montant_cts)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const W = 96
  const H = 28
  const pad = 3
  const normalize = (v: number) =>
    max === min ? H / 2 : H - pad - ((v - min) / (max - min)) * (H - 2 * pad)

  const points = items.map((item, idx) => {
    const x = pad + (idx / Math.max(items.length - 1, 1)) * (W - 2 * pad)
    const y = normalize(item.montant_cts)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  const variation = data.variation_pct
  const lastX = parseFloat(points[points.length - 1].split(',')[0])
  const lastY = parseFloat(points[points.length - 1].split(',')[1])

  return (
    <div className="flex items-center gap-3">
      <svg width={W} height={H} className="shrink-0">
        <polyline
          points={points.join(' ')}
          fill="none"
          stroke="#059669"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx={lastX} cy={lastY} r="2.5" fill="#059669" />
      </svg>
      {variation !== null && (
        <span className={`text-[11.5px] font-bold ${variation >= 0 ? 'text-[#1d7d4a]' : 'text-[#991b1b]'}`}>
          {variation >= 0 ? '+' : ''}{variation}%
        </span>
      )}
      <span className="text-[10.5px] text-[#a1a1a6]">vs mois préc.</span>
    </div>
  )
}

// ── Carte marges comparées ────────────────────────────────────────────────────
function CarteMarges({ data }: { data: StockMargesResponse | undefined }) {
  if (!data || data.nb_articles === 0) return null
  const diff = data.marge_moy_pct - data.marge_catalogue_moy_pct
  const isAbove = diff >= 0
  return (
    <div className="bg-[#f5f5f7] border border-[#d2d2d7] rounded-md p-3 flex items-center justify-between gap-3">
      <div>
        <div className="text-[11px] text-[#6e6e73] mb-0.5">Marge réelle (ce fourn.)</div>
        <div className={`text-[17px] font-bold ${isAbove ? 'text-[#1d7d4a]' : 'text-[#991b1b]'}`}>
          {data.marge_moy_pct.toFixed(1)}%
        </div>
      </div>
      <div className="text-right">
        <div className="text-[11px] text-[#6e6e73] mb-0.5">Moy. catalogue</div>
        <div className="text-[14px] font-semibold text-[#424245]">{data.marge_catalogue_moy_pct.toFixed(1)}%</div>
      </div>
      <div className={`text-[11.5px] font-bold px-2 py-1 rounded-md ${
        isAbove
          ? 'bg-[rgba(29,125,74,.1)] text-[#1d7d4a]'
          : 'bg-[rgba(153,27,27,.08)] text-[#991b1b]'
      }`}>
        {isAbove ? '+' : ''}{diff.toFixed(1)} pts
      </div>
    </div>
  )
}

// ── Alertes hausse prix ETL ───────────────────────────────────────────────────
function AlertesPrixSection({ data }: { data: AlertesPrixResponse | undefined }) {
  if (!data || data.alertes.length === 0) return null
  return (
    <div>
      <div className="text-[11px] font-bold uppercase tracking-[.07em] text-[#a1a1a6] mb-2 flex items-center gap-1.5">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#92400e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        <span className="text-[#92400e]">{data.alertes.length} hausse{data.alertes.length > 1 ? 's' : ''} de prix détectée{data.alertes.length > 1 ? 's' : ''}</span>
      </div>
      <div className="border border-[rgba(146,64,14,.2)] rounded-md overflow-hidden">
        {data.alertes.slice(0, 5).map((a, i) => (
          <div key={i} className="flex items-center justify-between gap-2 px-3 py-2 border-b border-[rgba(146,64,14,.1)] last:border-b-0 bg-[rgba(146,64,14,.04)]">
            <div className="flex-1 min-w-0">
              <div className="text-[12px] font-semibold text-[#1d1d1f] truncate">{a.designation}</div>
              {a.ean && <div className="text-[10.5px] text-[#a1a1a6] font-mono">{a.ean}</div>}
            </div>
            <div className="text-right shrink-0">
              <div className="text-[11px] text-[#6e6e73]">
                {formatEur(a.prix_precedent_cts)} → <span className="font-semibold text-[#1d1d1f]">{formatEur(a.prix_actuel_cts)}</span>
              </div>
              <div className="text-[12px] font-bold text-[#92400e]">+{a.variation_pct.toFixed(1)}%</div>
            </div>
          </div>
        ))}
        {data.alertes.length > 5 && (
          <div className="px-3 py-1.5 text-[11px] text-[#6e6e73] text-center bg-[rgba(146,64,14,.04)]">
            +{data.alertes.length - 5} autres hausses
          </div>
        )}
      </div>
      {data.date_import_precedente && data.date_import_actuelle && (
        <div className="text-[10.5px] text-[#a1a1a6] mt-1.5">
          Comparaison facture ETL {formatDate(data.date_import_precedente)} → {formatDate(data.date_import_actuelle)}
        </div>
      )}
    </div>
  )
}

// ── Signaux qualité ───────────────────────────────────────────────────────────
function SignauxQualite({ data }: { data: QualiteResponse | undefined }) {
  if (!data) return null

  function pillQualite(
    label: string,
    pct: number | null,
    seuil_ok: number,
    seuil_warn: number,
    inverse = false,
  ) {
    if (pct === null) return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] font-medium bg-[#f5f5f7] border border-[#d2d2d7] text-[#a1a1a6]">
        <span className="w-1.5 h-1.5 rounded-full bg-[#d2d2d7]" />
        {label}: —
      </div>
    )
    const isOk   = inverse ? pct <= seuil_ok   : pct >= seuil_ok
    const isWarn = inverse ? pct <= seuil_warn  : pct >= seuil_warn
    const cls = isOk
      ? 'bg-[rgba(29,125,74,.08)] border-[rgba(29,125,74,.2)] text-[#1d7d4a]'
      : isWarn
      ? 'bg-[rgba(146,64,14,.08)] border-[rgba(146,64,14,.2)] text-[#92400e]'
      : 'bg-[rgba(153,27,27,.08)] border-[rgba(153,27,27,.2)] text-[#991b1b]'
    const dot = isOk ? '#1d7d4a' : isWarn ? '#92400e' : '#991b1b'
    return (
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] font-medium border ${cls}`}>
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dot }} />
        {label}: <span className="font-bold">{pct.toFixed(0)}%</span>
      </div>
    )
  }

  return (
    <div>
      <div className="text-[11px] font-bold uppercase tracking-[.07em] text-[#a1a1a6] mb-2">Signaux qualité</div>
      <div className="flex flex-wrap gap-2">
        {pillQualite('Livraisons à temps', data.taux_livraison_temps_pct, 90, 70)}
        {pillQualite('Factures en retard', data.taux_factures_retard_pct, 5, 20, true)}
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[12px] font-medium bg-[#f5f5f7] border border-[#d2d2d7] text-[#424245]">
          <span className="text-[#a1a1a6]">Commandes évaluées :</span>
          <span className="font-bold">{data.nb_commandes_evaluees}</span>
        </div>
      </div>
    </div>
  )
}

// ── AccordeonFournisseur (lazy loading) ───────────────────────────────────────
function AccordeonFournisseur({
  fournisseur,
  color,
  isManager,
  onNouvelleCommande,
}: {
  fournisseur: FournisseurRead
  color: string
  isManager: boolean
  onNouvelleCommande: (vendorId: string) => void
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [hasOpened, setHasOpened] = useState(false)

  const { data: stats } = useQuery({
    queryKey: ['epicerie', 'fournisseur-stats', fournisseur.vendor_id],
    queryFn: () => epicerieApi.getFournisseurStats(fournisseur.vendor_id),
    enabled: hasOpened,
    staleTime: 5 * 60 * 1000,
  })

  const { data: facturesData } = useQuery({
    queryKey: ['epicerie', 'fournisseur-factures', fournisseur.vendor_id],
    queryFn: () => epicerieApi.listFacturesFournisseur(fournisseur.vendor_id),
    enabled: hasOpened,
    staleTime: 2 * 60 * 1000,
  })

  const { data: commandesData } = useQuery({
    queryKey: ['epicerie', 'fournisseur-commandes', fournisseur.vendor_id],
    queryFn: () => epicerieApi.listCommandesFournisseur(fournisseur.vendor_id),
    enabled: hasOpened,
    staleTime: 2 * 60 * 1000,
  })
  const dernieresCommandes: SupplyOrderRead[] = commandesData?.items?.slice(0, 3) ?? []

  const { data: caData } = useQuery({
    queryKey: ['epicerie', 'fournisseur-ca', fournisseur.vendor_id],
    queryFn: () => epicerieApi.getCaHistorique(fournisseur.vendor_id),
    enabled: hasOpened,
    staleTime: 5 * 60 * 1000,
  })
  const { data: margesData } = useQuery({
    queryKey: ['epicerie', 'fournisseur-marges', fournisseur.vendor_id],
    queryFn: () => epicerieApi.getStockMarges(fournisseur.vendor_id),
    enabled: hasOpened,
    staleTime: 5 * 60 * 1000,
  })
  const { data: alertesPrixData } = useQuery({
    queryKey: ['epicerie', 'fournisseur-alertes-prix', fournisseur.vendor_id],
    queryFn: () => epicerieApi.getAlertesPrix(fournisseur.vendor_id),
    enabled: hasOpened,
    staleTime: 5 * 60 * 1000,
  })
  const { data: qualiteData } = useQuery({
    queryKey: ['epicerie', 'fournisseur-qualite', fournisseur.vendor_id],
    queryFn: () => epicerieApi.getQualite(fournisseur.vendor_id),
    enabled: hasOpened,
    staleTime: 5 * 60 * 1000,
  })

  const handleToggle = useCallback(() => {
    const next = !isOpen
    setIsOpen(next)
    if (next && !hasOpened) setHasOpened(true)
  }, [isOpen, hasOpened])

  const detteLabel = fournisseur.dette_cts > 0
    ? formatEur(fournisseur.dette_cts)
    : 'À jour'

  return (
    <div className={`border border-[#d2d2d7] rounded-md overflow-hidden`}>
      {/* ── Header ── */}
      <div
        onClick={handleToggle}
        className={`flex items-center gap-3 px-4 py-3.5 cursor-pointer select-none transition-colors ${
          isOpen ? 'bg-[rgba(5,150,105,.08)] border-b border-[#d2d2d7]' : 'bg-white hover:bg-[#f5f5f7]'
        }`}
      >
        <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: color }} />

        <div className="flex-1 min-w-0">
          <span className="text-[14px] font-bold text-[#1d1d1f]">{fournisseur.nom}</span>
          <span className="text-[11px] text-[#a1a1a6] font-normal ml-1.5">{fournisseur.code}</span>
        </div>

        <div className="flex items-center gap-3.5 shrink-0">
          <div className="text-right max-sm:hidden">
            <div className="text-[10px] text-[#a1a1a6] font-medium">Articles</div>
            <div className="text-[12.5px] font-bold text-[#1d1d1f]">{fournisseur.nb_articles}</div>
          </div>
          {fournisseur.ca_mensuel_cts > 0 && (
            <div className="text-right max-sm:hidden">
              <div className="text-[10px] text-[#a1a1a6] font-medium">CA mois</div>
              <div className="text-[12.5px] font-bold text-[#1d7d4a]">{formatEur(fournisseur.ca_mensuel_cts)}</div>
            </div>
          )}
          <div className="text-right">
            <div className="text-[10px] text-[#a1a1a6] font-medium">Dette</div>
            <div className={`text-[12.5px] font-bold ${fournisseur.dette_cts > 0 ? 'text-[#92400e]' : 'text-[#1d1d1f]'}`}>
              {detteLabel}
            </div>
          </div>
          <BadgeStatutDette statut={fournisseur.badge_statut} />
        </div>

        <div
          className="shrink-0 text-[#a1a1a6] transition-transform duration-200"
          style={{ transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
      </div>

      {/* ── Corps (lazy) ── */}
      {isOpen && (
        <div className="p-4 bg-white flex flex-col gap-4">
          {!stats ? (
            <SkeletonAccordeonStats />
          ) : (
            <>
              {/* Stat-cards */}
              <div className="grid grid-cols-3 gap-2.5 max-sm:grid-cols-2">
                {[
                  { label: 'Livraisons ce mois', value: `${stats.livraisons_mois} livraisons` },
                  { label: 'Achats ce mois', value: formatEur(stats.achats_mois_cts), ok: true },
                  { label: 'Délai crédit moyen', value: `${stats.delai_paiement_moyen_jours} jours` },
                ].map((s) => (
                  <div key={s.label} className="bg-[#f5f5f7] border border-[#d2d2d7] rounded-md p-3">
                    <div className="text-[11px] text-[#6e6e73] mb-1">{s.label}</div>
                    <div className={`text-[16px] font-bold tracking-tight ${s.ok ? 'text-[#1d7d4a]' : 'text-[#1d1d1f]'}`}>
                      {s.value}
                    </div>
                  </div>
                ))}
              </div>

              {/* Distribution catégories */}
              {stats.distribution_categories.length > 0 && (
                <DistributionCategories distribution={stats.distribution_categories} color={color} />
              )}

              {/* CA sparkline 6 mois + marges comparées */}
              {(caData || margesData) && (
                <div className="flex flex-col gap-2.5 sm:flex-row sm:items-stretch">
                  {caData && caData.items.length > 0 && (
                    <div className="flex-1 bg-[#f5f5f7] border border-[#d2d2d7] rounded-md p-3 flex flex-col gap-1.5 min-w-0">
                      <div className="text-[11px] text-[#6e6e73]">CA mensuel — 6 mois</div>
                      <SparklineCA data={caData} />
                    </div>
                  )}
                  <CarteMarges data={margesData} />
                </div>
              )}
            </>
          )}

          {/* Commandes récentes */}
          {dernieresCommandes.length > 0 && (
            <div>
              <div className="text-[11px] font-bold uppercase tracking-[.07em] text-[#a1a1a6] mb-2">
                Commandes récentes
              </div>
              <div className="flex flex-wrap gap-2">
                {dernieresCommandes.map((cmd) => {
                  const dateRef = cmd.date_livraison_reelle ?? cmd.date_commande
                  return (
                    <div
                      key={cmd.id}
                      className={`inline-flex items-center gap-2 px-2.5 py-1.5 rounded-md border text-[12px] font-medium ${STATUT_CMD_CLS[cmd.statut]}`}
                      style={{ borderColor: 'currentColor', opacity: 0.9 }}
                    >
                      <span className="font-semibold">{STATUT_CMD_LABEL[cmd.statut]}</span>
                      <span className="opacity-60">·</span>
                      <span>{formatDate(dateRef)}</span>
                      {cmd.total_cts > 0 && (
                        <>
                          <span className="opacity-60">·</span>
                          <span className="font-semibold">{formatEur(cmd.total_cts)}</span>
                        </>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Tableau factures — masqué si vide */}
          {facturesData && (
            facturesData.items.length > 0 ? (
              <TableauFactures
                invoices={facturesData.items}
                onNouvelleCommande={() => onNouvelleCommande(fournisseur.vendor_id)}
                isManager={isManager}
              />
            ) : isManager ? (
              <div className="flex justify-end">
                <button
                  onClick={() => onNouvelleCommande(fournisseur.vendor_id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border-[1.5px] border-[#059669] text-[#059669] text-[12.5px] font-semibold bg-transparent hover:bg-[rgba(5,150,105,.08)] transition-colors"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  Nouvelle commande
                </button>
              </div>
            ) : null
          )}

          {/* Alertes hausse prix (ETL) */}
          <AlertesPrixSection data={alertesPrixData} />

          {/* Signaux qualité */}
          <SignauxQualite data={qualiteData} />
        </div>
      )}
    </div>
  )
}

// ── Modal nouvelle commande ───────────────────────────────────────────────────
function ModalNouvelleCommande({
  vendorId,
  fournisseurs,
  onClose,
}: {
  vendorId: string | null
  fournisseurs: FournisseurRead[]
  onClose: () => void
}) {
  const { success, error: toastError } = useToast()
  const queryClient = useQueryClient()

  const [selectedVendor, setSelectedVendor] = useState(vendorId ?? '')
  const [lignes, setLignes] = useState<LigneCommandeCreate[]>([
    { produit_id: 0, quantite: 1, prix_unitaire_cts: 0 },
  ])
  const [notes, setNotes] = useState('')

  // Chargement des produits pour le sélecteur
  const { data: produitsData, isLoading: produitsLoading } = useQuery({
    queryKey: ['epicerie', 'produits-all'],
    queryFn: () => epicerieApi.listProduits({ limit: 500 }),
    staleTime: 10 * 60 * 1000,
  })
  const produits: EpicerieProduitRead[] = produitsData ?? []

  const { mutate: creer, isPending } = useMutation({
    mutationFn: () =>
      epicerieApi.creerCommande({
        vendor_id: selectedVendor,
        lignes: lignes.filter((l) => l.produit_id > 0 && l.quantite > 0),
        notes: notes.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['epicerie', 'fournisseurs'] })
      queryClient.invalidateQueries({ queryKey: ['epicerie', 'fournisseur-commandes', selectedVendor] })
      success('Commande créée', `Commande envoyée au fournisseur`)
      onClose()
    },
    onError: (err: unknown) => {
      toastError('Erreur', normalizeError(err).message || 'Impossible de créer la commande')
    },
  })

  const ajouterLigne = () =>
    setLignes((prev) => [...prev, { produit_id: 0, quantite: 1, prix_unitaire_cts: 0 }])

  const supprimerLigne = (i: number) =>
    setLignes((prev) => prev.filter((_, idx) => idx !== i))

  const updateLigne = (i: number, patch: Partial<LigneCommandeCreate>) =>
    setLignes((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)))

  const lignesValides = lignes.filter((l) => l.produit_id > 0 && l.quantite > 0)
  const peutValider = selectedVendor !== '' && lignesValides.length > 0

  const totalCts = lignesValides.reduce((acc, l) => acc + l.quantite * l.prix_unitaire_cts, 0)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#d2d2d7]">
          <h2 className="text-[17px] font-bold text-[#1d1d1f] tracking-tight">Nouvelle commande</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-md border border-[#d2d2d7] bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#d2d2d7] flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {/* Corps scrollable */}
        <div className="overflow-y-auto flex-1 px-5 py-4 flex flex-col gap-4">
          {/* Fournisseur */}
          <div>
            <label className="block text-[12px] font-semibold text-[#424245] mb-1.5">Fournisseur</label>
            <select
              value={selectedVendor}
              onChange={(e) => setSelectedVendor(e.target.value)}
              className="w-full border border-[#d2d2d7] rounded-md px-3 py-2 text-[13px] text-[#1d1d1f] bg-white focus:outline-none focus:ring-2 focus:ring-[#059669]/40"
            >
              <option value="">Sélectionner un fournisseur…</option>
              {fournisseurs.map((f) => (
                <option key={f.vendor_id} value={f.vendor_id}>{f.nom}</option>
              ))}
            </select>
          </div>

          {/* Lignes commande */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-[12px] font-semibold text-[#424245]">Lignes</label>
              <button
                onClick={ajouterLigne}
                className="text-[11.5px] font-semibold text-[#059669] hover:underline"
              >
                + Ajouter une ligne
              </button>
            </div>
            <div className="flex flex-col gap-2">
              {lignes.map((ligne, i) => (
                <div key={i} className="flex gap-2 items-center">
                  {produitsLoading ? (
                    <div className="flex-1 h-[33px] bg-[#e8e8ed] rounded-md animate-pulse" />
                  ) : (
                    <select
                      value={ligne.produit_id || ''}
                      onChange={(e) => {
                        const produitId = Number(e.target.value)
                        const produit = produits.find((p) => p.id === produitId)
                        updateLigne(i, {
                          produit_id: produitId,
                          prix_unitaire_cts: produit?.prix_unitaire_cts ?? 0,
                        })
                      }}
                      className="flex-1 border border-[#d2d2d7] rounded-md px-2 py-1.5 text-[12px] text-[#1d1d1f] bg-white focus:outline-none focus:ring-2 focus:ring-[#059669]/40"
                    >
                      <option value="">Produit…</option>
                      {produits.map((p) => (
                        <option key={p.id} value={p.id}>{p.designation_clean}</option>
                      ))}
                    </select>
                  )}
                  <input
                    type="number"
                    min="1"
                    value={ligne.quantite}
                    onChange={(e) => updateLigne(i, { quantite: Math.max(1, Number(e.target.value)) })}
                    placeholder="Qté"
                    className="w-16 border border-[#d2d2d7] rounded-md px-2 py-1.5 text-[12px] text-center text-[#1d1d1f] focus:outline-none focus:ring-2 focus:ring-[#059669]/40"
                  />
                  <div className="relative w-24">
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={Math.round(ligne.prix_unitaire_cts / 100)}
                      onChange={(e) => updateLigne(i, { prix_unitaire_cts: Math.round(Number(e.target.value) * 100) })}
                      placeholder="0"
                      className="w-full border border-[#d2d2d7] rounded-md pl-2 pr-8 py-1.5 text-[12px] text-[#1d1d1f] focus:outline-none focus:ring-2 focus:ring-[#059669]/40"
                    />
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-[#a1a1a6] pointer-events-none">€</span>
                  </div>
                  {lignes.length > 1 && (
                    <button
                      onClick={() => supprimerLigne(i)}
                      className="text-[#991b1b] hover:text-[#dc2626] shrink-0"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="block text-[12px] font-semibold text-[#424245] mb-1.5">Notes (facultatif)</label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Ex : Commande hebdomadaire"
              className="w-full border border-[#d2d2d7] rounded-md px-3 py-2 text-[13px] text-[#1d1d1f] focus:outline-none focus:ring-2 focus:ring-[#059669]/40"
            />
          </div>

          {/* Total */}
          {totalCts > 0 && (
            <div className="bg-[#f5f5f7] rounded-md px-3 py-2 flex items-center justify-between">
              <span className="text-[12px] text-[#6e6e73]">Total estimé</span>
              <span className="text-[15px] font-bold text-[#1d1d1f]">{formatEur(totalCts)}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-[#d2d2d7] flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-md border border-[#d2d2d7] bg-[#f5f5f7] text-[#424245] text-[13px] font-medium hover:bg-[#d2d2d7] transition-colors"
          >
            Annuler
          </button>
          <button
            onClick={() => creer()}
            disabled={!peutValider || isPending}
            className="px-4 py-2 rounded-md bg-[#059669] text-white text-[13px] font-semibold hover:bg-[#047857] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isPending ? 'Création…' : 'Créer la commande'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── OngletSyntheseDettes ──────────────────────────────────────────────────────
function OngletSyntheseDettes({ fournisseurs }: { fournisseurs: FournisseurRead[] }) {
  const totalDette = fournisseurs.reduce((acc, f) => acc + f.dette_cts, 0)

  return (
    <div className="flex flex-col gap-6">
      {/* Tableau récap */}
      <div>
        <div className="text-[11px] font-bold uppercase tracking-[.07em] text-[#a1a1a6] mb-3">
          Tableau de synthèse — Dettes fournisseurs
        </div>
        <div className="border border-[#d2d2d7] rounded-md overflow-hidden">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-[#f5f5f7]">
                {['Fournisseur', 'CA ce mois', 'Total dû', 'Statut'].map((h) => (
                  <th key={h} className="p-[10px_14px] text-left text-[11px] font-bold uppercase tracking-[.05em] text-[#a1a1a6] border-b border-[#d2d2d7]">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fournisseurs.map((f, i) => (
                <tr key={f.vendor_id} className="hover:bg-[#f5f5f7] border-b border-[#d2d2d7] last:border-b-0">
                  <td className="p-[11px_14px]">
                    <div className="flex items-center gap-2.5">
                      <div className="w-2 h-2 rounded-full shrink-0" style={{ background: supplierColor(i) }} />
                      <span className="text-[13px] font-semibold text-[#1d1d1f]">{f.nom}</span>
                    </div>
                  </td>
                  <td className="p-[11px_14px]">
                    <span className="text-[13px] text-[#424245]">
                      {f.ca_mensuel_cts > 0 ? formatEur(f.ca_mensuel_cts) : '—'}
                    </span>
                  </td>
                  <td className="p-[11px_14px]">
                    <span className={`text-[13px] font-bold ${f.dette_cts > 0 ? 'text-[#1d1d1f]' : 'text-[#a1a1a6]'}`}>
                      {f.dette_cts > 0 ? formatEur(f.dette_cts) : '—'}
                    </span>
                  </td>
                  <td className="p-[11px_14px]"><BadgeStatutDette statut={f.badge_statut} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Distribution graphique */}
      {totalDette > 0 && (
        <div>
          <div className="text-[11px] font-bold uppercase tracking-[.07em] text-[#a1a1a6] mb-3">
            Répartition par fournisseur
          </div>
          <div className="border border-[#d2d2d7] rounded-md p-4 flex flex-col gap-2">
            {fournisseurs
              .filter((f) => f.dette_cts > 0)
              .map((f, i) => {
                const pct = Math.round((f.dette_cts / totalDette) * 100)
                return (
                  <div key={f.vendor_id} className="flex items-center gap-2.5">
                    <div className="text-[12px] text-[#424245] w-[100px] shrink-0 truncate">{f.nom}</div>
                    <div className="flex-1 h-1.5 bg-[#d2d2d7] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${pct}%`, background: supplierColor(i) }}
                      />
                    </div>
                    <div className="text-[11px] font-semibold text-[#6e6e73] w-8 text-right shrink-0">{pct}%</div>
                    <div className="text-[12px] font-semibold text-[#424245] w-[110px] text-right shrink-0">
                      {formatEur(f.dette_cts)}
                    </div>
                  </div>
                )
              })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── FournisseursPage ──────────────────────────────────────────────────────────
export default function FournisseursPage() {
  const { error: toastError } = useToast()
  const [activeTab, setActiveTab] = useState<'fournisseurs' | 'dettes'>('fournisseurs')
  const [search, setSearch] = useState('')
  const [filtreStatut, setFiltreStatut] = useState<FournisseurRead['badge_statut'] | null>(null)
  const [modalVendorId, setModalVendorId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['epicerie', 'fournisseurs'],
    queryFn: () => epicerieApi.listFournisseurs(),
    staleTime: 2 * 60 * 1000,
    throwOnError: (err) => {
      toastError('Erreur', normalizeError(err).message || 'Impossible de charger les fournisseurs')
      return false
    },
  })

  const fournisseurs: FournisseurRead[] = data?.items ?? []
  const filtres = fournisseurs
    .filter((f) => {
      if (filtreStatut && f.badge_statut !== filtreStatut) return false
      if (!search.trim()) return true
      const s = search.toLowerCase()
      return f.nom.toLowerCase().includes(s) || (f.code ?? '').toLowerCase().includes(s)
    })
    .sort((a, b) => {
      const urg = URGENCE_ORDER[a.badge_statut] - URGENCE_ORDER[b.badge_statut]
      return urg !== 0 ? urg : b.dette_cts - a.dette_cts
    })

  const { user } = useMassaCorpAuthStore()
  const isManager = user?.role === 'manager'

  return (
    <div className="flex flex-col min-h-0">
      {/* ── Header ── */}
      <div className="px-7 pt-7 pb-0 border-b border-[#d2d2d7] bg-white max-sm:px-4 max-sm:pt-5">
        <h1 className="text-[22px] font-bold text-[#1d1d1f] tracking-tight mb-1">Fournisseurs</h1>
        <p className="text-[13px] text-[#6e6e73] mb-4">Gestion des achats et suivi des dettes fournisseurs</p>

        {/* Onglets de page */}
        <div className="flex">
          {([
            { key: 'fournisseurs', label: 'Fournisseurs' },
            { key: 'dettes', label: 'Synthèse dettes' },
          ] as const).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2.5 text-[13.5px] font-medium border-b-2 transition-colors -mb-px ${
                activeTab === tab.key
                  ? 'text-[#059669] border-[#059669] font-semibold'
                  : 'text-[#6e6e73] border-transparent hover:text-[#1d1d1f]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Contenu ── */}
      <div className="flex-1 overflow-y-auto px-7 py-6 max-sm:px-4 max-sm:py-4">
        {activeTab === 'fournisseurs' && (
          <div>
            {/* KPI band */}
            {!isLoading && fournisseurs.length > 0 && (
              <KpiBand
                fournisseurs={fournisseurs}
                filtreStatut={filtreStatut}
                onFiltreChange={setFiltreStatut}
              />
            )}

            {/* Barre de recherche + action principale */}
            <div className="flex items-center gap-3 mb-4">
              <div className="relative flex-1 max-w-xs">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-[#a1a1a6]" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Rechercher un fournisseur…"
                  className="w-full border border-[#d2d2d7] rounded-md pl-8 pr-3 py-2 text-[13px] text-[#1d1d1f] placeholder-[#a1a1a6] focus:outline-none focus:ring-2 focus:ring-[#059669]/40"
                />
              </div>
              {isManager && (
                <button
                  onClick={() => setModalVendorId('')}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-[#059669] text-white text-[13px] font-semibold hover:bg-[#047857] transition-colors whitespace-nowrap"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  Nouvelle commande
                </button>
              )}
            </div>

            {/* Liste accordéons */}
            {isLoading ? (
              <SkeletonFournisseurList />
            ) : filtres.length === 0 ? (
              <div className="text-center text-[#a1a1a6] text-[13px] py-12">
                {search ? `Aucun fournisseur pour "${search}".` : 'Aucun fournisseur enregistré.'}
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {filtres.map((f, i) => (
                  <AccordeonFournisseur
                    key={f.vendor_id}
                    fournisseur={f}
                    color={supplierColor(i)}
                    isManager={isManager}
                    onNouvelleCommande={setModalVendorId}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'dettes' && (
          <OngletSyntheseDettes fournisseurs={fournisseurs} />
        )}
      </div>

      {/* ── Modal nouvelle commande ── */}
      {modalVendorId !== null && (
        <ModalNouvelleCommande
          vendorId={modalVendorId}
          fournisseurs={fournisseurs}
          onClose={() => setModalVendorId(null)}
        />
      )}
    </div>
  )
}
