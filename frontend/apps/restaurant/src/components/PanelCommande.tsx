import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { X, CreditCard, Users, Clock, Trash2, AlertTriangle } from 'lucide-react'
import { restaurantApi } from '@/api/restaurant'
import { normalizeError } from '@shared/errors/normalizer'
import { useFocusTrap } from '@shared/hooks/useFocusTrap'
import OngletCommande from './OngletCommande'
import OngletPaiement from './OngletPaiement'
import ModalAjouterPlat from './ModalAjouterPlat'

function fmtDuree(isoDate: string): string {
  const diff = Date.now() - new Date(isoDate).getTime()
  const min = Math.floor(diff / 60_000)
  if (min < 60) return `${min}min`
  return `${Math.floor(min / 60)}h${String(min % 60).padStart(2, '0')}`
}

function SkeletonPanel() {
  return (
    <div className="flex flex-col gap-3 animate-pulse p-5">
      <div className="flex items-center justify-between">
        <div className="bg-stone-200 rounded h-4 w-28" />
        <div className="bg-stone-200 rounded h-4 w-16" />
      </div>
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5">
          <div className="bg-stone-200 rounded h-3 w-40 mb-1.5" />
          <div className="bg-stone-200 rounded h-3 w-24" />
        </div>
      ))}
    </div>
  )
}

function ConfirmAnnulerDialog({
  onClose,
  onConfirm,
  isPending,
  error,
}: {
  onClose: () => void
  onConfirm: () => void
  isPending: boolean
  error: string
}) {
  const trapRef = useFocusTrap<HTMLDivElement>(onClose)
  return (
    <div className="absolute inset-0 z-10 flex items-center justify-center bg-white/80 backdrop-blur-sm">
      <div ref={trapRef} role="dialog" aria-modal="true" className="bg-white border border-stone-200 rounded-2xl p-5 mx-4 w-full max-w-xs shadow-xl">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <span className="text-[14px] font-bold text-stone-900">Annuler la commande ?</span>
        </div>
        <p className="text-[12.5px] text-stone-600 mb-4">Cette action est irréversible. Toutes les lignes seront supprimées.</p>
        {error && <div className="text-[12px] text-red-600 mb-3">{error}</div>}
        <div className="flex gap-2">
          <button onClick={onClose}
            className="flex-1 py-2 bg-stone-50 text-stone-900 text-[12.5px] font-semibold rounded-xl hover:bg-stone-100 border border-stone-200 min-h-[44px]">
            Non
          </button>
          <button onClick={onConfirm} disabled={isPending}
            className="flex-1 py-2 bg-red-500 text-white text-[12.5px] font-semibold rounded-xl hover:bg-red-600 disabled:opacity-50 min-h-[44px]">
            {isPending ? 'Annulation...' : 'Oui, annuler'}
          </button>
        </div>
      </div>
    </div>
  )
}

interface PanelCommandeProps {
  commandeId: number | null
  onClose: () => void
}

export default function PanelCommande({ commandeId, onClose }: PanelCommandeProps) {
  const qc = useQueryClient()
  const [onglet, setOnglet] = useState<'commande' | 'paiement'>('commande')
  const [showAnnuler, setShowAnnuler] = useState(false)
  const [showAjouter, setShowAjouter] = useState(false)
  const [annulerError, setAnnulerError] = useState('')

  const { data: commande, isLoading } = useQuery({
    queryKey: ['restaurant-commande', commandeId],
    queryFn: () => restaurantApi.getCommande(commandeId!),
    enabled: commandeId !== null,
    staleTime: 5_000,
  })

  const annulerMutation = useMutation({
    mutationFn: () => restaurantApi.annulerCommande(commandeId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['restaurant-tables'] })
      onClose()
    },
    onError: (err) => setAnnulerError(normalizeError(err).message || 'Erreur'),
  })

  if (!commandeId) {
    return (
      <div className="flex flex-col h-full items-center justify-center gap-3 px-5">
        <div className="w-12 h-12 rounded-full bg-stone-50 flex items-center justify-center">
          <CreditCard className="h-5 w-5 text-stone-400" />
        </div>
        <p className="text-[13px] text-stone-900 font-medium">Sélectionnez une table</p>
        <p className="text-[12px] text-stone-600 text-center">
          Cliquez sur une table libre pour l'ouvrir,<br/>ou sur une table occupée pour voir sa commande
        </p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between px-5 py-4 border-b border-stone-200">
          <div className="flex items-center gap-2">
            <div className="animate-pulse bg-stone-100 rounded-full h-7 w-24" />
            <div className="animate-pulse bg-stone-100 rounded-full h-7 w-20" />
          </div>
          <button onClick={onClose} className="text-stone-600 hover:text-stone-900 p-1" aria-label="Fermer">
            <X className="h-4 w-4" />
          </button>
        </div>
        <SkeletonPanel />
      </div>
    )
  }

  if (!commande) return null

  const peutPayer = commande.statut === 'OUVERTE' || commande.statut === 'SERVIE'
  const peutAnnuler = commande.statut === 'OUVERTE'

  return (
    <div className="flex flex-col h-full overflow-hidden bg-white">
      {/* Drag handle visible sur mobile (overlay full screen) */}
      <div className="md:hidden flex justify-center pt-2 pb-1">
        <div className="w-10 h-1 rounded-full bg-stone-300" />
      </div>
      {/* Header */}
      <div className="px-5 py-3 border-b border-stone-200">
        <div className="flex items-start justify-between mb-3 gap-3">
          <div className="min-w-0 flex-1">
            <div className="text-[16px] font-bold text-stone-900 leading-tight">
              {commande.table_numero ? `Table ${commande.table_numero}` : 'À emporter'}
            </div>
            {commande.nom_client && (
              <div className="text-[12px] text-stone-600 font-medium truncate">{commande.nom_client}</div>
            )}
            <div className="flex items-center gap-3 text-[12px] text-stone-500 mt-1">
              <span className="flex items-center gap-1"><Users className="h-3.5 w-3.5" />{commande.nb_couverts} couv.</span>
              <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{fmtDuree(commande.date_ouverture)}</span>
            </div>
          </div>
          <button onClick={onClose}
            className="text-stone-500 hover:text-stone-900 min-w-[44px] min-h-[44px] flex items-center justify-center -mt-1 -mr-2"
            aria-label="Fermer">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-0">
            <button onClick={() => setOnglet('commande')}
              className={`text-[14px] font-semibold px-4 h-12 border-b-2 transition-colors ${
                onglet === 'commande' ? 'text-amber-600 border-amber-600' : 'text-stone-600 border-transparent hover:text-stone-900'
              }`}>
              Commande
            </button>
            {peutPayer && (
              <button onClick={() => setOnglet('paiement')}
                className={`text-[14px] font-semibold px-4 h-12 border-b-2 transition-colors ${
                  onglet === 'paiement' ? 'text-amber-600 border-amber-600' : 'text-stone-600 border-transparent hover:text-stone-900'
                }`}>
                Paiement
              </button>
            )}
          </div>
          {peutAnnuler && (
            <button onClick={() => setShowAnnuler(true)}
              className="text-[12px] text-stone-500 hover:text-red-500 flex items-center gap-1.5 transition-colors min-h-[44px] px-2">
              <Trash2 className="h-3.5 w-3.5" /> Annuler
            </button>
          )}
        </div>
      </div>

      {/* Contenu */}
      <div className="flex-1 overflow-y-auto">
        {onglet === 'commande' && (
          <OngletCommande
            commande={commande}
            restaurantApi={{ supprimerLigne: restaurantApi.supprimerLigne, marquerPret: restaurantApi.marquerPret, marquerServi: restaurantApi.marquerServi }}
            onShowAjouter={() => setShowAjouter(true)}
          />
        )}
        {onglet === 'paiement' && peutPayer && (
          <OngletPaiement
            commande={commande}
            restaurantApi={{ payerCommande: restaurantApi.payerCommande }}
            onSuccess={onClose}
          />
        )}
      </div>

      {/* Modal ajout plat */}
      {showAjouter && (
        <ModalAjouterPlat
          commandeId={commande.id}
          onClose={() => setShowAjouter(false)}
          onAdded={() => qc.invalidateQueries({ queryKey: ['restaurant-commande', commande.id] })}
        />
      )}

      {/* Modal confirmation annulation */}
      {showAnnuler && (
        <ConfirmAnnulerDialog
          onClose={() => setShowAnnuler(false)}
          onConfirm={() => annulerMutation.mutate()}
          isPending={annulerMutation.isPending}
          error={annulerError}
        />
      )}
    </div>
  )
}
