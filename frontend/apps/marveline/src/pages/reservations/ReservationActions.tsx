import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import {
  Bell, ClipboardCheck, Truck, CheckCircle, AlertTriangle, PackageCheck,
  Pen, Archive, RefreshCw, Trash2, FileSignature,
} from 'lucide-react'
import { Button, ConfirmDialog } from '@shared/components/ui'
import { normalizeError } from '@shared/errors/normalizer'
import { useToast } from '@/hooks'
import {
  useConfirmReservation, useCancelReservation, useDeleteReservation,
  useRemindReservationDeposit, useCompletePreCheck, useDeliverReservation,
  useCompleteReservation, useCloseReservationDispute, useArchiveReservation,
} from '@/api/queries'
import type { ReservationDetailFull, ReservationPhase } from '@/types/reservation'
import type { Deposit } from '@/types/deposit'
import { CancelReservationModal } from '@/pages/events/components/CancelReservationModal'
import { DeleteReservationModal } from '@/pages/events/components/DeleteReservationModal'
import { CloseDisputeModal } from '@/pages/events/components/CloseDisputeModal'
import { AmendReservationModal } from './components/AmendReservationModal'
import { ReturnInspectionModal } from './components/ReturnInspectionModal'
import { formatDate } from '@/lib/utils'
import { isDepositOk, isSignatureOk, isAdvancePaid, hasLines as reservationHasLines } from './selectors/reservationPhase'

interface ReservationActionsProps {
  reservation: ReservationDetailFull
  phase: ReservationPhase
  deposits: Deposit[]
}

type DialogKey =
  | null
  | 'cancel'
  | 'delete'
  | 'closeDispute'
  | 'confirmDeliver'
  | 'confirmComplete'
  | 'confirmDepartNoDeposit'
  | 'confirmPreCheckRisk'
  | 'amend'
  | 'inspection'

/**
 * Composant unique qui rend les CTAs contextuels pour chaque phase.
 *
 * - P0.2 : ConfirmDialog systématique sur toute action irréversible
 * - P1.3 : libellés Call-to-Value (bénéfice > action technique)
 * - P3.1 : toasts scopés succès + erreur par mutation (célébration §11)
 * - P3.2 : empty state terminee actif avec CTA création similaire
 */
export function ReservationActions({ reservation, phase, deposits }: ReservationActionsProps) {
  const navigate = useNavigate()
  const toast = useToast()
  const reservationId = reservation.id
  const idStr = String(reservationId)

  const confirmMut = useConfirmReservation()
  const cancelMut = useCancelReservation()
  const deleteMut = useDeleteReservation()
  const remindMut = useRemindReservationDeposit()
  const preCheckMut = useCompletePreCheck()
  const deliverMut = useDeliverReservation()
  const completeMut = useCompleteReservation()
  const closeDisputeMut = useCloseReservationDispute()
  const archiveMut = useArchiveReservation()

  const [dialog, setDialog] = useState<DialogKey>(null)

  const depositOk = isDepositOk(reservation, deposits)
  const signatureOk = isSignatureOk(reservation)
  const advanceOk = isAdvancePaid(reservation)
  const depositReleased = deposits[0]?.status === 'released'

  // Guards livraison consolidés : reflète les checks backend (B + C 2026-04-26).
  // L'opérateur ne devrait pas pouvoir cliquer un CTA qui retournera 422.
  const canDeliver = depositOk && signatureOk && advanceOk
  const deliveryBlockReasons = [
    !depositOk && 'caution non encaissée',
    !signatureOk && 'contrat non signé',
    !advanceOk && 'acompte non payé',
  ].filter(Boolean) as string[]
  const deliveryBlockTooltip = deliveryBlockReasons.length > 0
    ? `Livraison bloquée : ${deliveryBlockReasons.join(', ')}.`
    : undefined

  function toastError(errorTitle: string) {
    return (err: unknown) => toast.error(errorTitle, normalizeError(err).message || undefined)
  }

  const goOperationsDeparture = () =>
    navigate({ to: '/operations/departure/$reservationId', params: { reservationId: idStr } })
  const goOperationsReturn = () =>
    navigate({ to: '/operations/return/$reservationId', params: { reservationId: idStr } })
  const goSignature = () =>
    navigate({ to: '/reservations/$id/signature', params: { id: idStr } })
  const goLines = () =>
    navigate({ to: '/reservations/$id/lines', params: { id: idStr } })
  const goEdit = () =>
    navigate({ to: '/reservations/$id/edit', params: { id: idStr } })
  const goList = () => navigate({ to: '/reservations' })

  // Une résa issue d'un devis peut faire l'objet d'un avenant
  // (sauf statuts terminaux). Visible en pied de bloc actions.
  const canAmend =
    Boolean(reservation.devis_id)
    && reservation.status !== 'completed'
    && reservation.status !== 'cancelled'

  // Constat de retour rapide (modale P9) — visible UNIQUEMENT après le retour
  // pour ajouter des observations sans déclencher la transition d'état.
  // Avant retour, le flow officiel passe par /operations/return ("Enregistrer le retour")
  // qui assure stock + signature + dommages + facturation cohérents.
  const canInspect = (
    reservation.status === 'returned'
    || reservation.status === 'returned_dispute'
  )

  return (
    <div className="space-y-3">
      {renderPhaseCtas()}

      {canAmend && (
        <div className="pt-2 border-t border-dark-700/50">
          <button
            onClick={() => setDialog('amend')}
            className="text-sm text-primary-400 hover:text-primary-300 inline-flex items-center gap-1.5"
          >
            <FileSignature className="w-3.5 h-3.5" />
            Modifier le périmètre (avenant)
          </button>
        </div>
      )}

      {canInspect && (
        <div className="pt-2 border-t border-dark-700/50">
          <button
            onClick={() => setDialog('inspection')}
            className="text-sm text-primary-400 hover:text-primary-300 inline-flex items-center gap-1.5"
          >
            <ClipboardCheck className="w-3.5 h-3.5" />
            Ajouter un constat post-retour
          </button>
        </div>
      )}

      <AmendReservationModal
        open={dialog === 'amend'}
        onClose={() => setDialog(null)}
        reservation={reservation}
      />

      <ReturnInspectionModal
        open={dialog === 'inspection'}
        onClose={() => setDialog(null)}
        reservation={reservation}
      />

      <CancelReservationModal
        isOpen={dialog === 'cancel'}
        onClose={() => setDialog(null)}
        onConfirm={() => cancelMut.mutate(reservationId, {
          onSuccess: () => { setDialog(null); toast.success('Réservation annulée') },
          onError: toastError('Erreur annulation'),
        })}
        loading={cancelMut.isPending}
        reference={reservation.reference}
      />

      <DeleteReservationModal
        isOpen={dialog === 'delete'}
        onClose={() => setDialog(null)}
        onConfirm={() => deleteMut.mutate(reservationId, {
          onSuccess: () => { toast.success('Réservation supprimée'); goList() },
          onError: toastError('Erreur suppression'),
        })}
        loading={deleteMut.isPending}
        reference={reservation.reference}
      />

      <CloseDisputeModal
        isOpen={dialog === 'closeDispute'}
        onClose={() => setDialog(null)}
        onConfirm={(resolutionNotes) => closeDisputeMut.mutate(
          { reservationId, resolutionNotes },
          {
            onSuccess: () => { setDialog(null); toast.success('Litige clôturé') },
            onError: toastError('Erreur clôture litige'),
          },
        )}
        loading={closeDisputeMut.isPending}
        error={closeDisputeMut.error ? normalizeError(closeDisputeMut.error).message : null}
      />

      <ConfirmDialog
        isOpen={dialog === 'confirmDeliver'}
        title="Confirmer la livraison"
        description="Cette action marque la réservation comme livrée et verrouille le stock. Opération irréversible."
        confirmText="Oui, confirmer la livraison"
        variant="warning"
        onConfirm={() => {
          setDialog(null)
          deliverMut.mutate(reservationId, {
            onSuccess: () => toast.success('Livraison enregistrée', 'Le stock est verrouillé.'),
            onError: toastError('Erreur livraison'),
          })
        }}
        onClose={() => setDialog(null)}
      />

      <ConfirmDialog
        isOpen={dialog === 'confirmComplete'}
        title="Clôturer la réservation"
        description={
          depositReleased
            ? "La réservation sera archivée. Opération irréversible."
            : "La caution sera libérée et la réservation archivée. Opération irréversible."
        }
        confirmText={depositReleased ? "Oui, clôturer" : "Oui, clôturer et libérer la caution"}
        variant="warning"
        onConfirm={() => {
          setDialog(null)
          completeMut.mutate(reservationId, {
            onSuccess: () => toast.success(
              'Réservation clôturée',
              depositReleased ? 'Archivée avec succès.' : 'Caution libérée, matériel dispo.',
            ),
            onError: toastError('Erreur clôture'),
          })
        }}
        onClose={() => setDialog(null)}
      />

      <ConfirmDialog
        isOpen={dialog === 'confirmDepartNoDeposit'}
        title="Départ sans caution encaissée"
        description="La caution n'a pas encore été encaissée. Lancer le départ malgré tout ?"
        confirmText="Oui, lancer le départ"
        variant="warning"
        onConfirm={() => { setDialog(null); goOperationsDeparture() }}
        onClose={() => setDialog(null)}
      />

      <ConfirmDialog
        isOpen={dialog === 'confirmPreCheckRisk'}
        title="Valider le départ (risque accepté)"
        description="Cette réservation a un risque documenté. Continuer ?"
        confirmText="Oui, accepter le risque"
        variant="warning"
        onConfirm={() => {
          setDialog(null)
          preCheckMut.mutate(reservationId, {
            onSuccess: () => toast.success('Pre-check validé'),
            onError: toastError('Erreur pre-check'),
          })
        }}
        onClose={() => setDialog(null)}
      />
    </div>
  )

  function renderPhaseCtas() {
    switch (phase) {
      case 'brouillon': return renderBrouillon()
      case 'brouillon-incomplet': return renderBrouillonIncomplet()
      case 'confirmee': return renderConfirmee()
      case 'prete': return renderPrete()
      case 'risque': return renderRisque()
      case 'precheck': return renderPrecheck()
      case 'legal': return renderLegal()
      case 'en-cours': return renderEnCours()
      case 'prolongee': return renderProlongee()
      case 'retournee': return renderRetournee()
      case 'litige': return renderLitige()
      case 'terminee': return renderTerminee()
      case 'annulee': return renderAnnulee()
    }
  }

  function handleConfirm() {
    confirmMut.mutate(reservationId, {
      onSuccess: () => toast.success('Réservation confirmée', 'Le stock est réservé et le client notifié.'),
      onError: toastError('Erreur confirmation'),
    })
  }

  function handleLaunchPreCheck() {
    preCheckMut.mutate(reservationId, {
      onSuccess: () => toast.success('Pre-check lancé'),
      onError: toastError('Erreur pre-check'),
    })
  }

  function handleRemind() {
    remindMut.mutate(reservationId, {
      onSuccess: () => toast.success('Relance caution envoyée'),
      onError: toastError('Erreur relance'),
    })
  }

  function handleArchive() {
    archiveMut.mutate(reservationId, {
      onSuccess: () => toast.success('Réservation archivée'),
      onError: toastError('Erreur archivage'),
    })
  }

  function handleDepartOrWarn() {
    if (depositOk) goOperationsDeparture()
    else setDialog('confirmDepartNoDeposit')
  }

  function renderBrouillon() {
    const canConfirm = reservationHasLines(reservation)
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          onClick={handleConfirm}
          loading={confirmMut.isPending}
          disabled={!canConfirm}
          title={canConfirm ? undefined : 'Ajoute au moins un produit pour confirmer'}
          leftIcon={<CheckCircle className="w-4 h-4" />}
        >
          Valider et envoyer au client
        </Button>
        <Button variant="secondary" onClick={() => setDialog('cancel')}>
          Annuler
        </Button>
        <Button
          variant="secondary"
          onClick={() => setDialog('delete')}
          leftIcon={<Trash2 className="w-4 h-4" />}
        >
          Supprimer définitivement
        </Button>
      </div>
    )
  }

  function renderBrouillonIncomplet() {
    return (
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={goLines}>
          Ajouter des produits au devis
        </Button>
        <Button variant="secondary" onClick={goEdit}>
          Compléter les infos client
        </Button>
        <Button variant="secondary" onClick={() => setDialog('delete')}>
          Supprimer le brouillon
        </Button>
      </div>
    )
  }

  function renderConfirmee() {
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          onClick={handleLaunchPreCheck}
          loading={preCheckMut.isPending}
          leftIcon={<ClipboardCheck className="w-4 h-4" />}
        >
          Lancer le pre-check terrain
        </Button>
        <Button
          variant="secondary"
          onClick={handleDepartOrWarn}
          leftIcon={<Truck className="w-4 h-4" />}
        >
          Livrer maintenant
        </Button>
        <Button
          variant="secondary"
          onClick={handleRemind}
          loading={remindMut.isPending}
          leftIcon={<Bell className="w-4 h-4" />}
        >
          Relancer la caution
        </Button>
      </div>
    )
  }

  function renderPrete() {
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          onClick={goOperationsDeparture}
          leftIcon={<Truck className="w-4 h-4" />}
          disabled={!canDeliver}
          title={deliveryBlockTooltip}
        >
          Livrer maintenant au client
        </Button>
        {!canDeliver && (
          <p className="text-xs text-amber-300 w-full">
            ⚠ {deliveryBlockTooltip}
          </p>
        )}
      </div>
    )
  }

  function renderRisque() {
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          onClick={() => setDialog('confirmPreCheckRisk')}
          leftIcon={<ClipboardCheck className="w-4 h-4" />}
        >
          Valider le pre-check (risque accepté)
        </Button>
        <Button
          variant="secondary"
          onClick={handleDepartOrWarn}
          leftIcon={<Truck className="w-4 h-4" />}
        >
          Livrer malgré le risque
        </Button>
        <Button
          variant="secondary"
          onClick={handleRemind}
          loading={remindMut.isPending}
          leftIcon={<Bell className="w-4 h-4" />}
        >
          Relancer la caution
        </Button>
        <Button variant="secondary" onClick={() => setDialog('cancel')}>
          Annuler la réservation
        </Button>
      </div>
    )
  }

  function renderPrecheck() {
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          onClick={goOperationsDeparture}
          leftIcon={<Truck className="w-4 h-4" />}
        >
          Départ opérationnel
        </Button>
        <Button
          variant="secondary"
          onClick={() => setDialog('confirmDeliver')}
          leftIcon={<PackageCheck className="w-4 h-4" />}
        >
          Confirmer la livraison
        </Button>
      </div>
    )
  }

  function renderLegal() {
    return (
      <div className="flex flex-wrap gap-2">
        {!signatureOk && (
          <Button
            variant="primary"
            onClick={goSignature}
            leftIcon={<Pen className="w-4 h-4" />}
          >
            Signer le contrat maintenant
          </Button>
        )}
        <Button
          variant="secondary"
          onClick={handleDepartOrWarn}
          leftIcon={<Truck className="w-4 h-4" />}
        >
          Livrer malgré tout
        </Button>
      </div>
    )
  }

  function renderEnCours() {
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          onClick={goOperationsReturn}
          leftIcon={<PackageCheck className="w-4 h-4" />}
        >
          Enregistrer le retour
        </Button>
      </div>
    )
  }

  function renderProlongee() {
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          onClick={goOperationsReturn}
          leftIcon={<PackageCheck className="w-4 h-4" />}
        >
          Enregistrer le retour
        </Button>
      </div>
    )
  }

  function renderRetournee() {
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          onClick={() => setDialog('confirmComplete')}
          loading={completeMut.isPending}
          leftIcon={<CheckCircle className="w-4 h-4" />}
        >
          {depositReleased ? 'Clôturer la réservation' : 'Clôturer et libérer la caution'}
        </Button>
        <Button
          variant="secondary"
          onClick={goOperationsReturn}
          leftIcon={<AlertTriangle className="w-4 h-4" />}
        >
          Signaler un dommage
        </Button>
      </div>
    )
  }

  function renderLitige() {
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          onClick={() => setDialog('closeDispute')}
          leftIcon={<CheckCircle className="w-4 h-4" />}
        >
          Clore le litige
        </Button>
        <Button
          variant="secondary"
          onClick={goOperationsReturn}
          leftIcon={<AlertTriangle className="w-4 h-4" />}
        >
          Voir les dommages
        </Button>
      </div>
    )
  }

  function renderTerminee() {
    return (
      <div className="space-y-3">
        {reservation.is_archived ? (
          <div className="card p-4 flex items-center gap-3">
            <Archive className="w-5 h-5 text-dark-400 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-dark-100">Réservation archivée</p>
              {reservation.updated_at && (
                <p className="text-xs text-dark-400">
                  Archivée le {formatDate(reservation.updated_at)}
                </p>
              )}
            </div>
          </div>
        ) : (
          <Button
            variant="secondary"
            onClick={handleArchive}
            loading={archiveMut.isPending}
            leftIcon={<Archive className="w-4 h-4" />}
          >
            Archiver la réservation
          </Button>
        )}
        <Button
          variant="primary"
          onClick={() => navigate({
            to: '/devis/new',
            search: { customer_id: reservation.customer_id } as never,
          })}
          leftIcon={<RefreshCw className="w-4 h-4" />}
        >
          Créer une réservation similaire pour ce client
        </Button>
      </div>
    )
  }

  function renderAnnulee() {
    return (
      <div className="flex flex-wrap gap-2">
        {!reservation.is_archived && (
          <Button
            variant="secondary"
            onClick={handleArchive}
            loading={archiveMut.isPending}
            leftIcon={<Archive className="w-4 h-4" />}
          >
            Archiver
          </Button>
        )}
        <Button
          variant="primary"
          onClick={() => navigate({
            to: '/devis/new',
            search: { customer_id: reservation.customer_id } as never,
          })}
          leftIcon={<RefreshCw className="w-4 h-4" />}
        >
          Créer une réservation similaire
        </Button>
      </div>
    )
  }
}
