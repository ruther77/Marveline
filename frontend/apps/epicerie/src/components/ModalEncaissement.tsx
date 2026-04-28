import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { X, CreditCard, Banknote, Building2, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { epicerieApi } from '@/api/epicerie'
import { normalizeError } from '@shared/errors/normalizer'
import { cn } from '@shared/lib/utils'
import type { CartItem, EncaissementRequest, EncaissementResponse, ModePaiement } from '@/types/epicerie-v2'

function formatEur(centimes: number): string {
  return (centimes / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
}

const MODE_CONFIG: { key: ModePaiement; label: string; icon: React.ReactNode }[] = [
  { key: 'ESPECES',  label: 'Espèces', icon: <Banknote className="h-4 w-4" /> },
  { key: 'CB',       label: 'Carte',   icon: <CreditCard className="h-4 w-4" /> },
  { key: 'VIREMENT', label: 'Virement', icon: <Building2 className="h-4 w-4" /> },
]

function SelectModePaiement({ value, onChange }: { value: ModePaiement; onChange: (m: ModePaiement) => void }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {MODE_CONFIG.map(({ key, label, icon }) => (
        <button key={key} onClick={() => onChange(key)}
          className={cn('flex flex-col items-center gap-1 p-3 rounded-xl border text-xs font-medium transition-colors min-h-[44px]',
            value === key ? 'border-blue-500 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-500 hover:border-gray-300',
          )}>
          {icon}{label}
        </button>
      ))}
    </div>
  )
}

interface ModalEncaissementProps {
  items: CartItem[]
  ttcNet: number
  remiseCentimes: number
  remiseMotif: string
  onSuccess: (res: EncaissementResponse) => void
  onClose: () => void
}

export default function ModalEncaissement({ items, ttcNet, remiseCentimes, remiseMotif, onSuccess, onClose }: ModalEncaissementProps) {
  const [mode, setMode] = useState<ModePaiement>('ESPECES')
  const [montantEspeces, setMontantEspeces] = useState('')
  const [error, setError] = useState('')

  const espCentimes = mode === 'ESPECES' ? Math.round(parseFloat(montantEspeces) * 100 || 0) : 0
  const rendu = mode === 'ESPECES' ? Math.max(0, espCentimes - ttcNet) : 0
  const peutEncaisser = mode !== 'ESPECES' || espCentimes >= ttcNet

  const { mutate: encaisser, isPending } = useMutation({
    mutationFn: (req: EncaissementRequest) => epicerieApi.encaisser(req),
    onSuccess,
    onError: (err: unknown) => setError(normalizeError(err).message || "Erreur lors de l'encaissement"),
  })

  function submit() {
    setError('')
    encaisser({
      lignes: items.map(it => ({
        produit_id: it.produit.id,
        quantite: it.quantite,
        prix_unitaire_ttc: it.produit.prix_unitaire_cts,
      })),
      mode_paiement: mode,
      montant_especes: espCentimes,
      montant_cb: mode === 'CB' ? ttcNet : 0,
      montant_virement: mode === 'VIREMENT' ? ttcNet : 0,
      remise_centimes: remiseCentimes,
      remise_motif: remiseMotif || null,
      client_nom: null,
    })
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
        <div className="flex justify-between items-center p-5 border-b">
          <h2 className="font-semibold text-gray-800">Encaissement</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="h-5 w-5" /></button>
        </div>

        <div className="p-5 space-y-4">
          <div className="text-center">
            <p className="text-sm text-gray-400">Total à payer</p>
            <p className="text-3xl font-bold text-blue-700">{formatEur(ttcNet)}</p>
            {remiseCentimes > 0 && <p className="text-xs text-green-600">Remise de {formatEur(remiseCentimes)} appliquée</p>}
          </div>

          <SelectModePaiement value={mode} onChange={setMode} />

          {mode === 'ESPECES' && (
            <div className="space-y-2">
              <label className="text-xs text-gray-500 block">Montant remis (EUR)</label>
              <input type="number" min={ttcNet / 100} value={montantEspeces}
                onChange={e => setMontantEspeces(e.target.value)}
                placeholder={`Min. ${Math.round(ttcNet / 100)} EUR`}
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-300 focus:outline-none" />
              {rendu > 0 && (
                <div className="flex justify-between items-center bg-green-50 rounded-lg px-3 py-2">
                  <span className="text-xs text-green-600">Monnaie rendue</span>
                  <span className="font-bold text-green-700">{formatEur(rendu)}</span>
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-red-600 text-xs bg-red-50 rounded-lg p-2">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />{error}
            </div>
          )}
        </div>

        <div className="p-5 pt-0">
          <button onClick={submit} disabled={!peutEncaisser || isPending}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 disabled:text-gray-400 text-white font-semibold rounded-xl transition-colors min-h-[44px]">
            {isPending ? 'Traitement…' : "Confirmer l'encaissement"}
          </button>
        </div>
      </div>
    </div>
  )
}

export function SuccessModal({ ticket, onClose }: { ticket: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-xs p-6 text-center">
        <CheckCircle2 className="h-14 w-14 text-green-500 mx-auto mb-3" />
        <h3 className="font-bold text-gray-800 text-lg mb-1">Vente enregistrée</h3>
        <p className="text-sm text-gray-400 mb-4">Ticket n° {ticket}</p>
        <button onClick={onClose}
          className="w-full py-2.5 bg-gray-900 text-white font-medium rounded-xl hover:bg-gray-800 transition-colors min-h-[44px]">
          Nouvelle vente
        </button>
      </div>
    </div>
  )
}
