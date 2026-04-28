import { useState } from 'react'
import { useParams, useNavigate, useSearch, Outlet } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import {
  useDevisDetail,
  useDevisMutations,
  useDevisPdf,
  useDevisVersions,
} from '@/api/queries/useDevis'
import { normalizeError } from '@shared/errors/normalizer'
import { SubNav } from '@/layout/SubNav'
import { DomainStatusBadge, ActionError, ErrorState } from '@shared/components/ui'
import { DevisActions } from './components/DevisActions'
import { DevisSendModal } from './components/DevisSendModal'
import { DevisConvertModal } from './components/DevisConvertModal'
import { DevisRefuseModal } from './components/DevisRefuseModal'
import { DevisPdfPreview } from './components/DevisPdfPreview'

type ModalType = 'send' | 'convert' | 'refuse'

function shiftDate(iso: string | null | undefined, days: number): string {
  if (!iso) return new Date().toISOString().slice(0, 10)
  const d = new Date(iso.slice(0, 10))
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

export default function DevisIdLayout() {
  const { id } = useParams({ strict: false }) as { id: string }
  const navigate = useNavigate()
  const searchParams = useSearch({ strict: false }) as { send?: string; action?: string }
  const devisId = parseInt(id, 10)

  const { data: devis, isLoading, error: queryError, refetch } = useDevisDetail(devisId)
  const { accept, refuse, cancel, duplicate, renew, startNegotiation, markVersionPending } = useDevisMutations()
  const pdfMutation = useDevisPdf()
  const { data: versions = [] } = useDevisVersions(devisId)

  const [modal, setModal] = useState<ModalType | null>(
    searchParams.action === 'convert' ? 'convert'
      : searchParams.send === '1' ? 'send'
      : null
  )
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null)
  const [refuseReason, setRefuseReason] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [showCancelConfirm, setShowCancelConfirm] = useState(false)

  const navItems = [
    { label: 'Détails', href: `/devis/${id}/` },
    { label: 'Prestations', href: `/devis/${id}/prestations` },
    { label: 'Négociation', href: `/devis/${id}/negotiation` },
    {
      label: 'Versions',
      href: `/devis/${id}/versions`,
      badge: versions.length > 0 ? versions.length : undefined,
    },
    { label: 'Demandes', href: `/devis/${id}/change-requests` },
  ]

  const handleAccept = () => {
    setActionError(null)
    accept.mutate(devisId, {
      onError: (err) =>
        setActionError(
          normalizeError(err).message ||
            "Erreur lors de l'acceptation."
        ),
    })
  }

  const handleRefuse = () => {
    setActionError(null)
    refuse.mutate(
      { id: devisId, reason: refuseReason || undefined },
      {
        onSuccess: () => setModal(null),
        onError: (err) =>
          setActionError(
            normalizeError(err).message ||
              'Erreur lors du refus.'
          ),
      }
    )
  }

  const handleCancel = () => {
    cancel.mutate(devisId, {
      onSuccess: () => setShowCancelConfirm(false),
      onError: (err) =>
        setActionError(
          normalizeError(err).message ||
            "Erreur lors de l'annulation."
        ),
    })
  }

  const handleDuplicate = () => {
    duplicate.mutate(devisId, {
      onSuccess: (d) => navigate({ to: '/devis/$id', params: { id: String(d.id) } }),
    })
  }

  const handleRenew = () => {
    setActionError(null)
    renew.mutate(devisId, {
      onSuccess: (d) => navigate({ to: '/devis/$id', params: { id: String(d.id) } }),
      onError: (err) =>
        setActionError(
          normalizeError(err).message ||
            'Erreur lors du renouvellement.'
        ),
    })
  }

  const handleStartNegotiation = () => {
    if (!devis) return
    setActionError(null)
    if (devis.status === 'negotiation') {
      navigate({ to: '/devis/$id/negotiation', params: { id: String(devisId) } })
      return
    }
    startNegotiation.mutate(devisId, {
      onSuccess: () => navigate({ to: '/devis/$id/negotiation', params: { id: String(devisId) } }),
      onError: (err) =>
        setActionError(
          normalizeError(err).message ||
            "Erreur lors de l'ouverture de la négociation."
        ),
    })
  }

  const handleVersionPending = () => {
    setActionError(null)
    markVersionPending.mutate(devisId, {
      onError: (err) =>
        setActionError(
          normalizeError(err).message ||
            'Erreur lors du passage en révision.'
        ),
    })
  }

  const handlePreviewPdf = () => {
    pdfMutation.mutate(devisId, {
      onSuccess: (blob) => {
        if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl)
        const url = URL.createObjectURL(blob)
        setPdfPreviewUrl(url)
      },
    })
  }

  const handleDownloadPdf = () => {
    if (pdfPreviewUrl) {
      const a = document.createElement('a')
      a.href = pdfPreviewUrl
      a.download = `devis-${devis?.reference ?? devisId}.pdf`
      a.click()
      return
    }
    pdfMutation.mutate(devisId, {
      onSuccess: (blob) => {
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `devis-${devis?.reference ?? devisId}.pdf`
        a.click()
        URL.revokeObjectURL(url)
      },
    })
  }

  if (queryError) {
    return <ErrorState onRetry={() => refetch()} />
  }

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="card p-6 space-y-4">
          <div className="h-5 skel rounded w-40" />
          <div className="h-3 skel rounded w-64" />
        </div>
        <div className="card p-6 space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex justify-between">
              <div className="h-3 skel rounded w-28" />
              <div className="h-3 skel rounded w-36" />
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!devis) {
    return <div className="py-12 text-center text-dark-400">Devis introuvable.</div>
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate({ to: '/devis' })}
            className="p-2 hover:bg-dark-600 rounded text-dark-400"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-4">
              <h1 className="text-xl font-semibold">{devis.reference}</h1>
              <DomainStatusBadge status={devis.status} />
            </div>
            <p className="text-sm text-dark-400">{devis.customer_name}</p>
          </div>
        </div>

        <DevisActions
          devisId={devisId}
          reference={devis.reference}
          status={devis.status}
          pdfPending={pdfMutation.isPending}
          acceptPending={accept.isPending}
          negotiationPending={startNegotiation.isPending}
          versionPendingPending={markVersionPending.isPending}
          renewPending={renew.isPending}
          duplicatePending={duplicate.isPending}
          cancelPending={cancel.isPending}
          showCancelConfirm={showCancelConfirm}
          onSend={() => setModal('send')}
          onAccept={handleAccept}
          onRefuse={() => setModal('refuse')}
          onConvert={() => setModal('convert')}
          onRenew={handleRenew}
          onNegotiate={handleStartNegotiation}
          onVersionPending={handleVersionPending}
          onPreviewPdf={handlePreviewPdf}
          onDuplicate={handleDuplicate}
          onCancelRequest={() => setShowCancelConfirm(true)}
          onCancelConfirm={handleCancel}
          onCancelAbort={() => setShowCancelConfirm(false)}
        />
      </div>

      <ActionError message={actionError} onDismiss={() => setActionError(null)} />

      {/* SubNav */}
      <div className="-mx-4 md:-mx-6 border-b border-dark-600">
        <SubNav items={navItems} />
      </div>

      {/* Outlet */}
      <Outlet />

      {/* Modals */}
      <DevisSendModal
        devisId={devisId}
        reference={devis.reference}
        open={modal === 'send'}
        onClose={() => setModal(null)}
      />
      <DevisConvertModal
        devisId={devisId}
        reference={devis.reference}
        open={modal === 'convert'}
        onClose={() => setModal(null)}
        deliveryDate={devis.delivery_date ?? shiftDate(devis.event_date, -1)}
        returnDate={devis.return_date ?? shiftDate(devis.event_date, 1)}
        eventDate={devis.event_date}
        eventLocation={devis.event_location}
        deliveryMethod={devis.delivery_method}
        deliveryFeeCents={devis.delivery_fee_cents}
        carrierName={devis.carrier_name}
        carrierCode={devis.carrier_code}
        deliveryAddress={devis.delivery_address}
        deliveryCity={devis.delivery_city}
        deliveryPostalCode={devis.delivery_postal_code}
        deliveryZoneId={devis.delivery_zone_id}
        deliveryInstructions={devis.delivery_instructions}
      />
      <DevisRefuseModal
        open={modal === 'refuse'}
        refuseReason={refuseReason}
        isPending={refuse.isPending}
        error={actionError}
        onReasonChange={setRefuseReason}
        onClose={() => setModal(null)}
        onConfirm={handleRefuse}
        devisNumber={devis.reference}
        totalAmountCents={devis.total_cents}
        customerName={devis.customer_name}
      />

      {pdfPreviewUrl && (
        <DevisPdfPreview
          url={pdfPreviewUrl}
          reference={devis.reference}
          onDownload={handleDownloadPdf}
          onClose={() => {
            URL.revokeObjectURL(pdfPreviewUrl)
            setPdfPreviewUrl(null)
          }}
        />
      )}
    </div>
  )
}
