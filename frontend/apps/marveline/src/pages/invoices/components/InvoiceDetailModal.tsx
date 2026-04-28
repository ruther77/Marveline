import { useState } from 'react'
import { normalizeError } from '@shared/errors/normalizer'
import { ActionError } from '@shared/components/ui/ActionError'
import {
  useInvoiceFull,
  useInvoicePayments,
  useAddPaymentRecord,
  useCancelInvoice,
  useAddCharge,
  useInvoiceCreditNotes,
  useCreateCreditNote,
  useMarkInvoiceSent,
  useRemindInvoice,
  useTenantSettings,
  useInvoicePdf,
} from '@/api/queries'
import { Modal } from '@shared/components/ui/Modal'
import { formatDate } from '@/lib/utils'
import { VAT_RATE, HOURLY_RATE_WEEKDAY_EUR, HOURLY_RATE_WEEKEND_EUR } from '@/lib/constants'
import type { PaymentMethod } from '@/types/invoice'
import { InvoiceDetailHeader } from './InvoiceDetailHeader'
import { InvoicePaymentProgress } from './InvoicePaymentProgress'
import { InvoicePaymentForm } from './InvoicePaymentForm'
import { InvoicePaymentHistory } from './InvoicePaymentHistory'
import { InvoiceInfoGrid } from './InvoiceInfoGrid'
import { InvoiceLinkedReservation } from './InvoiceLinkedReservation'
import { InvoiceChargesSection } from './InvoiceChargesSection'
import { InvoiceCreditNotesSection } from './InvoiceCreditNotesSection'
import { InvoiceAuditTimeline } from './InvoiceAuditTimeline'
import { InvoiceMarkSentModal } from './InvoiceMarkSentModal'

interface InvoiceDetailModalProps {
  isOpen: boolean
  onClose: () => void
  invoiceId?: number
}

export function InvoiceDetailModal({ isOpen, onClose, invoiceId }: InvoiceDetailModalProps) {
  const [showPaymentForm, setShowPaymentForm] = useState(false)
  const [showSendModal, setShowSendModal] = useState(false)
  const [cancelError, setCancelError] = useState<string | null>(null)

  const cancelErrHandler = (err: unknown) => setCancelError(
    normalizeError(err).message || 'Une erreur est survenue'
  )

  const activeId = isOpen && invoiceId ? invoiceId : null
  const { data: tenantSettings } = useTenantSettings()
  const { data: invoice, isLoading } = useInvoiceFull(activeId)
  const effectiveVatRate = invoice?.tva_rate ?? tenantSettings?.vat_rate ?? VAT_RATE
  const effectiveHourlyWeekday = tenantSettings?.hourly_rate_weekday ?? HOURLY_RATE_WEEKDAY_EUR
  const effectiveHourlyWeekend = tenantSettings?.hourly_rate_weekend ?? HOURLY_RATE_WEEKEND_EUR

  const { data: payments = [] } = useInvoicePayments(activeId)
  const paymentMutation = useAddPaymentRecord()
  const cancelMutation = useCancelInvoice()
  const markSentMutation = useMarkInvoiceSent(activeId ?? 0)
  const remindMutation = useRemindInvoice(activeId ?? 0)
  const invoicePdfMutation = useInvoicePdf()
  const chargeMutation = useAddCharge()
  const { data: creditNotes = [] } = useInvoiceCreditNotes(activeId)
  const creditNoteMutation = useCreateCreditNote(activeId ?? 0)

  const handleDownloadPdf = async () => {
    if (!invoice) return
    const blob = await invoicePdfMutation.mutateAsync(invoice.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `facture-${invoice.invoice_number}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleClose = () => {
    setShowPaymentForm(false)
    setShowSendModal(false)
    onClose()
  }

  return (
    <>
      <Modal isOpen={isOpen} onClose={handleClose} title="Détails de la facture" size="lg">
        {isLoading ? (
          <div className="space-y-4 animate-pulse">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-4">
                <div className="w-5 h-5 skel rounded" />
                <div className="h-6 skel rounded w-32" />
              </div>
              <div className="h-6 skel rounded w-20" />
            </div>
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex justify-between py-2 border-b border-dark-600">
                <div className="h-3 skel rounded w-24" />
                <div className="h-3 skel rounded w-32" />
              </div>
            ))}
            <div className="card divide-y divide-dark-600">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 px-4 py-4">
                  <div className="flex-1 space-y-2">
                    <div className="h-3 skel rounded w-40" />
                    <div className="h-2 skel rounded w-24" />
                  </div>
                  <div className="h-3 skel rounded w-16 shrink-0" />
                </div>
              ))}
            </div>
          </div>
        ) : invoice ? (
          <div className="space-y-6">
            <InvoiceDetailHeader
              invoice={invoice}
              cancelPending={cancelMutation.isPending}
              remindPending={remindMutation.isPending}
              showPaymentForm={showPaymentForm}
              onDownloadPdf={handleDownloadPdf}
              onOpenSendModal={() => setShowSendModal(true)}
              onRemind={() => remindMutation.mutate(undefined, { onError: () => {} })}
              onTogglePaymentForm={() => setShowPaymentForm(!showPaymentForm)}
              onCancel={() => cancelMutation.mutate(invoice.id, { onError: cancelErrHandler })}
            />

            <ActionError message={cancelError} onDismiss={() => setCancelError(null)} />
            <ActionError
              message={remindMutation.error ? normalizeError(remindMutation.error).message || 'Erreur lors de la relance' : null}
              onDismiss={() => remindMutation.reset()}
            />

            <InvoicePaymentProgress invoice={invoice} />

            {showPaymentForm && (
              <InvoicePaymentForm
                remainingCents={invoice.remaining_amount_cents}
                isPending={paymentMutation.isPending}
                error={paymentMutation.error as { response?: { data?: { detail?: string } } } | null}
                onSubmit={(data) =>
                  paymentMutation.mutate(
                    { invoiceId: invoice.id, data: { amount_cents: data.amount_cents, payment_method: data.payment_method as PaymentMethod, payment_date: data.payment_date, notes: data.notes } },
                    { onSuccess: () => setShowPaymentForm(false) }
                  )
                }
                onCancel={() => setShowPaymentForm(false)}
              />
            )}

            <InvoicePaymentHistory payments={payments} />

            <InvoiceInfoGrid invoice={invoice} effectiveVatRate={effectiveVatRate} />

            {invoice.reservation && (
              <InvoiceLinkedReservation reservation={invoice.reservation} />
            )}

            <InvoiceChargesSection
              invoiceId={invoice.id}
              status={invoice.status}
              charges={invoice.charges}
              isPending={chargeMutation.isPending}
              error={chargeMutation.error as { response?: { data?: { detail?: string } } } | null}
              effectiveHourlyWeekday={effectiveHourlyWeekday}
              effectiveHourlyWeekend={effectiveHourlyWeekend}
              onSubmit={(charge) => chargeMutation.mutate({ invoiceId: invoice.id, charge })}
            />

            <InvoiceCreditNotesSection
              status={invoice.status}
              creditNotes={creditNotes}
              isPending={creditNoteMutation.isPending}
              onSubmit={(data) => creditNoteMutation.mutate(data)}
            />

            <InvoiceAuditTimeline invoice={invoice} payments={payments} creditNotes={creditNotes} />
          </div>
        ) : (
          <div className="text-center py-8 text-dark-400">Facture introuvable</div>
        )}
      </Modal>

      {showSendModal && invoice && (
        <InvoiceMarkSentModal
          invoiceNumber={invoice.invoice_number}
          isPending={markSentMutation.isPending}
          error={markSentMutation.error as { response?: { data?: { detail?: string } } } | null}
          onConfirm={(data) =>
            markSentMutation.mutate(
              { sent_at: data.sent_at, notes: data.notes },
              { onSuccess: () => setShowSendModal(false) }
            )
          }
          onClose={() => setShowSendModal(false)}
        />
      )}
    </>
  )
}
