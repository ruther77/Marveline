import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CreditCard, Check, Plus, Trash2 } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'
import type { CommandeDetailRead, CommandeHistoriqueDetail } from '../types/restaurant-v2'
import { printerApi } from '../api/printer'
import type { TicketLine } from '../api/printer'
import LoyaltyScanner from './LoyaltyScanner'

function fmtEur(cts: number): string {
  return (cts / 100).toFixed(2) + ' €'
}

type ModePaiement = 'especes' | 'CB' | 'virement' | 'mixte'
interface Fraction { label: string; montant_cts: number; mode: 'especes' | 'CB' | 'virement' }

const MODES: { key: ModePaiement; label: string }[] = [
  { key: 'especes', label: 'Espèces' },
  { key: 'CB', label: 'CB' },
  { key: 'virement', label: 'Virement' },
  { key: 'mixte', label: 'Mixte' },
]

interface PayerBody {
  mode_paiement: string
  montant_encaisse_cts: number
  pourboire_cts: number
  fractions: null | { label: string; montant_cts: number; mode: string }[]
}

interface OngletPaiementProps {
  commande: CommandeDetailRead
  onSuccess: () => void
  restaurantApi: {
    payerCommande: (commandeId: number, data: PayerBody) => Promise<CommandeHistoriqueDetail>
  }
}

export default function OngletPaiement({ commande, onSuccess, restaurantApi }: OngletPaiementProps) {
  const qc = useQueryClient()
  const [mode, setMode] = useState<ModePaiement>('CB')
  const [montantEspeces, setMontantEspeces] = useState('')
  const [pourboire, setPourboire] = useState('')
  const [fractions, setFractions] = useState<Fraction[]>([])
  const [fracLabel, setFracLabel] = useState('')
  const [fracMontant, setFracMontant] = useState('')
  const [fracMode, setFracMode] = useState<'especes' | 'CB' | 'virement'>('CB')
  const [error, setError] = useState('')
  const [showLoyalty, setShowLoyalty] = useState(false)
  const [printFailed, setPrintFailed] = useState(false)

  const totalCts = commande.total_cts
  const parsedEspeces = parseFloat(montantEspeces)
  const especesValid = montantEspeces !== '' && !isNaN(parsedEspeces) && parsedEspeces >= 0
  const monnaie = especesValid && mode === 'especes'
    ? Math.round(parsedEspeces * 100) - totalCts
    : null

  const fracTotal = fractions.reduce((s, f) => s + f.montant_cts, 0)
  const fracReste = totalCts - fracTotal

  const payerMutation = useMutation({
    mutationFn: () => restaurantApi.payerCommande(commande.id, {
      mode_paiement: mode,
      montant_encaisse_cts: mode === 'especes' && especesValid
        ? Math.round(parsedEspeces * 100)
        : totalCts,
      pourboire_cts: pourboire && !isNaN(parseFloat(pourboire)) ? Math.round(parseFloat(pourboire) * 100) : 0,
      fractions: mode === 'mixte' ? fractions : null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
      // Impression ticket best-effort (non bloquant)
      const lignes: TicketLine[] = commande.lignes.map(l => ({
        designation: l.variante_nom,
        quantite: l.quantite,
        prix_unitaire_cts: l.prix_unitaire_cts,
        total_cts: l.prix_unitaire_cts * l.quantite,
      }))
      printerApi.printTicket({
        ticket_type: 'recu_restaurant',
        lignes,
        sous_total_ht_cts: commande.sous_total_cts,
        total_ttc_cts: totalCts,
        numero_ticket: `CMD-${commande.id}`,
        ouvrir_tiroir: mode === 'especes',
      }).catch(() => { setPrintFailed(true) })
      setShowLoyalty(true)
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur lors du paiement'),
  })

  function addFraction() {
    if (!fracLabel.trim() || !fracMontant) return
    setFractions(prev => [...prev, {
      label: fracLabel.trim(),
      montant_cts: Math.round(parseFloat(fracMontant) * 100),
      mode: fracMode,
    }])
    setFracLabel('')
    setFracMontant('')
  }

  // Après paiement → afficher scanner fidélité
  if (showLoyalty) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-5 gap-4">
        {printFailed && (
          <div className="flex items-center gap-2 px-3 py-2 bg-amber-700/[.08] border border-amber-700/30 rounded-md w-full">
            <span className="text-[12px] text-amber-700 flex-1">Impression du ticket échouée</span>
            <button
              onClick={() => {
                setPrintFailed(false)
                const lignes: TicketLine[] = commande.lignes.map(l => ({
                  designation: l.variante_nom,
                  quantite: l.quantite,
                  prix_unitaire_cts: l.prix_unitaire_cts,
                  total_cts: l.prix_unitaire_cts * l.quantite,
                }))
                printerApi.printTicket({
                  ticket_type: 'recu_restaurant',
                  lignes,
                  sous_total_ht_cts: commande.sous_total_cts,
                  total_ttc_cts: totalCts,
                  numero_ticket: `CMD-${commande.id}`,
                  ouvrir_tiroir: false,
                }).catch(() => { setPrintFailed(true) })
              }}
              className="text-[13px] text-amber-600 font-semibold hover:underline shrink-0 min-h-[44px] px-2"
            >
              Réimprimer
            </button>
          </div>
        )}
        <LoyaltyScanner
          commandeId={commande.id}
          totalCts={totalCts}
          onClose={onSuccess}
        />
        <button onClick={onSuccess}
          className="text-[13px] text-stone-500 hover:text-stone-900 min-h-[44px] px-4">
          Passer sans fidélité
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 px-5 py-4 overflow-y-auto h-full">
      {/* Récap */}
      <div className="bg-stone-50 border border-stone-200 rounded-xl overflow-hidden">
        <div className="px-3 py-2 border-b border-stone-200">
          <span className="text-[11.5px] font-semibold text-stone-500">Récapitulatif</span>
        </div>
        <div className="px-3 py-2 flex flex-col gap-1">
          {commande.lignes.map(l => (
            <div key={l.ligne_id} className="flex items-center justify-between text-[11.5px]">
              <span className="text-stone-900 truncate flex-1">{l.variante_nom} ×{l.quantite}</span>
              <span className="text-stone-500 shrink-0 ml-2">{fmtEur(l.prix_unitaire_cts * l.quantite)}</span>
            </div>
          ))}
        </div>
        <div className="px-3 py-2 border-t border-stone-200 flex flex-col gap-1">
          <div className="flex justify-between text-[11.5px]">
            <span className="text-stone-500">Sous-total HT</span>
            <span className="text-stone-500">{fmtEur(commande.sous_total_cts)}</span>
          </div>
          <div className="flex justify-between text-[11.5px]">
            <span className="text-stone-500">TVA</span>
            <span className="text-stone-500">{fmtEur(commande.tva_cts)}</span>
          </div>
          <div className="flex justify-between text-[13px] font-bold border-t border-stone-200 pt-1 mt-0.5">
            <span className="text-stone-900">Total TTC</span>
            <span className="text-stone-900">{fmtEur(totalCts)}</span>
          </div>
        </div>
      </div>

      {/* Mode paiement */}
      <div>
        <label className="text-[11.5px] font-semibold text-stone-500 mb-1.5 block">Mode de paiement</label>
        <div className="grid grid-cols-4 gap-1.5">
          {MODES.map(m => (
            <button key={m.key} onClick={() => setMode(m.key)}
              className={`flex items-center justify-center gap-1 py-2 text-[11.5px] font-semibold rounded-xl border transition-colors min-h-[44px] ${
                mode === m.key
                  ? 'bg-stone-900 text-white border-stone-900'
                  : 'bg-stone-50 text-stone-500 border-stone-200 hover:bg-stone-100'
              }`}>
              {m.key === 'CB' && <CreditCard className="h-3 w-3" />}
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Espèces */}
      {mode === 'especes' && (
        <div>
          <label className="text-[11.5px] font-semibold text-stone-500 mb-1 block">Montant encaissé</label>
          <input type="number" min={0} step={1} value={montantEspeces} onChange={e => setMontantEspeces(e.target.value)}
            placeholder={String(Math.round(totalCts / 100))}
            className="w-full bg-white border border-stone-200 rounded-xl px-3 py-2.5 text-[13px] focus:outline-none focus:ring-2 focus:ring-amber-500" />
          {monnaie !== null && monnaie >= 0 && (
            <div className="text-[12px] text-green-700 mt-1 font-semibold">
              Monnaie à rendre : {fmtEur(monnaie)}
            </div>
          )}
        </div>
      )}

      {/* Mixte */}
      {mode === 'mixte' && (
        <div>
          <label className="text-[11.5px] font-semibold text-stone-500 mb-1.5 block">Fractions</label>
          {fractions.map((f, i) => (
            <div key={i} className="flex items-center justify-between text-[11.5px] px-3 py-1.5 bg-stone-50 border border-stone-200 rounded-lg mb-1">
              <span>{f.label} ({f.mode})</span>
              <div className="flex items-center gap-2">
                <span className="font-semibold">{fmtEur(f.montant_cts)}</span>
                <button onClick={() => setFractions(prev => prev.filter((_, j) => j !== i))}
                  className="text-stone-400 hover:text-red-500 p-0.5 min-h-[44px] min-w-[44px] flex items-center justify-center">
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
          {fracReste > 0 && (
            <div className="flex gap-1.5 mt-2">
              <input type="text" value={fracLabel} onChange={e => setFracLabel(e.target.value)}
                placeholder="Libellé" className="flex-1 bg-white border border-stone-200 rounded-lg px-2 py-1.5 text-[11.5px] focus:outline-none focus:ring-1 focus:ring-amber-500" />
              <input type="number" value={fracMontant} onChange={e => setFracMontant(e.target.value)}
                placeholder={String(Math.round(fracReste / 100))}
                className="w-20 bg-white border border-stone-200 rounded-lg px-2 py-1.5 text-[11.5px] focus:outline-none focus:ring-1 focus:ring-amber-500" />
              <select value={fracMode} onChange={e => setFracMode(e.target.value as typeof fracMode)}
                className="bg-white border border-stone-200 rounded-lg px-2 py-1.5 text-[11.5px] focus:outline-none">
                <option value="CB">CB</option>
                <option value="especes">Esp.</option>
                <option value="virement">Vir.</option>
              </select>
              <button onClick={addFraction} className="text-amber-600 hover:opacity-80 p-1.5 bg-stone-50 border border-stone-200 rounded-lg min-h-[44px] min-w-[44px] flex items-center justify-center">
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
          {fractions.length > 0 && (
            <div className="text-[11.5px] text-stone-500 mt-1.5">
              Reste : {fmtEur(Math.max(0, fracReste))}
            </div>
          )}
        </div>
      )}

      {/* Pourboire */}
      <div>
        <label className="text-[11.5px] font-semibold text-stone-500 mb-1 block">Pourboire (optionnel)</label>
        <input type="number" min={0} step={1} value={pourboire} onChange={e => setPourboire(e.target.value)}
          placeholder="0"
          className="w-full bg-white border border-stone-200 rounded-xl px-3 py-2.5 text-[13px] focus:outline-none focus:ring-2 focus:ring-amber-500" />
      </div>

      {error && <div className="text-[12px] text-red-600 bg-red-50 rounded-xl px-3 py-2">{error}</div>}

      <button
        onClick={() => { setError(''); payerMutation.mutate() }}
        disabled={
          payerMutation.isPending ||
          (mode === 'especes' && !especesValid) ||
          (mode === 'especes' && especesValid && Math.round(parsedEspeces * 100) < totalCts) ||
          (mode === 'mixte' && fracReste > 0)
        }
        className="w-full flex items-center justify-center gap-1.5 bg-green-700 text-white text-[13px] font-semibold rounded-xl py-2.5 hover:opacity-90 disabled:opacity-40 transition-colors min-h-[44px]">
        <Check className="h-4 w-4" />
        {payerMutation.isPending ? 'Validation…' : 'Valider le paiement'}
      </button>
    </div>
  )
}
