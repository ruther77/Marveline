import { PageHeader } from '@/components/PageHeader'
import { useState, useEffect } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { useReservationDetail, useUpdateReservation } from '@/api/queries/useReservations'
import { normalizeError } from '@shared/errors/normalizer'
import { ArrowLeft, Save, AlertTriangle } from 'lucide-react'
import type { ReservationUpdate } from '@/types/reservation'

type EventType = 'mariage' | 'anniversaire' | 'entreprise' | 'autre'

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  mariage: 'Mariage',
  anniversaire: 'Anniversaire',
  entreprise: 'Entreprise',
  autre: 'Autre',
}

const EVENT_TYPES: EventType[] = ['mariage', 'anniversaire', 'entreprise', 'autre']

const EDITABLE_STATUSES = [
  'draft', 'confirmed', 'confirmed_risk', 'pre_check',
]

export default function ReservationEditPage() {
  const { id } = useParams({ strict: false }) as { id: string }
  const reservationId = Number(id)

  const { data: reservation, isLoading, error: loadError } = useReservationDetail(reservationId)
  const updateMutation = useUpdateReservation()

  const [eventDate, setEventDate] = useState('')
  const [deliveryDate, setDeliveryDate] = useState('')
  const [returnDate, setReturnDate] = useState('')
  const [eventLocation, setEventLocation] = useState('')
  const [eventType, setEventType] = useState<EventType | ''>('')
  const [eventName, setEventName] = useState('')
  const [guestCount, setGuestCount] = useState<number | ''>('')
  const [depositPaid, setDepositPaid] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!reservation) return
    setEventDate(reservation.event_date?.slice(0, 10) ?? '')
    setDeliveryDate(reservation.delivery_date?.slice(0, 10) ?? '')
    setReturnDate(reservation.return_date?.slice(0, 10) ?? '')
    setEventLocation(reservation.event_location ?? '')
    setEventType(reservation.event_type ?? '')
    setEventName(reservation.event_name ?? '')
    setGuestCount(reservation.guest_count ?? '')
    setDepositPaid(reservation.deposit_paid)
  }, [reservation])

  const isReadOnly = reservation ? !EDITABLE_STATUSES.includes(reservation.status) : false
  const isDraft = reservation?.status === 'draft'

  // Détecte si les dates diffèrent de l'original (cascade mouvements inventaire)
  const datesChanged = reservation && !isDraft && (
    deliveryDate !== (reservation.delivery_date?.slice(0, 10) ?? '') ||
    returnDate !== (reservation.return_date?.slice(0, 10) ?? '')
  )

  const handleSave = async () => {
    setSaveError(null)
    setSaved(false)
    try {
      const payload: ReservationUpdate = {
        event_date: eventDate || undefined,
        delivery_date: deliveryDate || undefined,
        return_date: returnDate || undefined,
        event_location: eventLocation || undefined,
        event_type: eventType || undefined,
        event_name: eventName || undefined,
        guest_count: guestCount !== '' ? Number(guestCount) : undefined,
        deposit_paid: depositPaid,
      }
      await updateMutation.mutateAsync({ id: reservationId, data: payload })
      setSaved(true)
    } catch (err) {
      setSaveError(normalizeError(err).message || 'Erreur lors de la sauvegarde')
    }
  }

  // ── Loading skeleton ───────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-4">
        <div className="h-8 w-52 skel rounded animate-pulse" />
        <div className="card p-6 space-y-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-10 skel rounded animate-pulse" />
          ))}
        </div>
        <div className="card p-6 space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-10 skel rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  // ── Error / not found ──────────────────────────────────────────────────────
  if (loadError || !reservation) {
    return (
      <div className="max-w-2xl lg:max-w-5xl mx-auto">
        <div className="card p-8 text-center text-danger">
          {loadError ? normalizeError(loadError).message : 'Réservation introuvable'}
        </div>
      </div>
    )
  }

  // ── Main view ──────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl lg:max-w-5xl mx-auto space-y-4 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <Link
          to="/reservations/$id"
          params={{ id: String(reservationId) }}
          className="btn-secondary btn-sm flex items-center gap-2 min-h-[44px]"
        >
          <ArrowLeft className="w-4 h-4" />
          Retour
        </Link>
        <div className="flex-1 min-w-0">
          <PageHeader title="Modifier la réservation" subtitle={`${reservation.reference} — ${reservation.customer_name ?? ''}`} />
        </div>
        {isReadOnly && (
          <span className="text-xs font-medium px-2.5 py-1 rounded-lg bg-dark-900 text-dark-300">
            Non modifiable · {reservation.status}
          </span>
        )}
      </div>

      {/* Dates */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">Dates</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Date événement</label>
            <input
              type="date"
              className="input w-full"
              value={eventDate}
              onChange={e => setEventDate(e.target.value)}
              disabled={isReadOnly}
            />
          </div>
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Livraison</label>
            <input
              type="date"
              className="input w-full"
              value={deliveryDate}
              max={eventDate || undefined}
              onChange={e => setDeliveryDate(e.target.value)}
              disabled={isReadOnly}
            />
          </div>
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Retour</label>
            <input
              type="date"
              className="input w-full"
              value={returnDate}
              min={eventDate || undefined}
              onChange={e => setReturnDate(e.target.value)}
              disabled={isReadOnly}
            />
          </div>
        </div>
        {deliveryDate && eventDate && deliveryDate > eventDate && (
          <p className="text-sm text-red-400">La livraison doit être avant ou le jour de l&apos;événement.</p>
        )}
        {returnDate && eventDate && returnDate < eventDate && (
          <p className="text-sm text-red-400">Le retour doit être après ou le jour de l&apos;événement.</p>
        )}
        {datesChanged && (
          <div className="flex items-start gap-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
            <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
            <div className="text-sm text-amber-200">
              <p className="font-medium">Les dates de cette réservation sont déjà confirmées.</p>
              <p className="text-amber-300/80 mt-0.5">
                En modifiant les dates, les mouvements d'inventaire planifiés seront automatiquement recalés,
                et les montants des lignes seront recalculés selon la nouvelle durée de location.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Événement */}
      <div className="card p-6 space-y-4">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide">
          Événement
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Type</label>
            <select
              className="input w-full"
              value={eventType}
              onChange={e => setEventType(e.target.value as EventType | '')}
              disabled={isReadOnly}
            >
              <option value="">— Sélectionner —</option>
              {EVENT_TYPES.map(t => (
                <option key={t} value={t}>{EVENT_TYPE_LABELS[t]}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Nom de l'événement</label>
            <input
              className="input w-full"
              placeholder="Mariage Dupont"
              value={eventName}
              onChange={e => setEventName(e.target.value)}
              disabled={isReadOnly}
            />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Lieu</label>
            <input
              className="input w-full"
              placeholder="Salle des fêtes, Paris"
              value={eventLocation}
              onChange={e => setEventLocation(e.target.value)}
              disabled={isReadOnly}
            />
          </div>
          <div>
            <label className="text-sm text-dark-400 mb-1.5 block">Nombre d'invités</label>
            <input
              type="number"
              className="input w-full"
              placeholder="150"
              min={1}
              value={guestCount}
              onChange={e => setGuestCount(e.target.value ? Number(e.target.value) : '')}
              disabled={isReadOnly}
            />
          </div>
        </div>
      </div>

      {/* Acompte */}
      <div className="card p-6">
        <h2 className="text-xs font-semibold text-dark-400 uppercase tracking-wide mb-4">
          Acompte
        </h2>
        <div className="flex items-center gap-4">
          <input
            id="deposit-paid"
            type="checkbox"
            className="w-4 h-4 rounded"
            checked={depositPaid}
            onChange={e => setDepositPaid(e.target.checked)}
            disabled={isReadOnly}
          />
          <label htmlFor="deposit-paid" className="text-sm cursor-pointer">
            Acompte encaissé
          </label>
        </div>
      </div>

      {/* Actions */}
      {!isReadOnly && (
        <div className="flex items-center gap-4 justify-end flex-wrap">
          {saveError != null && (
            <p className="text-sm text-danger">{saveError}</p>
          )}
          {saved && (
            <p className="text-sm text-green-400">Sauvegardé ✓</p>
          )}
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending || (!!deliveryDate && !!eventDate && deliveryDate > eventDate) || (!!returnDate && !!eventDate && returnDate < eventDate)}
            className="btn-primary flex items-center gap-2 min-h-[44px]"
          >
            {updateMutation.isPending ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Enregistrer
          </button>
        </div>
      )}
    </div>
  )
}
