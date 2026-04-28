import { Link } from '@tanstack/react-router'
import { FileText, ExternalLink, Send, Eye, Bell } from 'lucide-react'
import { normalizeError } from '@shared/errors/normalizer'
import { ActionError } from '@shared/components/ui/ActionError'
import { useInvoicesList, useCreateInvoice } from '@/api/queries'
import { formatCents, formatDate, cn } from '@/lib/utils'
import { INVOICE_STATUS_LABELS, INVOICE_STATUS_COLORS } from '@/lib/constants'

interface InvoiceSectionProps {
  reservationId: number
  eventDate: string
  status: string
}

export function InvoiceSection({ reservationId, eventDate, status }: InvoiceSectionProps) {
  const { data: invoicesData } = useInvoicesList({ reservation_id: reservationId }, true)
  const createMutation = useCreateInvoice()

  const hasInvoice = (invoicesData?.total ?? 0) > 0

  const handleCreateInvoice = () => {
    const today = new Date().toISOString().split('T')[0]
    const computed = new Date(new Date(eventDate).getTime() - 7 * 86400000).toISOString().split('T')[0]
    const dueDate = computed > today ? computed : new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0]
    createMutation.mutate({ reservation_id: reservationId, issue_date: today, due_date: dueDate })
  }

  return (
    <div className="space-y-3">
      <ActionError
        message={createMutation.error ? normalizeError(createMutation.error).message || 'Erreur lors de la création de la facture' : null}
        onDismiss={() => createMutation.reset()}
      />

      {createMutation.isSuccess && (
        <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm mb-4">
          Facture générée avec succès.{' '}
          <Link to="/finance/invoices" className="underline">Voir les factures</Link>
        </div>
      )}

      {hasInvoice && invoicesData?.items ? (
        <div className="space-y-2">
          {invoicesData.items.map((inv) => {
            const remaining = inv.total_amount_cents - (inv.paid_amount_cents ?? 0)
            const paidPct = inv.total_amount_cents > 0
              ? Math.round(((inv.paid_amount_cents ?? 0) / inv.total_amount_cents) * 100)
              : 0

            return (
              <div key={inv.id} className="p-4 card space-y-2">
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm">{inv.invoice_number}</span>
                    <span className={cn('text-xs px-2 py-0.5 rounded', INVOICE_STATUS_COLORS[inv.status] || 'bg-dark-900 text-dark-400')}>
                      {INVOICE_STATUS_LABELS[inv.status] || inv.status}
                    </span>
                  </div>
                  <span className="text-sm font-medium">{formatCents(inv.total_amount_cents)}</span>
                </div>
                {inv.status !== 'paid' && inv.status !== 'cancelled' && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-dark-400">
                      <span>Payé : {formatCents(inv.paid_amount_cents ?? 0)} / {formatCents(inv.total_amount_cents)}</span>
                      <span>Reste : {formatCents(remaining)}</span>
                    </div>
                    <div className="h-1.5 bg-dark-900 rounded-full overflow-hidden">
                      <div className="h-full bg-green-500 rounded-full transition-all" style={{ width: `${paidPct}%` }} />
                    </div>
                  </div>
                )}
                {/* Timeline mini */}
                {(inv.sent_at || inv.opened_at || inv.first_reminder_sent_at) && (
                  <div className="flex items-center gap-3 text-[11px] text-dark-400 pt-1">
                    {inv.sent_at && (
                      <span className="flex items-center gap-1">
                        <Send className="w-3 h-3 text-blue-400" />
                        Envoyée {formatDate(inv.sent_at)}
                      </span>
                    )}
                    {inv.opened_at && (
                      <span className="flex items-center gap-1">
                        <Eye className="w-3 h-3 text-green-400" />
                        Ouverte {formatDate(inv.opened_at)}
                      </span>
                    )}
                    {inv.first_reminder_sent_at && (
                      <span className="flex items-center gap-1">
                        <Bell className="w-3 h-3 text-amber-400" />
                        Relance {formatDate(inv.last_reminder_sent_at || inv.first_reminder_sent_at)}
                      </span>
                    )}
                  </div>
                )}

                <Link
                  to="/finance/invoices/$id"
                  params={{ id: String(inv.id) }}
                  className="inline-flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300"
                >
                  <ExternalLink className="w-3 h-3" />
                  {inv.status !== 'paid' && inv.status !== 'cancelled' ? 'Enregistrer un paiement' : 'Voir la facture'}
                </Link>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-dark-400">Aucune facture liée.</p>
          {status !== 'cancelled' && status !== 'draft' && (
            <button
              onClick={handleCreateInvoice}
              disabled={createMutation.isPending}
              className="btn-secondary btn-sm flex items-center gap-1"
            >
              <FileText className="w-3 h-3" />
              {createMutation.isPending ? 'Création…' : 'Générer facture'}
            </button>
          )}
        </div>
      )}
    </div>  )
}
