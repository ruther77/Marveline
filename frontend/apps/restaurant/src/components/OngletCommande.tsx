import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, Plus, Check, AlertTriangle } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'
import { statutPlatBadge } from './TableCard'
import type { CommandeDetailRead } from '../types/restaurant-v2'

function fmtEur(cts: number): string {
  return (cts / 100).toFixed(2) + ' €'
}

interface OngletCommandeProps {
  commande: CommandeDetailRead
  restaurantApi: {
    supprimerLigne: (commandeId: number, ligneId: number) => Promise<unknown>
    marquerPret: (commandeId: number) => Promise<unknown>
    marquerServi: (commandeId: number) => Promise<unknown>
  }
  onShowAjouter: () => void
}

export default function OngletCommande({ commande, restaurantApi, onShowAjouter }: OngletCommandeProps) {
  const qc = useQueryClient()
  const [error, setError] = useState('')

  const supprimerMutation = useMutation({
    mutationFn: (ligneId: number) => restaurantApi.supprimerLigne(commande.id, ligneId),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['restaurant-commande', commande.id] })
      qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur suppression ligne'),
  })

  const marquerServiMutation = useMutation({
    mutationFn: () => restaurantApi.marquerServi(commande.id),
    onSuccess: () => {
      setError('')
      qc.invalidateQueries({ queryKey: ['restaurant-commande', commande.id] })
      qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
    },
    onError: (err) => setError(normalizeError(err).message || 'Erreur marquage servi'),
  })

  const hasPrete = commande.lignes.some(l => l.statut_plat === 'PRETE')
  const peutAjouter = commande.statut === 'OUVERTE' || commande.statut === 'SERVIE'

  return (
    <div className="flex flex-col gap-3 px-5 py-4 overflow-y-auto h-full">
      {error && (
        <div className="flex items-center gap-2 px-3 py-2 bg-red-600/[.08] border border-red-600/20 rounded-md">
          <AlertTriangle className="h-3.5 w-3.5 text-red-600 shrink-0" />
          <span className="text-[12px] text-red-600 flex-1">{error}</span>
          <button onClick={() => setError('')} aria-label="Fermer l'erreur"><X className="h-3.5 w-3.5 text-red-600" /></button>
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        {commande.lignes.map(ligne => {
          const badge = statutPlatBadge(ligne.statut_plat)
          return (
            <div key={ligne.ligne_id} className="flex items-center gap-2 px-3 py-2.5 bg-stone-50 border border-stone-200 rounded-xl">
              <div className="flex-1 min-w-0">
                <div className="text-[12.5px] font-semibold text-stone-900 truncate">
                  {ligne.variante_nom}
                  {ligne.side_nom && <span className="text-stone-500 font-normal"> + {ligne.side_nom}</span>}
                </div>
                <div className="text-[11.5px] text-stone-500 flex items-center gap-2">
                  <span>×{ligne.quantite}</span>
                  <span>·</span>
                  <span>{fmtEur(ligne.prix_unitaire_cts * ligne.quantite)}</span>
                  {ligne.notes && <span className="text-stone-400 italic truncate">«{ligne.notes}»</span>}
                </div>
              </div>
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full shrink-0 ${badge.cls}`}>
                {badge.label}
              </span>
              {ligne.statut_plat === 'ENVOYEE' && (
                <button onClick={() => supprimerMutation.mutate(ligne.ligne_id)}
                  disabled={supprimerMutation.isPending}
                  className="text-stone-400 hover:text-red-500 disabled:opacity-40 shrink-0 p-1 min-h-[44px] min-w-[44px] flex items-center justify-center">
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          )
        })}

        {commande.lignes.length === 0 && (
          <div className="text-center py-4 text-stone-500 text-[12.5px]">Aucune ligne</div>
        )}
      </div>

      <div className="flex flex-col gap-2 mt-1">
        {peutAjouter && (
          <button onClick={onShowAjouter}
            className="w-full flex items-center justify-center gap-1.5 bg-stone-50 border border-stone-200 text-stone-900 text-[12.5px] font-semibold rounded-xl py-2.5 hover:border-amber-400 hover:text-amber-700 transition-colors min-h-[44px]">
            <Plus className="h-3.5 w-3.5" /> Ajouter un plat
          </button>
        )}

        {hasPrete && (
          <button onClick={() => marquerServiMutation.mutate()} disabled={marquerServiMutation.isPending}
            className="w-full flex items-center justify-center gap-1.5 bg-green-50 border border-green-200 text-green-700 text-[12.5px] font-semibold rounded-xl py-2.5 hover:bg-green-100 disabled:opacity-50 transition-colors min-h-[44px]">
            <Check className="h-4 w-4" />
            {marquerServiMutation.isPending ? 'En cours…' : 'Marquer comme servis'}
          </button>
        )}
      </div>
    </div>
  )
}
