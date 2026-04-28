// Route : /_massacorp/epicerie/reception
// Réception des commandes fournisseurs — saisie des quantités reçues + validation

import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Package } from 'lucide-react'
import { epicerieApi } from '@/api/epicerie'
import { normalizeError } from '@shared/errors/normalizer'
import { useToast } from '@shared/components/ui/Toast'
import type { SupplyOrderRead, FournisseurRead, LigneCommandeRead } from '@/types/epicerie-v2'

// ─── Helpers ─────────────────────────────────────────────────────────────────

const STATUTS_RECEPTIONNABLES = new Set(['confirmee', 'expediee'])

function xpf(cts: number): string {
  return Math.round(cts / 100).toLocaleString('fr-FR') + ' XPF'
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

const BADGE: Record<string, string> = {
  confirmee: 'bg-[#dbeafe] text-[#1d4ed8]',
  expediee:  'bg-[#fef3c7] text-[#92400e]',
}

// ─── FiltreFournisseurs ───────────────────────────────────────────────────────

function FiltreFournisseurs({ items, selected, onSelect }: {
  items: FournisseurRead[]; selected: string | null; onSelect: (id: string | null) => void
}) {
  const chipClass = (active: boolean) =>
    `px-2.5 py-1 rounded text-[12px] font-medium border transition-colors ${
      active ? 'bg-[#1d1d1f] text-white border-[#1d1d1f]' : 'bg-white text-[#1d1d1f] border-[#d2d2d7] hover:bg-[#f5f5f7]'
    }`
  return (
    <div className="flex flex-wrap gap-1.5 px-3 pt-3 pb-2">
      <button className={chipClass(selected === null)} onClick={() => onSelect(null)}>Tous</button>
      {items.map(f => (
        <button key={f.vendor_id} className={chipClass(selected === f.vendor_id)} onClick={() => onSelect(f.vendor_id)}>
          {f.code}
        </button>
      ))}
    </div>
  )
}

// ─── CarteCommande ────────────────────────────────────────────────────────────

function CarteCommande({ cmd, active, onClick }: {
  cmd: SupplyOrderRead; active: boolean; onClick: () => void
}) {
  return (
    <button onClick={onClick}
      className={`w-full text-left px-4 py-3 border-b border-[#e5e5ea] transition-colors ${active ? 'bg-[#f0fdf4]' : 'hover:bg-[#f5f5f7]'}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[13px] font-semibold text-[#1d1d1f] truncate">{cmd.vendor_nom}</span>
        <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${BADGE[cmd.statut] ?? ''}`}>{cmd.statut}</span>
      </div>
      <div className="text-[12px] text-[#6e6e73] mt-0.5">
        {cmd.lignes.length} article{cmd.lignes.length > 1 ? 's' : ''} · Livraison {fmtDate(cmd.date_livraison_prevue)}
      </div>
    </button>
  )
}

// ─── LigneReceptionRow ────────────────────────────────────────────────────────

function LigneReceptionRow({ ligne, recu, onChangeRecu }: {
  ligne: LigneCommandeRead; recu: number; onChangeRecu: (v: number) => void
}) {
  const ecart = recu - ligne.quantite
  const ecartClass = ecart === 0 ? 'text-[#6e6e73]' : ecart > 0 ? 'text-[#059669] font-semibold' : 'text-[#991b1b] font-semibold'
  return (
    <tr className="border-b border-[#e5e5ea]">
      <td className="px-4 py-2.5 text-[13px] font-medium text-[#1d1d1f]">{ligne.designation}</td>
      <td className="px-4 py-2.5 text-[13px] text-right text-[#6e6e73]">{ligne.quantite}</td>
      <td className="px-4 py-2.5 text-right">
        <input type="number" min={0} value={recu} onChange={e => onChangeRecu(Math.max(0, +e.target.value))}
          className="w-16 border border-[#d2d2d7] rounded text-[13px] text-right px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#059669]" />
      </td>
      <td className={`px-4 py-2.5 text-[13px] text-right ${ecartClass}`}>{ecart > 0 ? `+${ecart}` : ecart}</td>
      <td className="px-4 py-2.5 text-[13px] text-right text-[#6e6e73]">{xpf(ligne.prix_unitaire_cts)}</td>
      <td className="px-4 py-2.5 text-[13px] text-right text-[#6e6e73]">{xpf(recu * ligne.prix_unitaire_cts)}</td>
    </tr>
  )
}

// ─── PanelEmpty ───────────────────────────────────────────────────────────────

function PanelEmpty() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center p-8">
      <Package className="h-10 w-10 text-[#d2d2d7]" />
      <p className="text-[14px] font-medium text-[#6e6e73]">Sélectionner une commande</p>
      <p className="text-[12px] text-[#a1a1a6]">Cliquez sur une commande pour démarrer la réception</p>
    </div>
  )
}

// ─── PanelReception ───────────────────────────────────────────────────────────

function PanelReception({ commande, recus, onChangeRecu, onValider, error, isPending }: {
  commande: SupplyOrderRead
  recus: Record<number, number>
  onChangeRecu: (produitId: number, v: number) => void
  onValider: () => void
  error: string | null
  isPending: boolean
}) {
  const totalRecu = commande.lignes.reduce((s, l) => s + (recus[l.produit_id] ?? 0) * l.prix_unitaire_cts, 0)
  return (
    <div className="flex flex-col h-full">
      <div className="px-5 py-3 border-b border-[#d2d2d7]">
        <div className="text-[15px] font-bold text-[#1d1d1f]">{commande.vendor_nom}</div>
        <div className="text-[12px] text-[#6e6e73]">
          Commande #{commande.id} · {fmtDate(commande.date_commande)} · Livraison prévue {fmtDate(commande.date_livraison_prevue)}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d2d2d7]">
              {['Article', 'Commandé', 'Reçu', 'Écart', 'Prix HT', 'Total HT'].map(h => (
                <th key={h} className="text-right first:text-left text-[11.5px] font-semibold text-[#6e6e73] px-4 py-2.5">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {commande.lignes.map(l => (
              <LigneReceptionRow key={l.produit_id} ligne={l}
                recu={recus[l.produit_id] ?? 0}
                onChangeRecu={v => onChangeRecu(l.produit_id, v)} />
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-5 py-3 border-t border-[#d2d2d7] bg-[#f5f5f7] flex items-center justify-between gap-4">
        <div className="text-[13px] text-[#6e6e73]">Total reçu : <span className="font-bold text-[#1d1d1f]">{xpf(totalRecu)}</span></div>
        {error && <p className="text-[12px] text-[#991b1b]">{error}</p>}
        <button onClick={onValider} disabled={isPending}
          className="px-4 py-2 bg-[#059669] text-white text-[13px] font-semibold rounded-md hover:opacity-90 disabled:opacity-50">
          {isPending ? 'Validation…' : 'Valider la réception'}
        </button>
      </div>
    </div>
  )
}

// ─── ReceptionCommandesPage ───────────────────────────────────────────────────

export default function ReceptionCommandesPage() {
  const [filtreVendor, setFiltreVendor] = useState<string | null>(null)
  const [commandeActive, setCommandeActive] = useState<SupplyOrderRead | null>(null)
  const [recus, setRecus] = useState<Record<number, number>>({})
  const [error, setError] = useState<string | null>(null)
  const qc = useQueryClient()
  const { success: toastOk, error: toastErr } = useToast()

  const { data: fournisseursData } = useQuery({
    queryKey: ['epicerie-fournisseurs'],
    queryFn: () => epicerieApi.listFournisseurs(),
    staleTime: 60_000,
  })

  const { data: commandesData } = useQuery({
    queryKey: ['epicerie-commandes-fournisseur', filtreVendor ?? 'all'],
    queryFn: async () => {
      const vendors = filtreVendor
        ? [filtreVendor]
        : (fournisseursData?.items ?? []).map(f => f.vendor_id)
      const results = await Promise.all(vendors.map(v => epicerieApi.listCommandesFournisseur(v)))
      return results.flatMap(r => r.items).filter(c => STATUTS_RECEPTIONNABLES.has(c.statut))
    },
    enabled: !!fournisseursData,
    staleTime: 30_000,
  })

  const mutation = useMutation({
    mutationFn: async () => {
      if (!commandeActive) return
      const lignes = commandeActive.lignes.filter(l => (recus[l.produit_id] ?? 0) > 0)
      await Promise.all(lignes.map(l =>
        epicerieApi.ajusterStock({
          produit_id: l.produit_id,
          type_ajustement: 'ENTREE',
          quantite: recus[l.produit_id] ?? 0,
          raison: `Réception commande #${commandeActive.id} — ${commandeActive.vendor_nom}`,
        }),
      ))
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['epicerie-stock-stats'] })
      qc.invalidateQueries({ queryKey: ['epicerie-stock'] })
      qc.invalidateQueries({ queryKey: ['epicerie-mouvements'] })
      qc.invalidateQueries({ queryKey: ['epicerie-commandes-fournisseur'] })
      toastOk('Réception validée', `Commande #${commandeActive?.id} — stock mis à jour`)
      setCommandeActive(null)
      setRecus({})
      setError(null)
    },
    onError: (err) => {
      const msg = normalizeError(err).message || 'Erreur lors de la validation'
      setError(msg)
      toastErr('Erreur réception', msg)
    },
  })

  const fournisseurs = fournisseursData?.items ?? []
  const commandes = commandesData ?? []

  useEffect(() => {
    if (commandes.length > 0 && !commandeActive) {
      selectCommande(commandes[0])
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [commandes])

  function selectCommande(cmd: SupplyOrderRead) {
    setCommandeActive(cmd)
    setRecus(Object.fromEntries(cmd.lignes.map(l => [l.produit_id, l.quantite])))
    setError(null)
  }

  return (
    <div className="flex flex-col min-h-0">
      <div className="px-7 pt-6 pb-4 border-b border-[#d2d2d7] bg-white">
        <h1 className="text-[22px] font-bold text-[#1d1d1f] tracking-tight">Réception Commandes</h1>
        <p className="text-[13px] text-[#6e6e73] mt-0.5">Commandes confirmées et expédiées en attente de livraison</p>
      </div>

      <div className="flex-1 overflow-hidden flex">
        {/* Sidebar gauche — liste commandes */}
        <div className="w-72 shrink-0 border-r border-[#d2d2d7] flex flex-col overflow-hidden bg-white">
          <div className="border-b border-[#d2d2d7]">
            <p className="px-4 pt-3 pb-1 text-[11.5px] font-semibold text-[#6e6e73] uppercase tracking-wide">
              Commandes à réceptionner
            </p>
            <FiltreFournisseurs items={fournisseurs} selected={filtreVendor} onSelect={v => { setFiltreVendor(v); setCommandeActive(null) }} />
          </div>
          <div className="flex-1 overflow-y-auto">
            {commandes.length === 0 ? (
              <p className="text-center text-[12px] text-[#a1a1a6] py-8">Aucune commande en attente</p>
            ) : (
              commandes.map(cmd => (
                <CarteCommande key={cmd.id} cmd={cmd}
                  active={commandeActive?.id === cmd.id}
                  onClick={() => selectCommande(cmd)} />
              ))
            )}
          </div>
        </div>

        {/* Panel principal */}
        <div className="flex-1 overflow-hidden flex flex-col bg-[#f5f5f7]">
          {commandeActive
            ? <PanelReception
                commande={commandeActive}
                recus={recus}
                onChangeRecu={(id, v) => setRecus(prev => ({ ...prev, [id]: v }))}
                onValider={() => mutation.mutate()}
                error={error}
                isPending={mutation.isPending}
              />
            : <PanelEmpty />
          }
        </div>
      </div>
    </div>
  )
}
