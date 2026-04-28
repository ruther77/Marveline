import { useState } from 'react'
import { X, FileSignature, AlertCircle } from 'lucide-react'
import { Button } from '@shared/components/ui'
import { normalizeError } from '@shared/errors/normalizer'
import { useAmendReservation } from '@/api/queries'
import type { ReservationDetailFull, ReservationAmendRequest } from '@/types/reservation'
import { useToast } from '@/hooks'

interface AmendReservationModalProps {
  open: boolean
  onClose: () => void
  reservation: ReservationDetailFull
}

/**
 * Modale "Modifier le périmètre" — déclenche un avenant sur une résa convertie.
 *
 * - Visible uniquement si `reservation.devis_id` est défini.
 * - Crée une DevisVersion pre-amend côté backend (snapshot contractuel).
 * - Applique les modifications de dates + lines en bypass des guards 409.
 * - V1 : raison + dates uniquement (lines à ajouter en V2).
 */
export function AmendReservationModal({ open, onClose, reservation }: AmendReservationModalProps) {
  const toast = useToast()
  const amendMut = useAmendReservation()

  const [reason, setReason] = useState('')
  const [eventDate, setEventDate] = useState('')
  const [deliveryDate, setDeliveryDate] = useState('')
  const [returnDate, setReturnDate] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (!open) return null

  const hasChanges = Boolean(eventDate || deliveryDate || returnDate)
  const canSubmit = reason.trim().length >= 3 && hasChanges && !amendMut.isPending

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const payload: ReservationAmendRequest = { reason: reason.trim() }
    if (eventDate) payload.event_date = eventDate
    if (deliveryDate) payload.delivery_date = deliveryDate
    if (returnDate) payload.return_date = returnDate

    amendMut.mutate(
      { id: reservation.id, payload },
      {
        onSuccess: () => {
          toast.success('Avenant créé', `Une nouvelle version du devis a été générée.`)
          onClose()
          // Reset
          setReason('')
          setEventDate('')
          setDeliveryDate('')
          setReturnDate('')
        },
        onError: (err) => {
          setError(normalizeError(err).message || 'Erreur lors de l\'avenant')
        },
      },
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-dark-800 rounded-xl border border-dark-600 w-full max-w-lg shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-5 py-4 border-b border-dark-600">
          <div className="flex items-center gap-2">
            <FileSignature className="w-5 h-5 text-primary-400" />
            <h2 className="font-bold">Modifier le périmètre</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Fermer"
            className="text-dark-400 hover:text-dark-200"
          >
            <X className="w-5 h-5" />
          </button>
        </header>

        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-4">
          <p className="text-sm text-dark-300">
            Cette modification créera une <strong>nouvelle version du devis</strong>{' '}
            ({reservation.reference}) tracée pour le client. La raison apparaîtra dans
            les notes et l'historique.
          </p>

          <div>
            <label className="text-sm font-medium block mb-1">
              Raison de l'avenant <span className="text-red-400">*</span>
            </label>
            <textarea
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Ex : Client souhaite reporter de 10 jours, ajout 20 chaises…"
              className="input w-full"
              required
              minLength={3}
              maxLength={500}
            />
          </div>

          <fieldset className="border border-dark-700 rounded-lg p-3 space-y-2">
            <legend className="text-xs text-dark-400 px-1">Nouvelles dates (au moins une)</legend>

            <div>
              <label className="text-xs text-dark-400 block">Date événement</label>
              <input
                type="date"
                value={eventDate}
                onChange={(e) => setEventDate(e.target.value)}
                className="input w-full"
              />
            </div>

            <div>
              <label className="text-xs text-dark-400 block">Date livraison</label>
              <input
                type="date"
                value={deliveryDate}
                onChange={(e) => setDeliveryDate(e.target.value)}
                className="input w-full"
              />
            </div>

            <div>
              <label className="text-xs text-dark-400 block">Date retour</label>
              <input
                type="date"
                value={returnDate}
                onChange={(e) => setReturnDate(e.target.value)}
                className="input w-full"
              />
            </div>
          </fieldset>

          {!hasChanges && (
            <p className="text-xs text-dark-400 flex items-center gap-1">
              <AlertCircle className="w-3 h-3" /> Renseignez au moins une nouvelle date.
            </p>
          )}

          {error && (
            <div className="bg-red-900/30 border border-red-600/40 text-red-300 text-sm rounded-lg px-3 py-2">
              {error}
            </div>
          )}
        </form>

        <footer className="flex justify-end gap-2 px-5 py-4 border-t border-dark-600">
          <Button variant="ghost" onClick={onClose} disabled={amendMut.isPending}>
            Annuler
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit as unknown as () => void}
            disabled={!canSubmit}
          >
            {amendMut.isPending ? 'Création…' : 'Créer l\'avenant'}
          </Button>
        </footer>
      </div>
    </div>
  )
}
